#!/usr/bin/env python3
"""Shared HTML → PNG capture helpers (Chrome print-to-PDF, single tall page).

自动截图用本机 Chrome/Chromium。不改 HOME（避免 macOS 钥匙串弹窗），
使用 --use-mock-keychain，并隔离 crash dumps，尽量减少系统对话框。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]

# 截图版式宽度（CSS px），与 @page size 一致
PAGE_WIDTH_CSS = 750
# Chrome print-to-PDF 按 96dpi → 72pt 换算，1 CSS px = 0.75 pt
PT_PER_CSS_PX = 0.75
# 默认输出倍数：2 倍图（1500px 宽），兼顾清晰度与文件体积
DEFAULT_ZOOM = 2.0
# 报告 @media print 字号约 1.4×，高度估算乘此系数
PRINT_TYPE_SCALE = 1.4
# 超长图保护：避免 pixmap 占用过高内存 / 生成平台无法处理的巨图
MAX_LONG_EDGE_PX = 32000
MAX_TOTAL_PX = 80_000_000

CHROME_PATHS = [
    "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("google-chrome") or "",
    shutil.which("google-chrome-stable") or "",
]


def find_chrome() -> str | None:
    env = (os.environ.get("AI_RESUME_CHROME") or os.environ.get("CHROME_PATH") or "").strip()
    if env and Path(env).exists():
        return env
    for p in CHROME_PATHS:
        if p and Path(p).exists():
            return p
    return None


def favicon_link_html(root: Path | None = None, *, name: str = "favicon.svg") -> str:
    """Inline SVG favicon so outbox HTML stays self-contained.

    name:
      - favicon.svg      — review（紫粉橙，对齐诊断页头）
      - favicon-jd.svg    — jd（靛蓝→紫→青，对齐岗位匹配页头高分渐变）
      - favicon-diff.svg — diff（青绿→蓝，对齐对比页头）
    """
    base = root or ROOT
    svg_path = base / "templates" / name
    if not svg_path.exists():
        return ""
    svg = " ".join(svg_path.read_text(encoding="utf-8").split())
    href = "data:image/svg+xml," + quote(svg, safe="")
    return f'<link rel="icon" type="image/svg+xml" href="{href}" />'


def estimate_page_height(html: str) -> int:
    """Estimate required single-page height in CSS px (upper bound, later cropped).

    模板 @media print 会放大字号，高度按 PRINT_TYPE_SCALE 上调。
    """
    n_pair = html.count('class="pair"')
    n_section = html.count('class="section-card"')
    if n_pair:
        note_bonus = html.count('class="pair-note"') * 32
        score_bonus = 140 if "score-strip" in html else 0
        base = max(2200, 320 + score_bonus + n_section * 72 + n_pair * 168 + note_bonus)
        return min(50000, int(base * PRINT_TYPE_SCALE))

    n_hunk = html.count('class="hunk"')
    if n_hunk:
        return min(50000, int(max(1600, 200 + n_hunk * 130) * PRINT_TYPE_SCALE))

    n_diff = html.count('class="diff-item"')
    if n_diff:
        return min(60000, int(max(2400, 360 + n_diff * 300) * PRINT_TYPE_SCALE))

    n_dim = html.count('class="dim-item"')
    n_card = html.count('class="card ')
    n_li = len(re.findall(r"<li[\s>]", html))
    base = max(2600, 1100 + n_card * 210 + n_dim * 105 + n_li * 46)
    return min(16000, int(base * PRINT_TYPE_SCALE))


def resolve_zoom(zoom: float | None = None) -> float:
    """输出倍数：显式参数 > 环境变量 AI_RESUME_CAPTURE_ZOOM > 默认 2 倍。"""
    if zoom is not None:
        return max(1.0, float(zoom))
    env = (os.environ.get("AI_RESUME_CAPTURE_ZOOM") or "").strip()
    if env:
        try:
            return max(1.0, float(env))
        except ValueError:
            print(f"[warn] AI_RESUME_CAPTURE_ZOOM={env!r} 不是数字，按默认 {DEFAULT_ZOOM} 倍处理。")
    return DEFAULT_ZOOM


def clamp_zoom(zoom: float, height_css: int, width_css: int = PAGE_WIDTH_CSS) -> float:
    """超长图按长边与总像素上限回退倍数，避免内存爆掉。"""
    by_edge = MAX_LONG_EDGE_PX / max(width_css, height_css)
    by_area = (MAX_TOTAL_PX / (width_css * height_css)) ** 0.5
    allowed = max(1.0, min(by_edge, by_area))
    if zoom > allowed:
        print(f"[warn] 页面过长（约 {height_css}px），倍数由 {zoom:g} 回退到 {allowed:.2f}。")
        return allowed
    return zoom


def inject_capture_page_size(html: str, height_px: int) -> str:
    style = f"""
<style id="capture-page-size">
  @page {{ size: {PAGE_WIDTH_CSS}px {height_px}px; margin: 0; }}
  html, body {{
    height: auto !important;
    min-height: 0 !important;
    overflow: visible !important;
  }}
</style>
"""
    if "</head>" in html:
        return html.replace("</head>", style + "</head>", 1)
    return style + html


def _pixel_rgb(pix, x: int, y: int) -> tuple[int, int, int]:
    p = pix.pixel(x, y)
    return int(p[0]), int(p[1]), int(p[2])


def _row_stats(pix, y: int, samples: int = 24) -> tuple[tuple[int, int, int], int]:
    step = max(1, pix.width // samples)
    rs = gs = bs = 0
    n = 0
    colors: list[tuple[int, int, int]] = []
    for x in range(0, pix.width, step):
        rgb = _pixel_rgb(pix, x, y)
        colors.append(rgb)
        rs += rgb[0]
        gs += rgb[1]
        bs += rgb[2]
        n += 1
    avg = (rs // n, gs // n, bs // n)
    spread = 0
    for r, g, b in colors:
        spread = max(spread, abs(r - avg[0]), abs(g - avg[1]), abs(b - avg[2]))
    return avg, spread


def _color_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _is_blank_row(
    avg: tuple[int, int, int],
    spread: int,
    backgrounds: list[tuple[int, int, int]],
) -> bool:
    if spread >= 10:
        return False
    return any(_color_dist(avg, bg) < 22 for bg in backgrounds)


def _crop_to_height(pix, bottom: int):
    import fitz

    bottom = max(1, min(bottom, pix.height))
    if bottom >= pix.height - 2:
        return pix
    cropped = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, pix.width, bottom), 0)
    cropped.copy(pix, fitz.IRect(0, 0, pix.width, bottom))
    return cropped


def _detect_body_padding_bottom(html: str) -> int:
    m = re.search(r"body\s*\{[^}]*?padding-bottom:\s*(\d+)px", html, re.S)
    if m:
        return max(0, int(m.group(1)))
    return 14


def _trim_bottom_padding(pix, pad: int = 21):
    backgrounds: list[tuple[int, int, int]] = [
        (255, 255, 255),
        (246, 248, 250),
        (238, 242, 255),
        (253, 244, 255),
        (255, 247, 237),
    ]
    for y in (pix.height - 1, pix.height - 2, pix.height - 12, pix.height - 40):
        if 0 <= y < pix.height:
            avg, spread = _row_stats(pix, y)
            if spread < 14:
                backgrounds.append(avg)

    last_content = 0
    for y in range(pix.height - 1, -1, -1):
        avg, spread = _row_stats(pix, y)
        if not _is_blank_row(avg, spread, backgrounds):
            last_content = y
            break

    bottom = min(pix.height, last_content + pad)
    return _crop_to_height(pix, bottom)


def _capture_env(td: Path) -> dict[str, str]:
    """截图进程环境：不改 HOME（改 HOME 会触发 macOS「找不到钥匙串」弹窗）。"""
    env = os.environ.copy()
    env["CHROME_HEADLESS"] = "1"
    env["BREAKPAD_DUMP_LOCATION"] = str(td / "breakpad")
    # 避免 headless 去碰系统钥匙串 / 凭据存储
    env.pop("GOOGLE_API_KEY", None)
    return env


def _run_chrome_pdf(chrome: str, url: str, pdf_path: Path, td: Path) -> None:
    crash_dir = td / "crashes"
    crash_dir.mkdir(parents=True, exist_ok=True)
    env = _capture_env(td)

    # 说明：
    # - 不改 HOME、不加临时 --user-data-dir（前者弹钥匙串，后者在 macOS 易卡住）
    # - --use-mock-keychain / --password-store=basic：禁止访问系统钥匙串
    # - crash-dumps-dir + 关闭 crash reporter：尽量少弹「意外退出」
    common = [
        f"--crash-dumps-dir={crash_dir}",
        "--disable-crash-reporter",
        "--disable-breakpad",
        "--use-mock-keychain",
        "--password-store=basic",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",
        f"--print-to-pdf={pdf_path}",
        "--no-pdf-header-footer",
    ]
    attempts = [
        [chrome, "--headless=new", *common, url],
        [chrome, "--headless", *common, url],
    ]

    last_err: Exception | None = None
    for cmd in attempts:
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=90,
                env=env,
                start_new_session=True,
            )
            if pdf_path.exists() and pdf_path.stat().st_size >= 100:
                return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            last_err = e
            continue

    raise RuntimeError(f"Chrome 截图失败: {last_err}")


def html_to_png(html_path: Path, png_path: Path, *, zoom: float | None = None) -> bool:
    """Render local HTML file to a single long PNG, cropped to content.

    zoom 为相对 750px 版式的真实输出倍数（2 → 1500px 宽）。
    """
    import fitz

    chrome = find_chrome()
    if not chrome:
        print("[warn] 未找到 Chrome，跳过自动截图。可手动在浏览器中打开 HTML 截屏。")
        return False

    raw = html_path.read_text(encoding="utf-8")
    height = estimate_page_height(raw)
    prepared = inject_capture_page_size(raw, height)
    zoom = clamp_zoom(resolve_zoom(zoom), height)
    pad_css = _detect_body_padding_bottom(raw)
    pad_px = max(8, int(round(pad_css * zoom)))

    png_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ai-resume-capture-") as td_str:
        td = Path(td_str)
        prep_html = td / "capture.html"
        prep_pdf = td / "capture.pdf"
        prep_html.write_text(prepared, encoding="utf-8")
        url = prep_html.resolve().as_uri()

        try:
            _run_chrome_pdf(chrome, url, prep_pdf, td)
        except RuntimeError as e:
            print(f"[warn] {e}。可手动在浏览器中打开 HTML 截屏。")
            return False
        except Exception as e:  # noqa: BLE001
            print(f"[warn] Chrome 截图异常: {e}。可手动在浏览器中打开 HTML 截屏。")
            return False

        if not prep_pdf.exists() or prep_pdf.stat().st_size < 100:
            print("[warn] Chrome 未生成有效 PDF。")
            return False

        doc = fitz.open(str(prep_pdf))
        page_count = doc.page_count
        if page_count != 1:
            print(f"[warn] PDF 页数为 {page_count}（估算高度 {height}px），仍按拼接处理。")
        # PDF 页宽已按 0.75 缩过，这里补回，使输出等于 zoom × CSS 像素
        matrix_scale = zoom / PT_PER_CSS_PX
        matrix = fitz.Matrix(matrix_scale, matrix_scale)
        pixmaps = [page.get_pixmap(matrix=matrix, alpha=False) for page in doc]
        doc.close()

        if len(pixmaps) == 1:
            final = _trim_bottom_padding(pixmaps[0], pad=pad_px)
        else:
            total_h = sum(p.height for p in pixmaps)
            w = pixmaps[0].width
            combined = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, total_h), 0)
            combined.clear_with(255)
            y = 0
            for pix in pixmaps:
                combined.copy(pix, fitz.IRect(0, y, w, y + pix.height))
                y += pix.height
            final = _trim_bottom_padding(combined, pad=pad_px)

        final.save(str(png_path))
        print(
            f"[ok] PNG 截图 → {png_path.name} "
            f"({png_path.stat().st_size // 1024} KB, {final.width}x{final.height}, {zoom:g}x)"
        )
        return True

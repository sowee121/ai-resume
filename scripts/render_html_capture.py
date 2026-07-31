#!/usr/bin/env python3
"""Shared HTML → PNG capture helpers (Chrome print-to-PDF, single tall page)."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

CHROME_PATHS = [
    # 优先独立浏览器，减少与日常 Google Chrome 抢配置/弹崩溃窗
    "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("google-chrome") or "",
]


def find_chrome() -> str | None:
    for p in CHROME_PATHS:
        if p and Path(p).exists():
            return p
    return None


def favicon_link_html(root: Path | None = None, *, name: str = "favicon.svg") -> str:
    """Inline SVG favicon so outbox HTML stays self-contained.

    name:
      - favicon.svg      — review（紫粉橙，对齐诊断页头）
      - favicon-jd.svg    — jd（靛蓝→紫→青，对齐岗位匹配页头高分渐变）
      - favicon-diff.svg — diff（青绿→蓝，对齐对照页头）
    """
    base = root or Path(__file__).resolve().parents[1]
    svg_path = base / "templates" / name
    if not svg_path.exists():
        return ""
    svg = " ".join(svg_path.read_text(encoding="utf-8").split())
    href = "data:image/svg+xml," + quote(svg, safe="")
    return f'<link rel="icon" type="image/svg+xml" href="{href}" />'


def estimate_page_height(html: str) -> int:
    """Estimate required single-page height in CSS px (upper bound, later cropped).

    Prefer one tall page over multi-page stitching — pagination + break-inside
    avoid often causes clipped pairs and fake bottom whitespace.
    """
    n_pair = html.count('class="pair"')
    n_section = html.count('class="section-card"')
    if n_pair:
        note_bonus = html.count('class="pair-note"') * 32
        score_bonus = 140 if "score-strip" in html else 0
        # pair ≈ label + del + add + note；偏松估算，靠底部裁切收掉多余空白
        return min(
            50000,
            max(2200, 320 + score_bonus + n_section * 72 + n_pair * 168 + note_bonus),
        )

    n_hunk = html.count('class="hunk"')
    if n_hunk:
        return min(50000, max(1600, 200 + n_hunk * 130))

    n_diff = html.count('class="diff-item"')
    if n_diff:
        return min(60000, max(2400, 360 + n_diff * 300))

    n_dim = html.count('class="dim-item"')
    n_card = html.count('class="card ')
    n_li = len(re.findall(r"<li[\s>]", html))
    return min(16000, max(2600, 1100 + n_card * 210 + n_dim * 105 + n_li * 46))


def inject_capture_page_size(html: str, height_px: int) -> str:
    # Only enlarge the print page. Do NOT set min-height on body —
    # that stretches the gradient background and creates fake bottom padding.
    style = f"""
<style id="capture-page-size">
  @page {{ size: 750px {height_px}px; margin: 0; }}
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
    """Return (avg_rgb, max_channel_spread) for a horizontal sample of the row."""
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
    """Uniform row close to any known page/body background → empty padding."""
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
    """CSS px padding-bottom on body — used to keep PNG bottom margin consistent."""
    m = re.search(r"body\s*\{[^}]*?padding-bottom:\s*(\d+)px", html, re.S)
    if m:
        return max(0, int(m.group(1)))
    return 14


def _trim_bottom_padding(pix, pad: int = 21):
    """
    Crop trailing page padding, preserving ~body padding-bottom.

    Empty region may be pure white (PDF page) or soft body bg (#f6f8fa etc.),
    so match against several background samples from the bottom of the image.
    """
    backgrounds: list[tuple[int, int, int]] = [
        (255, 255, 255),
        (246, 248, 250),  # diff body
        (238, 242, 255),  # review/jd
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


def html_to_png(html_path: Path, png_path: Path, *, scale: float = 1.5) -> bool:
    """Render local HTML file to a single long PNG, cropped to content."""
    import fitz

    chrome = find_chrome()
    if not chrome:
        print("[warn] 未找到 Chrome，跳过自动截图。可手动在浏览器中打开 HTML 截屏。")
        return False

    raw = html_path.read_text(encoding="utf-8")
    height = estimate_page_height(raw)
    prepared = inject_capture_page_size(raw, height)
    pad_css = _detect_body_padding_bottom(raw)
    pad_px = max(8, int(round(pad_css * scale)))

    png_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        prep_html = Path(td) / "capture.html"
        prep_pdf = Path(td) / "capture.pdf"
        crash_dir = Path(td) / "chrome-crashes"
        crash_dir.mkdir(parents=True, exist_ok=True)
        prep_html.write_text(prepared, encoding="utf-8")
        url = prep_html.resolve().as_uri()

        # 说明：macOS 上给本机 Google Chrome 加 --user-data-dir 临时目录容易卡住；
        # 这里只用独立 crash-dumps-dir + 关闭崩溃上报，减少「意外退出」系统弹窗。
        cmd = [
            chrome,
            "--headless=new",
            f"--crash-dumps-dir={crash_dir}",
            "--disable-crash-reporter",
            "--disable-breakpad",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-sandbox",
            f"--print-to-pdf={prep_pdf}",
            "--no-pdf-header-footer",
            url,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=90)
        except subprocess.TimeoutExpired:
            print("[warn] Chrome 截图超时。可手动在浏览器中打开 HTML 截屏。")
            return False
        except subprocess.CalledProcessError as e:
            cmd_old = [
                chrome,
                "--headless",
                f"--crash-dumps-dir={crash_dir}",
                "--disable-crash-reporter",
                "--disable-breakpad",
                "--disable-gpu",
                "--no-first-run",
                "--no-sandbox",
                f"--print-to-pdf={prep_pdf}",
                "--no-pdf-header-footer",
                url,
            ]
            try:
                subprocess.run(cmd_old, check=True, capture_output=True, timeout=90)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e2:
                print(f"[warn] Chrome 截图失败: {e2}。可手动在浏览器中打开 HTML 截屏。")
                return False

        if not prep_pdf.exists() or prep_pdf.stat().st_size < 100:
            print("[warn] Chrome 未生成有效 PDF。")
            return False

        doc = fitz.open(str(prep_pdf))
        page_count = doc.page_count
        if page_count != 1:
            print(f"[warn] PDF 页数为 {page_count}（估算高度 {height}px），仍按拼接处理。")
        matrix = fitz.Matrix(scale, scale)
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
            f"({png_path.stat().st_size // 1024} KB, {final.width}x{final.height})"
        )
        return True

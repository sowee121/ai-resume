#!/usr/bin/env python3
"""生成 README 用的改动对比预览图：截到首个 .section-card（大模板卡片）底部。

诊断 / 岗位匹配报告在 README 直接用原图，不生成预览裁切。
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib_paths import OUTBOX_DIR, ROOT
from render_html_capture import html_to_png


def trim_to_first_section_card(html: str) -> str:
    """保留页头 + 首个改动大卡片，去掉后续长内容。"""
    m = re.search(
        r"(.*?<div class=\"content\">\s*)"
        r"(<section class=\"section-card\">.*?</section>)",
        html,
        flags=re.DOTALL,
    )
    if not m:
        raise ValueError("未找到 .content / 首个 .section-card，无法裁切预览")
    return m.group(1) + m.group(2) + "\n  </div>\n</body>\n</html>\n"


def make_diff_preview(stem: str) -> Path | None:
    src_html = OUTBOX_DIR / f"{stem}_diff.html"
    dest = OUTBOX_DIR / f"{stem}_diff_preview.png"
    if not src_html.is_file():
        print(f"[skip] 缺少 {src_html.relative_to(ROOT)}")
        return None
    trimmed = trim_to_first_section_card(src_html.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ai-resume-readme-preview-") as td:
        tmp = Path(td) / "preview.html"
        tmp.write_text(trimmed, encoding="utf-8")
        ok = html_to_png(tmp, dest)
    if not ok:
        print(f"[warn] 预览截图失败：{dest.name}")
        return None
    print(f"[ok] README 对比预览 → {dest.relative_to(ROOT)}")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description="生成 README 改动对比预览图（截到首个大卡片）")
    ap.add_argument("--stem", default="张三")
    args = ap.parse_args()
    make_diff_preview(args.stem)


if __name__ == "__main__":
    main()

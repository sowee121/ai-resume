#!/usr/bin/env python3
"""从 outbox 报告长图顶部裁出 README 预览图（固定高度，避免 README 过长）。"""
from __future__ import annotations

import argparse
from pathlib import Path

import fitz

from lib_paths import OUTBOX_DIR, ROOT


def crop_top(src: Path, dest: Path, max_h: int) -> None:
    pix = fitz.Pixmap(str(src))
    if pix.alpha:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    h = min(max_h, pix.height)
    if h < pix.height:
        out = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, pix.width, h), 0)
        out.copy(pix, fitz.IRect(0, 0, pix.width, h))
    else:
        out = pix
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(str(dest))
    print(f"[ok] {src.name} {pix.width}x{pix.height} → {dest.name} {out.width}x{out.height}")


def main() -> None:
    ap = argparse.ArgumentParser(description="裁剪 README 示例预览图")
    ap.add_argument("--stem", default="张三")
    ap.add_argument("--max-height", type=int, default=960, help="预览图最大高度（px）")
    args = ap.parse_args()
    stem = args.stem
    names = [
        f"{stem}_review_report.png",
        f"{stem}_diff.png",
        f"{stem}_jd_report.png",
    ]
    for name in names:
        src = OUTBOX_DIR / name
        if not src.is_file():
            print(f"[skip] 缺少 {src.relative_to(ROOT)}")
            continue
        dest = OUTBOX_DIR / f"{src.stem}_preview.png"
        crop_top(src, dest, args.max_height)


if __name__ == "__main__":
    main()

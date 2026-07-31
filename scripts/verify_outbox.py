#!/usr/bin/env python3
"""Verify outbox deliverables completeness and mutual exclusion rules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib_paths import JSONS_DIR, OUTBOX_DIR  # noqa: E402
from verify_content import verify_stem_content  # noqa: E402

SHARED_CLIENT = ["_review_report.png"]
GENERIC_ONLY_CLIENT = ["_优化版", "_diff.png"]
JD_ONLY_CLIENT = ["_定制版", "_diff_jd.png", "_jd_report.png"]
GENERIC_CLIENT = GENERIC_ONLY_CLIENT + SHARED_CLIENT
JD_CLIENT = JD_ONLY_CLIENT + SHARED_CLIENT

# 内部预览（仍在 outbox）
INTERNAL_PREVIEW_ALWAYS = ["_review_report.html"]
INTERNAL_PREVIEW_GENERIC = ["_diff.html"]
INTERNAL_PREVIEW_JD = ["_jd_report.html", "_diff_jd.html"]

# 中间 JSON（在 jsons/）
INTERNAL_JSON_ALWAYS = ["_segments.json", "_review_report.json"]
INTERNAL_JSON_GENERIC = ["_replacements.json", "_diff_outline.json"]
INTERNAL_JSON_JD = [
    "_replacements_jd.json",
    "_jd_report.json",
    "_diff_outline.json",
]

FORBIDDEN_EXT = {".txt", ".md", ".json"}


def _find(dir_path: Path, stem: str, suffix: str) -> list[Path]:
    if not dir_path.exists():
        return []
    if "." in suffix:
        exact = dir_path / f"{stem}{suffix}"
        return [exact] if exact.exists() else []
    return list(dir_path.glob(f"{stem}{suffix}.*"))


def verify(stem: str, has_jd: bool, outbox: Path | None = None) -> list[str]:
    out = outbox or OUTBOX_DIR
    jsons = JSONS_DIR if out == OUTBOX_DIR else out.parent / "jsons"
    errors: list[str] = []

    expected_client = JD_CLIENT if has_jd else GENERIC_CLIENT
    forbidden_client = GENERIC_ONLY_CLIENT if has_jd else JD_ONLY_CLIENT
    expected_preview = INTERNAL_PREVIEW_ALWAYS + (
        INTERNAL_PREVIEW_JD if has_jd else INTERNAL_PREVIEW_GENERIC
    )
    expected_json = INTERNAL_JSON_ALWAYS + (
        INTERNAL_JSON_JD if has_jd else INTERNAL_JSON_GENERIC
    )

    for suffix in expected_client:
        if not _find(out, stem, suffix):
            errors.append(f"[缺失] 客户文件 outbox/{stem}{suffix}* 不存在")

    for suffix in expected_preview:
        if not _find(out, stem, suffix):
            errors.append(f"[缺失] 内部预览 outbox/{stem}{suffix} 不存在")

    for suffix in expected_json:
        if not _find(jsons, stem, suffix) and not _find(out, stem, suffix):
            errors.append(f"[缺失] 中间 JSON jsons/{stem}{suffix} 不存在")

    for suffix in forbidden_client:
        found = _find(out, stem, suffix)
        if found:
            names = ", ".join(f.name for f in found)
            errors.append(f"[互斥] 不应存在 {names}（当前为{'JD' if has_jd else '通用'}分支）")

    if out.exists():
        for f in out.iterdir():
            if f.stem.startswith(stem) and f.suffix in FORBIDDEN_EXT:
                errors.append(f"[禁止] outbox 不应有 {f.suffix} 文件：{f.name}（JSON 请放 jsons/）")

    root = out.parent if out.name == "outbox" else ROOT
    errors.extend(verify_stem_content(stem, jd=has_jd, root=root))

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify outbox deliverables")
    parser.add_argument("--stem", required=True, help="简历 stem（无扩展名）")
    parser.add_argument("--jd", action="store_true", help="预期为 JD 分支")
    parser.add_argument("--outbox", default=str(OUTBOX_DIR))
    args = parser.parse_args()

    errs = verify(args.stem, has_jd=args.jd, outbox=Path(args.outbox))
    if errs:
        print(f"[FAIL] {args.stem} 验收未通过：")
        for e in errs:
            print(f"  {e}")
        raise SystemExit(1)
    branch = "JD 版" if args.jd else "通用版"
    print(f"[PASS] {args.stem}（{branch}）验收通过")


if __name__ == "__main__":
    main()

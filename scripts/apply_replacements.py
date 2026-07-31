#!/usr/bin/env python3
"""Apply replacements JSON back to DOCX (style-preserving) or PDF (best-effort)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib_docx import apply_docx_replacements  # noqa: E402
from lib_paths import OUTBOX_DIR, resolve_json  # noqa: E402
from lib_pdf import apply_pdf_replacements  # noqa: E402
from verify_content import verify_replacements_against_segments  # noqa: E402


def load_replacements(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "replacements" in data:
        data = data["replacements"]
    if not isinstance(data, list):
        raise SystemExit("replacements 必须是 JSON 数组，或含 replacements 字段的对象")
    return data


def build_mapping(items: list) -> dict:
    mapping = {}
    for item in items:
        sid = item.get("id")
        if not sid:
            continue
        rewritten = item.get("rewritten", item.get("original", ""))
        mapping[sid] = rewritten
    return mapping


def output_stem(stem: str, jd: bool) -> str:
    return f"{stem}_定制版" if jd else f"{stem}_优化版"


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply replacements to DOCX/PDF")
    parser.add_argument("--input", "-i", required=True, help="原始 inbox 文件 (.docx/.pdf)")
    parser.add_argument("--replacements", "-r", required=True, help="replacements JSON")
    parser.add_argument("--segments", "-s", help="segments JSON（PDF 回写需要；DOCX 用于串改校验）")
    parser.add_argument("--jd", action="store_true", help="JD 定制版（输出 _定制版.*）")
    parser.add_argument("--out-dir", default=str(OUTBOX_DIR))
    parser.add_argument(
        "--skip-content-check",
        action="store_true",
        help="跳过 replacements↔segments 串改校验（不推荐）",
    )
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f"文件不存在: {src}")

    rep_path = Path(args.replacements)
    items = load_replacements(rep_path)
    mapping = build_mapping(items)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    suffix = src.suffix.lower()
    out_base = output_stem(stem, args.jd)

    if args.segments:
        segments_path = Path(args.segments)
    else:
        segments_path = resolve_json(stem, "_segments.json") or (out_dir / f"{stem}_segments.json")
    if not args.skip_content_check and segments_path.exists():
        errs = verify_replacements_against_segments(rep_path, segments_path)
        if errs:
            print("[FAIL] replacements 内容校验未通过，已拒绝回写：")
            for e in errs:
                print(f"  {e}")
            raise SystemExit(1)

    if suffix == ".docx":
        dst = out_dir / f"{out_base}.docx"
        applied = apply_docx_replacements(str(src), str(dst), mapping)
        print(f"[ok] DOCX 保样式回写 → {dst.name} (applied={applied})")
    elif suffix == ".pdf":
        if not segments_path.exists():
            raise SystemExit(f"PDF 回写需要 segments JSON: {segments_path}")
        seg_payload = json.loads(segments_path.read_text(encoding="utf-8"))
        segments = seg_payload.get("segments", [])
        dst = out_dir / f"{out_base}.pdf"
        try:
            applied = apply_pdf_replacements(str(src), str(dst), mapping, segments)
            print(f"[ok] PDF 尽力回写 → {dst.name} (applied={applied})，请人工检查版式")
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"PDF 回写失败: {exc}。请改用可编辑的 Word 原件。") from exc
    else:
        raise SystemExit(f"不支持的文件类型: {suffix}")


if __name__ == "__main__":
    main()

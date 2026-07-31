#!/usr/bin/env python3
"""Extract editable text segments from inbox DOCX or PDF into jsons/ JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib_docx import extract_docx_segments, segments_to_dicts as docx_dicts  # noqa: E402
from lib_paths import JSONS_DIR, ensure_jsons  # noqa: E402
from lib_pdf import extract_pdf_segments, segments_to_dicts as pdf_dicts  # noqa: E402

SUPPORTED = {".docx", ".pdf"}


def stem_key(path: Path) -> str:
    return path.stem


def extract(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        segs = extract_docx_segments(str(path))
        data = docx_dicts(segs)
        source = "docx"
    elif suffix == ".pdf":
        segs = extract_pdf_segments(str(path))
        data = pdf_dicts(segs)
        source = "pdf"
    else:
        raise SystemExit(f"不支持的文件类型: {suffix}（仅支持 .docx / .pdf）")

    editable = [s for s in data if s.get("editable")]
    return {
        "source_file": str(path),
        "source_type": source,
        "segment_count": len(data),
        "editable_count": len(editable),
        "segments": data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract resume segments from DOCX/PDF")
    parser.add_argument("--input", "-i", help="单个文件路径")
    parser.add_argument("--batch", help="目录批处理（扫描 .docx/.pdf）")
    parser.add_argument("--out-dir", default=str(JSONS_DIR), help="JSON 输出目录（默认 jsons/）")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if out_dir.resolve() == JSONS_DIR.resolve():
        ensure_jsons()
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    inputs: list[Path] = []
    if args.batch:
        batch = Path(args.batch)
        inputs = sorted(
            p for p in batch.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED
        )
        if not inputs:
            raise SystemExit(f"目录中没有 .docx/.pdf: {batch}")
    elif args.input:
        inputs = [Path(args.input)]
    else:
        raise SystemExit("请指定 --input 或 --batch")

    for path in inputs:
        if not path.exists():
            raise SystemExit(f"文件不存在: {path}")
        payload = extract(path)
        out_path = out_dir / f"{stem_key(path)}_segments.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[ok] {path.name} → {out_path.parent.name}/{out_path.name} "
            f"(segments={payload['segment_count']}, editable={payload['editable_count']}, type={payload['source_type']})"
        )


if __name__ == "__main__":
    main()

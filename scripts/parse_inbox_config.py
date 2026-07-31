#!/usr/bin/env python3
"""Parse inbox/<stem>.md into JD, requirements, and dimension switches."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JD_HEADERS = ("职位描述（JD）", "职位描述", "JD")
REQ_HEADERS = ("额外要求", "其他要求")
DIM_HEADERS = ("六维优化", "六维", "优化维度")

DEFAULT_DIMENSIONS: dict[str, bool] = {
    "ats_keywords": True,
    "structure": True,
    "quantification": True,
    "skill_matching": True,
    "language": True,
    "highlights": True,
}

_BOOL = {"true": True, "yes": True, "1": True, "false": False, "no": False, "0": False}
_DIM_LINE = re.compile(
    r"^\s*[-*]?\s*(ats_keywords|structure|quantification|skill_matching|language|highlights)\s*:\s*(\w+)",
    re.I,
)


def _normalize_header(line: str) -> str:
    m = re.match(r"^##\s+(.+?)\s*$", line.strip())
    return m.group(1).strip() if m else ""


def _parse_dimensions(lines: list[str]) -> dict[str, bool]:
    dims = dict(DEFAULT_DIMENSIONS)
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("```") or stripped.startswith("（") or stripped.startswith("("):
            continue
        m = _DIM_LINE.match(stripped)
        if not m:
            continue
        key = m.group(1).lower()
        val = _BOOL.get(m.group(2).lower())
        if val is not None:
            dims[key] = val
    return dims


def parse_md(text: str) -> dict:
    sections: dict[str, list[str]] = {"jd": [], "requirements": [], "dimensions": []}
    current: str | None = None

    for line in text.splitlines():
        header = _normalize_header(line)
        if header:
            if header in JD_HEADERS:
                current = "jd"
                continue
            if header in REQ_HEADERS:
                current = "requirements"
                continue
            if header in DIM_HEADERS:
                current = "dimensions"
                continue
            current = None
            continue
        if current:
            sections[current].append(line)

    return {
        "jd": "\n".join(sections["jd"]).strip(),
        "requirements": "\n".join(sections["requirements"]).strip(),
        "dimensions": _parse_dimensions(sections["dimensions"]),
    }


def load_config(stem: str, inbox_dir: Path | None = None) -> dict:
    inbox = inbox_dir or (ROOT / "inbox")
    md_path = inbox / f"{stem}.md"
    if not md_path.exists():
        return {
            "jd": "",
            "requirements": "",
            "has_jd": False,
            "dimensions": dict(DEFAULT_DIMENSIONS),
            "config_file": None,
        }

    parsed = parse_md(md_path.read_text(encoding="utf-8"))
    jd = parsed["jd"]
    return {
        "jd": jd,
        "requirements": parsed["requirements"],
        "has_jd": bool(jd),
        "dimensions": parsed["dimensions"],
        "config_file": str(md_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse inbox/<stem>.md config")
    parser.add_argument("--stem", required=True, help="简历文件名（无扩展名）")
    parser.add_argument("--inbox", default=str(ROOT / "inbox"))
    args = parser.parse_args()

    result = load_config(args.stem, Path(args.inbox))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

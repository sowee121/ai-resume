#!/usr/bin/env python3
"""Parse inbox/<stem>.md into JD and extra requirements sections."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JD_HEADERS = ("职位描述（JD）", "职位描述", "JD")
REQ_HEADERS = ("额外要求", "其他要求")


def _normalize_header(line: str) -> str:
    m = re.match(r"^##\s+(.+?)\s*$", line.strip())
    return m.group(1).strip() if m else ""


def parse_md(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"jd": [], "requirements": []}
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
            current = None
            continue
        if current:
            sections[current].append(line)

    return {
        "jd": "\n".join(sections["jd"]).strip(),
        "requirements": "\n".join(sections["requirements"]).strip(),
    }


def load_config(stem: str, inbox_dir: Path | None = None) -> dict:
    inbox = inbox_dir or (ROOT / "inbox")
    md_path = inbox / f"{stem}.md"
    if not md_path.exists():
        return {"jd": "", "requirements": "", "has_jd": False, "config_file": None}

    parsed = parse_md(md_path.read_text(encoding="utf-8"))
    jd = parsed["jd"]
    return {
        "jd": jd,
        "requirements": parsed["requirements"],
        "has_jd": bool(jd),
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

#!/usr/bin/env python3
"""Render replacements JSON to a client-facing diff PDF (legacy; prefer render_diff_report.py)."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]

PAGE_W, PAGE_H = 595, 842  # A4 pt
MARGIN = 50
FONT_SIZE = 10


def load_replacements(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "replacements" in data:
        data = data["replacements"]
    if not isinstance(data, list):
        raise SystemExit("replacements 必须是 JSON 数组，或含 replacements 字段的对象")
    return data


def _pick_cjk_font() -> str | None:
    for path in (
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ):
        if Path(path).exists():
            return path
    return None


def _wrap(text: str, width: int = 68) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(para, width=width) or [""])
    return lines


class PdfWriter:
    def __init__(
        self,
        title: str,
        source_filename: str,
        source_type: str,
        total: int,
        changed: int,
    ) -> None:
        self.doc = fitz.open()
        try:
            self.font = fitz.Font("china-s")
        except Exception:  # noqa: BLE001
            fontfile = _pick_cjk_font()
            self.font = fitz.Font(fontfile=fontfile) if fontfile else fitz.Font("helv")
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.tw: fitz.TextWriter | None = None
        self.y = MARGIN
        self._new_writer()
        self._write_line(title, size=16)
        self._write_line(
            f"{source_filename} · 改写 {changed}/{total} 条",
            size=9,
            color=(0.4, 0.4, 0.4),
        )
        self._gap(8)
        if source_type == "pdf":
            self._write_line(
                "PDF 回写为尽力而为，输出前请人工核对版式。",
                size=9,
                color=(0.7, 0.5, 0.1),
            )
            self._gap(8)

    def _new_writer(self) -> None:
        if self.tw is not None:
            self.tw.write_text(self.page)
        self.tw = fitz.TextWriter(self.page.rect)

    def _ensure_space(self, needed: float = 20) -> None:
        if self.y + needed > PAGE_H - MARGIN:
            self._new_writer()
            self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
            self.tw = fitz.TextWriter(self.page.rect)
            self.y = MARGIN

    def _gap(self, pts: float) -> None:
        self.y += pts

    def _write_line(self, text: str, size: int = FONT_SIZE, color=(0, 0, 0)) -> None:
        self._ensure_space(size + 8)
        assert self.tw is not None
        self.tw.append((MARGIN, self.y + size), text, font=self.font, fontsize=size)
        self.y += size + 8

    def write_item(self, sid: str, original: str, rewritten: str) -> None:
        self._gap(12)
        self._write_line(sid, size=8)
        self._write_line("原文", size=10)
        for line in _wrap(original):
            self._write_line(line, size=FONT_SIZE)
        self._gap(4)
        self._write_line("改写", size=10)
        for line in _wrap(rewritten):
            self._write_line(line, size=FONT_SIZE)

    def save(self, path: Path) -> None:
        if self.tw is not None:
            self.tw.write_text(self.page)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.subset_fonts()
        self.doc.save(str(path), garbage=4, deflate=True)
        self.doc.close()


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lib_source import (  # noqa: E402
        resolve_source_filename,
        source_type_from_filename,
        stem_from_outbox_name,
    )

    parser = argparse.ArgumentParser(description="Render diff PDF from replacements JSON")
    parser.add_argument("--replacements", "-r", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--source-file", help="原稿文件名（如 张三.docx）")
    parser.add_argument("--source-type", default=None, choices=["docx", "pdf"])
    parser.add_argument("--title", default="简历改动对比")
    args = parser.parse_args()

    rep = Path(args.replacements)
    items = load_replacements(rep)
    changed = [i for i in items if i.get("original") != i.get("rewritten")]
    stem = stem_from_outbox_name(rep.name, "_replacements_jd", "_replacements")
    source_filename = resolve_source_filename(
        stem,
        root=ROOT,
        explicit=args.source_file,
        source_type=args.source_type,
    )
    source_type = source_type_from_filename(source_filename, fallback=args.source_type or "docx")
    writer = PdfWriter(args.title, source_filename, source_type, len(items), len(changed))
    for item in changed:
        writer.write_item(
            str(item.get("id", "")),
            item.get("original", ""),
            item.get("rewritten", ""),
        )
    out = Path(args.output)
    writer.save(out)
    size_kb = max(1, out.stat().st_size // 1024)
    print(f"[ok] 对比 PDF → {out.name} ({size_kb} KB)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Resolve inbox resume source filename for report subtitles."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stem_from_outbox_name(name: str, *suffixes: str) -> str:
    stem = Path(name).stem
    for suffix in suffixes:
        if stem.endswith(suffix):
            return stem[: -len(suffix)].strip() or "客户"
    return stem.strip() or "客户"


def resolve_segments_json(stem: str, root: Path | None = None) -> Path | None:
    """Prefer jsons/, fall back to legacy outbox/."""
    base = root or ROOT
    primary = base / "jsons" / f"{stem}_segments.json"
    if primary.exists():
        return primary
    legacy = base / "outbox" / f"{stem}_segments.json"
    if legacy.exists():
        return legacy
    return None


def resolve_source_filename(
    stem: str,
    *,
    root: Path | None = None,
    explicit: str | None = None,
    source_type: str | None = None,
) -> str:
    """Return display name like `吴卫.docx` (basename only)."""
    if explicit:
        return Path(explicit).name

    base = root or ROOT
    seg = resolve_segments_json(stem, base)
    if seg is not None:
        try:
            data = json.loads(seg.read_text(encoding="utf-8"))
            source_file = data.get("source_file")
            if source_file:
                return Path(str(source_file)).name
            st = str(data.get("source_type") or "").lower()
            if st in ("docx", "pdf"):
                return f"{stem}.{st}"
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    inbox = base / "inbox"
    for ext in (".docx", ".pdf"):
        path = inbox / f"{stem}{ext}"
        if path.exists():
            return path.name

    st = (source_type or "docx").strip().lower() or "docx"
    if st not in ("docx", "pdf"):
        st = "docx"
    return f"{stem}.{st}"


def source_type_from_filename(filename: str, fallback: str = "docx") -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in ("docx", "pdf"):
        return ext
    return fallback if fallback in ("docx", "pdf") else "docx"

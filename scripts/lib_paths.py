#!/usr/bin/env python3
"""Shared inbox / outbox / jsons path helpers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX_DIR = ROOT / "inbox"
OUTBOX_DIR = ROOT / "outbox"
JSONS_DIR = ROOT / "jsons"


def ensure_jsons() -> Path:
    JSONS_DIR.mkdir(parents=True, exist_ok=True)
    return JSONS_DIR


def ensure_outbox() -> Path:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    return OUTBOX_DIR


def json_path(stem: str, suffix: str) -> Path:
    """Internal JSON under jsons/, e.g. json_path('吴卫', '_segments.json')."""
    if not suffix.startswith("_"):
        suffix = "_" + suffix
    if not suffix.endswith(".json"):
        suffix = suffix + ".json"
    return JSONS_DIR / f"{stem}{suffix}"


def outbox_path(stem: str, name: str) -> Path:
    """Customer / preview artifact under outbox/."""
    return OUTBOX_DIR / f"{stem}{name}" if name.startswith("_") else OUTBOX_DIR / name


def resolve_json(stem: str, suffix: str) -> Path | None:
    """Prefer jsons/, fall back to legacy outbox/ for one release."""
    primary = json_path(stem, suffix)
    if primary.exists():
        return primary
    legacy = OUTBOX_DIR / primary.name
    if legacy.exists():
        return legacy
    return None

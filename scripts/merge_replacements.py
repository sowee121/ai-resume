#!/usr/bin/env python3
"""Scaffold / merge replacements with locked originals — root fix for id/note drift.

Why mismatches happen
---------------------
Hand-editing or regenerating a full replacements JSON often reshuffles
`rewritten` / `note` onto the wrong `id`. Downstream apply then silently
overwrites the wrong paragraph.

Root rule
---------
1. Scaffold from segments: id + original are frozen; rewritten starts as original.
2. Model/agent may only change rewritten + note.
3. merge_replacements.py re-binds any LLM output onto the scaffold by id
   (fallback: by original text), and always restores original from segments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_content import (  # noqa: E402
    verify_notes_relevance,
    verify_replacements_against_segments,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _seg_items(segments_path: Path) -> list[dict]:
    payload = _load(segments_path)
    segs = payload.get("segments", payload if isinstance(payload, list) else [])
    if not isinstance(segs, list):
        raise SystemExit(f"无效 segments: {segments_path}")
    return segs


def scaffold_from_segments(segments_path: Path, *, editable_only: bool = True) -> list[dict]:
    """Build locked replacements: original == segment text; rewritten initially same."""
    rows: list[dict] = []
    for seg in _seg_items(segments_path):
        if editable_only and not seg.get("editable", True):
            continue
        sid = str(seg.get("id", "")).strip()
        text = str(seg.get("text", ""))
        if not sid:
            continue
        rows.append(
            {
                "id": sid,
                "original": text,
                "rewritten": text,
                "note": "",
            }
        )
    return rows


def merge_onto_scaffold(
    scaffold: list[dict],
    patch_items: list[dict],
) -> tuple[list[dict], list[str]]:
    """
    Apply patch rewritten/note onto scaffold.

    Match order:
    1) same id AND patch.original == scaffold.original (best)
    2) same id (still take rewritten/note, keep scaffold.original)
    3) patch.original == scaffold.original (id drifted)
    Never trust patch.original over scaffold.
    """
    warnings: list[str] = []
    by_id = {str(p.get("id", "")).strip(): p for p in patch_items if p.get("id")}
    by_original: dict[str, dict] = {}
    for p in patch_items:
        o = str(p.get("original", ""))
        if o and o not in by_original:
            by_original[o] = p

    out: list[dict] = []
    used_patch_ids: set[str] = set()

    for row in scaffold:
        sid = row["id"]
        locked_original = row["original"]
        patch = None
        how = ""

        cand = by_id.get(sid)
        if cand is not None:
            po = str(cand.get("original", ""))
            if po == locked_original or not po:
                patch, how = cand, "id"
            else:
                warnings.append(
                    f"[warn] {sid} patch.original 与骨架不一致，改按 original 文本匹配 "
                    f"（patch={po[:20]!r} / locked={locked_original[:20]!r}）"
                )

        if patch is None and locked_original in by_original:
            patch, how = by_original[locked_original], "original"
            pid = str(patch.get("id", ""))
            if pid and pid != sid:
                warnings.append(
                    f"[warn] 条目 {sid} 通过 original 匹配到 patch.id={pid}（id 已漂移，已纠正）"
                )

        rewritten = locked_original
        note = ""
        if patch is not None:
            rewritten = str(patch.get("rewritten", locked_original))
            note = str(patch.get("note") or "")
            used_patch_ids.add(str(patch.get("id", "")).strip())
            if how == "id" and str(patch.get("original", "")) not in ("", locked_original):
                # already warned
                pass

        if rewritten == locked_original:
            note = ""

        out.append(
            {
                "id": sid,
                "original": locked_original,
                "rewritten": rewritten,
                "note": note,
            }
        )

    for pid, p in by_id.items():
        if pid and pid not in used_patch_ids:
            # unused patch — might be non-editable id or garbage
            if str(p.get("original", "")) != str(p.get("rewritten", "")):
                warnings.append(f"[warn] patch 未合并（无对应骨架）：{pid}")

    return out, warnings


def set_one(
    rows: list[dict],
    *,
    sid: str,
    rewritten: str,
    note: str,
) -> list[dict]:
    found = False
    out = []
    for row in rows:
        if row["id"] != sid:
            out.append(row)
            continue
        found = True
        new_note = note
        if rewritten == row["original"]:
            new_note = ""
        out.append(
            {
                "id": sid,
                "original": row["original"],
                "rewritten": rewritten,
                "note": new_note,
            }
        )
    if not found:
        raise SystemExit(f"骨架中不存在 id={sid}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold/merge replacements with originals locked to segments"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sc = sub.add_parser("scaffold", help="从 segments 生成锁定 original 的 replacements 骨架")
    p_sc.add_argument("--segments", "-s", required=True)
    p_sc.add_argument("--output", "-o", required=True)
    p_sc.add_argument(
        "--all",
        action="store_true",
        help="包含不可编辑段落（默认只 editable）",
    )

    p_mg = sub.add_parser(
        "merge",
        help="把模型/人工 patch 合并进骨架：只采纳 rewritten/note，original 始终来自 segments",
    )
    p_mg.add_argument("--segments", "-s", required=True)
    p_mg.add_argument("--patch", "-p", required=True, help="模型或人工产出的 replacements JSON")
    p_mg.add_argument("--output", "-o", required=True)
    p_mg.add_argument("--all", action="store_true")

    p_set = sub.add_parser("set", help="安全改单条（禁止手改错 id）")
    p_set.add_argument("--replacements", "-r", required=True)
    p_set.add_argument("--segments", "-s", required=True)
    p_set.add_argument("--id", required=True)
    p_set.add_argument("--rewritten", required=True)
    p_set.add_argument("--note", default="")
    p_set.add_argument("--output", "-o", help="默认覆盖 --replacements")

    args = parser.parse_args()

    if args.cmd == "scaffold":
        rows = scaffold_from_segments(Path(args.segments), editable_only=not args.all)
        out = Path(args.output)
        _dump(out, rows)
        print(f"[ok] scaffold → {out.name} ({len(rows)} 条，original 已锁定)")
        return

    if args.cmd == "merge":
        scaffold = scaffold_from_segments(Path(args.segments), editable_only=not args.all)
        patch_data = _load(Path(args.patch))
        if isinstance(patch_data, dict) and "replacements" in patch_data:
            patch_data = patch_data["replacements"]
        if not isinstance(patch_data, list):
            raise SystemExit("patch 必须是 replacements 数组")
        merged, warnings = merge_onto_scaffold(scaffold, patch_data)
        for w in warnings:
            print(w)

        out = Path(args.output)
        _dump(out, merged)
        errs = verify_notes_relevance(merged)
        errs += verify_replacements_against_segments(out, Path(args.segments))
        if errs:
            print(f"[FAIL] merge 后校验失败（{len(errs)}）：")
            for e in errs:
                print(f"  {e}")
            raise SystemExit(1)
        print(f"[ok] merge → {out.name} ({len(merged)} 条，original 已从 segments 锁定)")
        return

    if args.cmd == "set":
        rep_path = Path(args.replacements)
        rows = _load(rep_path)
        if isinstance(rows, dict) and "replacements" in rows:
            rows = rows["replacements"]
        # Re-lock originals from segments first
        scaffold = scaffold_from_segments(Path(args.segments), editable_only=True)
        merged, _ = merge_onto_scaffold(scaffold, rows)
        merged = set_one(
            merged,
            sid=args.id,
            rewritten=args.rewritten,
            note=args.note,
        )
        out = Path(args.output) if args.output else rep_path
        _dump(out, merged)
        errs = verify_replacements_against_segments(out, Path(args.segments))
        errs += verify_notes_relevance(merged)
        if errs:
            print(f"[FAIL] set 后校验失败（{len(errs)}）：")
            for e in errs:
                print(f"  {e}")
            raise SystemExit(1)
        print(f"[ok] set {args.id} → {out.name}")
        return

    raise SystemExit(f"未知命令: {args.cmd}")


if __name__ == "__main__":
    main()

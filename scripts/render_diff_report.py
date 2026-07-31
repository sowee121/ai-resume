#!/usr/bin/env python3
"""Render replacements JSON → hierarchical GitHub-style diff HTML (+ PNG).

Hierarchy MUST come from LLM outline `_diff_outline.json`
(prompt: prompts/diff_outline_zh.txt). Rule-based code is only a last-resort
fallback when outline is missing — keep it minimal on purpose.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "diff_report.html"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_paths import ensure_outbox  # noqa: E402
from lib_source import (  # noqa: E402
    resolve_source_filename,
    source_type_from_filename,
    stem_from_outbox_name,
)
from render_html_capture import favicon_link_html, html_to_png  # noqa: E402

LABEL_DUTY = "职责描述"

DIM_SHORT = {
    "ATS 关键词": "ATS",
    "结构优化": "结构",
    "量化表述": "量化",
    "技能匹配": "技能",
    "语言表达": "表达",
    "亮点提炼": "亮点",
}


def load_replacements(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "replacements" in data:
        data = data["replacements"]
    if not isinstance(data, list):
        raise SystemExit("replacements 必须是 JSON 数组，或含 replacements 字段的对象")
    return data


def load_outline(path: Path | None) -> dict[str, dict]:
    """Load LLM outline → id → {section, subsection, label}."""
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return {}
    meta: dict[str, dict] = {}
    for it in items:
        sid = str(it.get("id", "")).strip()
        if not sid:
            continue
        section = str(it.get("section") or "").strip() or "其他"
        meta[sid] = {
            "section": section,
            "subsection": str(it.get("subsection") or "").strip(),
            "label": str(it.get("label") or LABEL_DUTY).strip() or LABEL_DUTY,
        }
    return meta


def fallback_meta(changed: list[dict]) -> dict[str, dict]:
    """Minimal fallback only — flat list under 其他. Do NOT invent taxonomy with regex."""
    return {
        str(item.get("id", "")).strip(): {
            "section": "其他",
            "subsection": "",
            "label": LABEL_DUTY,
        }
        for item in changed
        if str(item.get("id", "")).strip()
    }


def _number_duplicate_labels(pairs: list[dict]) -> None:
    """同标签多项时全部编号：职责描述 1 / 2 / 3（单项不加数字）。"""
    counts: dict[str, int] = {}
    for pair in pairs:
        base = pair["label"]
        counts[base] = counts.get(base, 0) + 1
    seen: dict[str, int] = {}
    for pair in pairs:
        base = pair["label"]
        if counts[base] <= 1:
            continue
        seen[base] = seen.get(base, 0) + 1
        pair["label"] = f"{base} {seen[base]}"


def group_changes(changed: list[dict], seg_meta: dict[str, dict]) -> OrderedDict:
    tree: OrderedDict = OrderedDict()
    for item in changed:
        sid = str(item.get("id", ""))
        info = seg_meta.get(sid) or {
            "section": "其他",
            "subsection": "",
            "label": LABEL_DUTY,
        }
        section = str(info.get("section") or "其他")
        subsection = str(info.get("subsection") or "")
        label = str(info.get("label") or LABEL_DUTY)

        if section not in tree:
            tree[section] = OrderedDict()
        if subsection not in tree[section]:
            tree[section][subsection] = []

        tree[section][subsection].append(
            {
                "label": label,
                "original": item.get("original", ""),
                "rewritten": item.get("rewritten", ""),
                "note": str(item.get("note") or "").strip(),
            }
        )

    for subs in tree.values():
        for pairs in subs.values():
            _number_duplicate_labels(pairs)
    return tree


def _pair_html(pair: dict) -> str:
    note = str(pair.get("note") or "").strip()
    note_html = ""
    if note:
        note_html = (
            f'<div class="pair-note">'
            f'<span class="pair-note-label">改动说明：</span>'
            f"{html.escape(note)}"
            f"</div>"
        )
    return f"""
      <div class="pair">
        <div class="pair-label">{html.escape(pair["label"])}</div>
        <div class="line line-del"><span class="mark">-</span><span>{html.escape(pair["original"])}</span></div>
        <div class="line line-add"><span class="mark">+</span><span>{html.escape(pair["rewritten"])}</span></div>
        {note_html}
      </div>"""


def _tree_html(tree: OrderedDict) -> str:
    blocks: list[str] = []
    for section, subs in tree.items():
        count = sum(len(pairs) for pairs in subs.values())
        body_parts: list[str] = []
        for subsection, pairs in subs.items():
            if subsection:
                body_parts.append(
                    f'<div class="subsection"><div class="subsection-head">{html.escape(subsection)}</div>'
                )
                body_parts.extend(_pair_html(p) for p in pairs)
                body_parts.append("</div>")
            else:
                body_parts.append('<div class="subsection">')
                body_parts.extend(_pair_html(p) for p in pairs)
                body_parts.append("</div>")
        blocks.append(
            f"""
    <section class="section-card">
      <div class="section-head">
        <div class="section-title">{html.escape(section)}</div>
        <div class="section-count">{count} 处改动</div>
      </div>
      {"".join(body_parts)}
    </section>"""
        )
    return "\n".join(blocks)


def resolve_outline_path(rep: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    name = rep.name
    for old in ("_replacements_jd.json", "_replacements.json"):
        if name.endswith(old):
            return rep.with_name(name.replace(old, "_diff_outline.json"))
    stem = rep.stem.replace("_replacements_jd", "").replace("_replacements", "")
    return rep.with_name(stem + "_diff_outline.json")


def resolve_review_path(rep: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    name = rep.name
    for old in ("_replacements_jd.json", "_replacements.json"):
        if name.endswith(old):
            return rep.with_name(name.replace(old, "_review_report.json"))
    stem = rep.stem.replace("_replacements_jd", "").replace("_replacements", "")
    return rep.with_name(stem + "_review_report.json")


def _fmt_delta(delta: int) -> tuple[str, str]:
    """Return (display, css_extra_class)."""
    if delta > 0:
        return f"+{delta}", ""
    if delta < 0:
        return str(delta), ""
    return "0", " flat"


def _read_score(value, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def _score_panel_html(review: dict | None) -> str:
    if not review:
        return ""
    score = _read_score(review.get("score"))
    if score is None:
        return ""
    before = _read_score(review.get("score_before"), default=None)

    if before is not None:
        delta = score - before
        delta_txt, delta_cls = _fmt_delta(delta)
        score_main = (
            f'<div class="score-compare">'
            f'<span class="score-before">{before}</span>'
            f'<span class="score-arrow" aria-hidden="true">→</span>'
            f'<span class="score-now">{score}</span>'
            f'<span class="score-unit">分</span>'
            f'<span class="score-delta{delta_cls}">{delta_txt}</span>'
            f"</div>"
        )
    else:
        score_main = (
            f'<div class="score-main">'
            f'<span class="score-now">{score}</span>'
            f'<span class="score-unit">分</span>'
            f"</div>"
        )

    dims = review.get("dimensions") or []
    dim_parts: list[str] = []
    for dim in dims[:6]:
        name = str(dim.get("name", "")).strip()
        short = DIM_SHORT.get(name, name[:4] or "维度")
        ds = _read_score(dim.get("score"), 0) or 0
        db = _read_score(dim.get("score_before"), default=None)
        if db is not None and db != ds:
            vals = (
                f'<span class="b">{db}</span>'
                f'<span class="arr">→</span>'
                f'<span class="s">{ds}</span>'
            )
        else:
            vals = f'<span class="s">{ds}</span>'
        dim_parts.append(
            f'<div class="dim-chip">'
            f'<span class="n">{html.escape(short)}</span>'
            f'<span class="vals">{vals}</span>'
            f"</div>"
        )
    dims_html = "".join(dim_parts)
    if not dims_html:
        dims_html = '<div class="dim-chip"><span class="n">暂无六维</span></div>'

    tags = [str(t).strip() for t in (review.get("tags") or []) if str(t).strip()]
    tags_html = "".join(
        f'<span class="score-tag">{html.escape(t)}</span>' for t in tags[:6]
    )
    tags_block = f'<div class="score-tags">{tags_html}</div>' if tags_html else ""

    return f"""
    <div class="score-strip">
      <div class="score-top">
        <div class="score-main-wrap">
          <div class="score-kicker">综合评分</div>
          {score_main}
        </div>
        <div class="score-dims">{dims_html}</div>
      </div>
      {tags_block}
    </div>"""


def build_html(
    items: list,
    *,
    title: str,
    source_filename: str,
    source_type: str,
    outline_meta: dict[str, dict],
    structure_note: str,
    review: dict | None = None,
) -> str:
    changed = [i for i in items if i.get("original") != i.get("rewritten")]
    seg_meta = outline_meta if outline_meta else fallback_meta(changed)
    tree = group_changes(changed, seg_meta)

    tpl = TEMPLATE.read_text(encoding="utf-8")
    source_name = (source_filename or "").strip() or f"resume.{source_type}"
    meta = (
        f"{source_name} · 共优化 {len(changed)} 处重点表述"
        f" · {len(tree)} 个模块"
    )
    pdf_note = ""
    if source_type == "pdf":
        pdf_note = (
            '<div class="hero-note">PDF 回写为尽力而为，交付前请人工核对版式。</div>'
        )

    result = tpl
    result = result.replace("{{favicon_link}}", favicon_link_html(ROOT, name="favicon-diff.svg"))
    result = result.replace("{{title}}", html.escape(title))
    result = result.replace("{{meta}}", html.escape(meta))
    result = result.replace("{{pdf_note}}", pdf_note)
    result = result.replace("{{score_panel}}", _score_panel_html(review))
    result = result.replace("{{items}}", _tree_html(tree))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Render hierarchical diff report → HTML + PNG")
    parser.add_argument("--replacements", "-r", required=True)
    parser.add_argument(
        "--outline",
        help="LLM 结构大纲 JSON（必需；默认同 stem _diff_outline.json）",
    )
    parser.add_argument(
        "--review",
        help="优化诊断 JSON（默认同 stem _review_report.json；用于顶部评分卡）",
    )
    parser.add_argument("--segments", "-s", help="已废弃，层级以 --outline 为准")
    parser.add_argument("--output", "-o", help="输出 HTML 路径")
    parser.add_argument(
        "--source-file",
        help="原稿文件名（如 吴卫.docx；默认从 segments/inbox 推断）",
    )
    parser.add_argument("--source-type", default=None, choices=["docx", "pdf"])
    parser.add_argument("--title", default="简历改动对比")
    parser.add_argument("--no-png", action="store_true")
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="允许在缺少 outline 时用「其他」扁平回退（默认缺少 outline 则报错）",
    )
    args = parser.parse_args()

    rep = Path(args.replacements)
    stem = stem_from_outbox_name(rep.name, "_replacements_jd", "_replacements")
    if args.output:
        html_path = Path(args.output)
    elif rep.name.endswith("_replacements_jd.json"):
        html_path = ensure_outbox() / f"{stem}_diff_jd.html"
    elif rep.name.endswith("_replacements.json"):
        html_path = ensure_outbox() / f"{stem}_diff.html"
    else:
        html_path = ensure_outbox() / f"{rep.stem}.html"

    outline_path = resolve_outline_path(rep, args.outline)
    outline_meta = load_outline(outline_path)

    if not outline_meta and not args.allow_fallback:
        raise SystemExit(
            f"缺少模型大纲：{outline_path.name}\n"
            f"请先用 prompts/diff_outline_zh.txt + segments 生成 _diff_outline.json，"
            f"或临时加 --allow-fallback（仅扁平「其他」）。"
        )

    review_path = resolve_review_path(rep, args.review)
    review = None
    if review_path and review_path.exists():
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if not isinstance(review, dict):
            review = None

    source_filename = resolve_source_filename(
        stem,
        root=ROOT,
        explicit=args.source_file,
        source_type=args.source_type,
    )
    source_type = source_type_from_filename(source_filename, fallback=args.source_type or "docx")

    items = load_replacements(rep)
    structure_note = "结构：模型大纲" if outline_meta else "结构：扁平回退"
    html_content = build_html(
        items,
        title=args.title,
        source_filename=source_filename,
        source_type=source_type,
        outline_meta=outline_meta,
        structure_note=structure_note,
        review=review,
    )
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_content, encoding="utf-8")
    note = "含评分卡" if review else "无评分卡"
    print(f"[ok] HTML 对照 → {html_path.name} ({structure_note} · {note})")

    if not args.no_png:
        png_path = html_path.with_suffix(".png")
        html_to_png(html_path, png_path)


if __name__ == "__main__":
    main()

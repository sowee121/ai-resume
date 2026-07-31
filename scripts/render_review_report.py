#!/usr/bin/env python3
"""Render resume review report JSON → HTML (+ Chrome headless screenshot → PNG).

展示口径：原稿测评。读取 `score_before` / `dimensions[].score_before`；
优化后分（`score`）仅供 diff 评分卡使用，本报告不展示。
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "review_report.html"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_source import resolve_source_filename, stem_from_outbox_name  # noqa: E402
from render_html_capture import favicon_link_html, html_to_png  # noqa: E402
from lib_paths import ensure_outbox  # noqa: E402


def _score_theme(score: int) -> dict[str, str]:
    if score >= 80:
        return {
            "score_label": "简历质量优秀",
            "header_gradient": "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #06b6d4 100%)",
        }
    if score >= 60:
        return {
            "score_label": "简历质量良好",
            "header_gradient": "linear-gradient(135deg, #7c3aed 0%, #db2777 55%, #f59e0b 100%)",
        }
    return {
        "score_label": "简历有待优化",
        "header_gradient": "linear-gradient(135deg, #6366f1 0%, #ec4899 60%, #f43f5e 100%)",
    }


def _read_score(value, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def _manuscript_score(data: dict) -> int:
    """原稿综合分：优先 score_before，缺省回退 score。"""
    before = _read_score(data.get("score_before"))
    if before is not None:
        return before
    return _read_score(data.get("score"), 0) or 0


def _manuscript_dim_score(dim: dict) -> int:
    before = _read_score(dim.get("score_before"))
    if before is not None:
        return before
    return _read_score(dim.get("score"), 0) or 0


def _tags_html(items: list, *, hit: bool) -> str:
    if not items:
        return '<span class="tag tag-empty">暂无</span>'
    css = "tag-hit" if hit else "tag-miss"
    return "\n        ".join(
        f'<span class="tag {css}">{html.escape(str(k))}</span>' for k in items
    )


def _list_html(items: list) -> str:
    if not items:
        return "<li>暂无</li>"
    return "\n        ".join(f"<li>{html.escape(str(i))}</li>" for i in items)


DIM_HINTS = {
    "ATS 关键词": "提升简历在招聘系统中的匹配度",
    "结构优化": "调整简历布局，突出重点内容",
    "量化表述": "用数据说话，展示具体成就",
    "技能匹配": "强化与目标岗位的技能关联",
    "语言表达": "优化措辞，使用专业术语",
    "亮点提炼": "突出核心优势和独特价值",
}


def _dim_label_html(name: str) -> str:
    base = html.escape(name)
    hint = DIM_HINTS.get(name.strip())
    if not hint:
        return f'<span class="dim-name">{base}</span>'
    return (
        f'<span class="dim-name">{base}'
        f'<span class="dim-hint">{html.escape(hint)}</span></span>'
    )


def _dimension_html(dimensions: list) -> str:
    if not dimensions:
        return '<div class="dim-item"><div class="dim-comment">暂无评分数据</div></div>'

    blocks: list[str] = []
    for dim in dimensions:
        name = str(dim.get("name", "未命名维度"))
        score = _manuscript_dim_score(dim)
        comment = html.escape(str(dim.get("comment", "")))
        blocks.append(
            f"""
      <div class="dim-item">
        <div class="dim-head">
          {_dim_label_html(name)}
          <span class="dim-score">{score} 分</span>
        </div>
        <div class="dim-bar"><div class="dim-fill" style="width:{score}%"></div></div>
        <div class="dim-comment">{comment or "暂无评语"}</div>
      </div>"""
        )
    return "\n".join(blocks)


def build_html(data: dict, *, source_filename: str) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    score = _manuscript_score(data)
    theme = _score_theme(score)

    title = str(data.get("title") or "简历优化诊断").strip() or "简历优化诊断"
    source_name = (source_filename or "").strip() or "resume.docx"
    hero_sub = f"{source_name} · 六维评分诊断报告"

    result = tpl
    result = result.replace("{{favicon_link}}", favicon_link_html(ROOT))
    result = result.replace("{{title}}", html.escape(title))
    result = result.replace("{{hero_sub}}", html.escape(hero_sub))
    result = result.replace("{{score}}", str(score))
    result = result.replace("{{score_label}}", html.escape(theme["score_label"]))
    result = result.replace("{{header_gradient}}", theme["header_gradient"])
    result = result.replace("{{strength_tags}}", _tags_html(data.get("strengths") or [], hit=True))
    result = result.replace("{{weakness_tags}}", _tags_html(data.get("weaknesses") or [], hit=False))
    result = result.replace("{{dimension_items}}", _dimension_html(data.get("dimensions") or []))
    result = result.replace("{{suggestion_items}}", _list_html(data.get("suggestions") or []))
    result = result.replace("{{step_items}}", _list_html(data.get("next_steps") or []))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Render review report JSON → HTML + PNG")
    parser.add_argument("--input", "-i", required=True, help="_review_report.json 路径")
    parser.add_argument("--output", "-o", help="输出 HTML 路径（默认同名 .html）")
    parser.add_argument(
        "--source-file",
        help="原稿文件名（如 吴卫.docx；默认从 segments/inbox 推断）",
    )
    parser.add_argument(
        "--source-type",
        choices=["docx", "pdf"],
        help="缺省推断失败时的扩展名回退",
    )
    parser.add_argument("--no-png", action="store_true", help="不自动截图 PNG")
    args = parser.parse_args()

    src = Path(args.input)
    data = json.loads(src.read_text(encoding="utf-8"))
    stem = stem_from_outbox_name(src.name, "_review_report")
    source_filename = resolve_source_filename(
        stem,
        root=ROOT,
        explicit=args.source_file,
        source_type=args.source_type,
    )

    html_path = (
        Path(args.output)
        if args.output
        else ensure_outbox() / f"{stem}_review_report.html"
    )
    html_content = build_html(data, source_filename=source_filename)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_content, encoding="utf-8")
    print(f"[ok] HTML 报告 → {html_path.name}")

    if not args.no_png:
        png_path = html_path.with_suffix(".png")
        html_to_png(html_path, png_path)


if __name__ == "__main__":
    main()

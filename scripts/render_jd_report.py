#!/usr/bin/env python3
"""Render JD match report JSON → HTML (+ optional Chrome headless screenshot → PNG)."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "jd_report.html"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_source import resolve_source_filename, stem_from_outbox_name  # noqa: E402
from render_html_capture import favicon_link_html, html_to_png  # noqa: E402
from lib_paths import ensure_outbox  # noqa: E402


def _score_theme(score: int) -> dict[str, str]:
    if score >= 80:
        return {
            "score_label": "匹配度高",
            "header_gradient": "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #06b6d4 100%)",
        }
    if score >= 60:
        return {
            "score_label": "匹配度中等",
            "header_gradient": "linear-gradient(135deg, #7c3aed 0%, #db2777 55%, #f59e0b 100%)",
        }
    return {
        "score_label": "匹配度有待提升",
        "header_gradient": "linear-gradient(135deg, #6366f1 0%, #ec4899 60%, #f43f5e 100%)",
    }


def _tags_html(keywords: list, hit: bool) -> str:
    if not keywords:
        return '<span class="tag tag-empty">暂无</span>'
    css = "tag-hit" if hit else "tag-miss"
    return "\n        ".join(
        f'<span class="tag {css}">{html.escape(str(k))}</span>' for k in keywords
    )


def _list_html(items: list) -> str:
    if not items:
        return "<li>暂无</li>"
    return "\n        ".join(f"<li>{html.escape(str(i))}</li>" for i in items)


def build_html(data: dict, *, source_filename: str) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    score = max(0, min(100, int(data.get("score", 0))))
    theme = _score_theme(score)
    source_name = (source_filename or "").strip() or "resume.docx"
    hero_sub = f"{source_name} · 岗位匹配诊断报告"

    result = tpl
    result = result.replace("{{favicon_link}}", favicon_link_html(ROOT, name="favicon-jd.svg"))
    result = result.replace("{{title}}", html.escape(str(data.get("title", "岗位匹配诊断"))))
    result = result.replace("{{hero_sub}}", html.escape(hero_sub))
    result = result.replace("{{score}}", str(score))
    result = result.replace("{{score_label}}", html.escape(theme["score_label"]))
    result = result.replace("{{header_gradient}}", theme["header_gradient"])
    result = result.replace("{{matched_tags}}", _tags_html(data.get("matched_keywords", []), hit=True))
    result = result.replace("{{missing_tags}}", _tags_html(data.get("missing_keywords", []), hit=False))
    result = result.replace("{{weak_items}}", _list_html(data.get("weak_points", data.get("suggestions", []))))
    result = result.replace("{{step_items}}", _list_html(data.get("next_steps", [])))
    return result


def screenshot(html_path: Path, png_path: Path) -> bool:
    return html_to_png(html_path, png_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render JD report JSON → HTML + PNG")
    parser.add_argument("--input", "-i", required=True, help="_jd_report.json 路径")
    parser.add_argument("--output", "-o", help="输出 HTML 路径（默认同名 .html）")
    parser.add_argument(
        "--source-file",
        help="原稿文件名（如 张三.docx；默认从 segments/inbox 推断）",
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
    stem = stem_from_outbox_name(src.name, "_jd_report")
    source_filename = resolve_source_filename(
        stem,
        root=ROOT,
        explicit=args.source_file,
        source_type=args.source_type,
    )

    html_path = (
        Path(args.output)
        if args.output
        else ensure_outbox() / f"{stem}_jd_report.html"
    )
    html_content = build_html(data, source_filename=source_filename)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_content, encoding="utf-8")
    print(f"[ok] HTML 报告 → {html_path.name}")

    if not args.no_png:
        png_path = html_path.with_suffix(".png")
        screenshot(html_path, png_path)


if __name__ == "__main__":
    main()

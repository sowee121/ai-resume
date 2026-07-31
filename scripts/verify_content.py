#!/usr/bin/env python3
"""Content integrity checks for replacements + optimized DOCX/PDF text."""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib_docx import extract_docx_segments  # noqa: E402

# rewritten 与 original 相似度过低 → 多半是 id 写串 / 改成了别条内容
MIN_SIMILARITY = 0.28


def _content_phrases(text: str) -> set[str]:
    """从正文提取可用于对齐 note 的短语（中文 3–6 字滑窗 + 英文词）。"""
    out: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]+", text or ""):
        if len(run) >= 3:
            out.add(run)
        for n in (3, 4, 5, 6):
            if len(run) < n:
                continue
            for i in range(len(run) - n + 1):
                out.add(run[i : i + n])
    for eng in re.findall(r"[A-Za-z][A-Za-z0-9.+#-]{1,}", text or ""):
        if len(eng) >= 2:
            out.add(eng)
            out.add(eng.lower())
    return out


def verify_notes_relevance(items: list) -> list[str]:
    """改动说明必须能锚到本条正文；若只能锚到别条 → 串说明。"""
    errors: list[str] = []
    contents: dict[str, str] = {}
    phrase_index: dict[str, set[str]] = {}

    for item in items:
        sid = str(item.get("id", "")).strip()
        if not sid:
            continue
        text = str(item.get("original", "")) + "\n" + str(item.get("rewritten", ""))
        contents[sid] = text
        for ph in _content_phrases(text):
            phrase_index.setdefault(ph, set()).add(sid)

    # 过短/过泛短语不参与「外溢」判定
    weak = {
        "前端",
        "项目",
        "系统",
        "优化",
        "提升",
        "负责",
        "平台",
        "公司",
        "研发",
        "迭代",
        "交付",
        "用户",
        "业务",
        "数据",
        "支持",
        "实现",
        "建设",
        "技术",
        "信息",
        "规模",
        "核心",
        "能力",
        "工程",
        "对齐",
        "稳定",
        "定性",
        "稳定性",
        "工程化",
        "技术栈",
        "术栈",
        "核心业",
        "心业务",
        "核心业务",
        "句式",
    }

    for item in items:
        sid = str(item.get("id", "")).strip()
        original = str(item.get("original", ""))
        rewritten = str(item.get("rewritten", ""))
        note = str(item.get("note") or "").strip()

        if original == rewritten:
            if note:
                errors.append(f"[说明] {sid} 未改写但 note 非空：{note[:24]!r}")
            continue

        if not note:
            errors.append(f"[说明] {sid} 有改写但缺少 note")
            continue

        self_hits: list[str] = []
        other_hits: list[tuple[str, str]] = []
        # 只检查「出现在 note 里」的正文短语
        for ph, owners in phrase_index.items():
            if len(ph) < 3 or ph in weak:
                continue
            if ph not in note:
                continue
            if sid in owners:
                self_hits.append(ph)
            else:
                # 独属于别条
                if len(owners) == 1:
                    other_hits.append((ph, next(iter(owners))))

        if not self_hits and other_hits:
            sample = "、".join(f"{t}→{oid}" for t, oid in other_hits[:4])
            errors.append(
                f"[说明] {sid} 的 note 与改写内容无关，锚到了其他条目"
                f"（note={note[:28]!r}；外溢：{sample}）"
            )

    return errors


def verify_diff_html_notes(diff_html_path: Path, replacements_path: Path) -> list[str]:
    """diff HTML 中的「改动说明」必须来自 replacements.note。"""
    errors: list[str] = []
    if not diff_html_path.exists():
        return [f"[diff] 找不到 {diff_html_path.name}"]

    html = diff_html_path.read_text(encoding="utf-8")
    items = _rep_list(_load_json(replacements_path))
    expected_notes = [
        str(i.get("note") or "").strip()
        for i in items
        if i.get("original") != i.get("rewritten") and str(i.get("note") or "").strip()
    ]

    # 统计 HTML 中改动说明数量
    found = re.findall(
        r'class="pair-note"[^>]*>\s*<span class="pair-note-label">改动说明：</span>\s*(.*?)\s*</div>',
        html,
        flags=re.S,
    )
    # 去 HTML 实体简单还原
    def _unescape(s: str) -> str:
        return (
            s.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )

    found_notes = [_unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in found]

    if len(found_notes) != len(expected_notes):
        errors.append(
            f"[diff] 改动说明条数不一致：HTML {len(found_notes)} vs replacements {len(expected_notes)}"
        )

    missing = [n for n in expected_notes if n not in found_notes]
    for n in missing[:8]:
        errors.append(f"[diff] HTML 缺少改动说明：{n[:36]!r}")

    # HTML 中出现但不在 expected 的（串说明残留）
    unexpected = [n for n in found_notes if n not in expected_notes]
    for n in unexpected[:8]:
        errors.append(f"[diff] HTML 出现未知改动说明：{n[:36]!r}")

    return errors


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _rep_list(data) -> list:
    if isinstance(data, dict) and "replacements" in data:
        data = data["replacements"]
    if not isinstance(data, list):
        raise ValueError("replacements 必须是数组")
    return data


def _seg_map(segments_path: Path) -> dict[str, str]:
    payload = _load_json(segments_path)
    segs = payload.get("segments", payload if isinstance(payload, list) else [])
    return {str(s["id"]): str(s.get("text", "")) for s in segs}


def _similarity(a: str, b: str) -> float:
    a, b = a.strip(), b.strip()
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def verify_replacements_against_segments(
    replacements_path: Path,
    segments_path: Path,
) -> list[str]:
    errors: list[str] = []
    items = _rep_list(_load_json(replacements_path))
    segs = _seg_map(segments_path)

    seen: set[str] = set()
    for item in items:
        sid = str(item.get("id", "")).strip()
        if not sid:
            errors.append("[替换] 存在缺少 id 的条目")
            continue
        if sid in seen:
            errors.append(f"[替换] 重复 id：{sid}")
        seen.add(sid)

        if sid not in segs:
            errors.append(f"[替换] {sid} 不在 segments 中")
            continue

        original = str(item.get("original", ""))
        rewritten = str(item.get("rewritten", ""))
        seg_text = segs[sid]

        if original != seg_text:
            errors.append(
                f"[替换] {sid} 的 original 与 segments 不一致 "
                f"（original 前 24 字：{original[:24]!r} / segment：{seg_text[:24]!r}）"
            )

        if original == rewritten:
            continue

        sim = _similarity(original, rewritten)
        # 短标题被整段换成无关职责时 similarity 会极低
        if sim < MIN_SIMILARITY and original not in rewritten and rewritten not in original:
            errors.append(
                f"[串改] {sid} rewritten 与 original 相似度过低（{sim:.2f}），"
                f"疑似写到错误条目：{original[:20]!r} → {rewritten[:28]!r}"
            )

    errors.extend(verify_notes_relevance(items))
    return errors


def verify_optimized_docx(
    inbox_path: Path,
    optimized_path: Path,
    replacements_path: Path,
) -> list[str]:
    """逐段核对：优化稿段落文本必须等于 mapping[id]（或原文）。"""
    errors: list[str] = []
    if not inbox_path.exists():
        errors.append(f"[正文] 找不到原稿 {inbox_path}")
        return errors
    if not optimized_path.exists():
        errors.append(f"[正文] 找不到优化稿 {optimized_path}")
        return errors

    items = _rep_list(_load_json(replacements_path))
    mapping = {
        str(i["id"]): str(i.get("rewritten", i.get("original", "")))
        for i in items
        if i.get("id")
    }

    src_segs = extract_docx_segments(str(inbox_path))
    dst_segs = extract_docx_segments(str(optimized_path))

    if len(src_segs) != len(dst_segs):
        errors.append(
            f"[正文] 段落数不一致：原稿 {len(src_segs)} vs 优化稿 {len(dst_segs)}"
        )

    n = min(len(src_segs), len(dst_segs))
    for i in range(n):
        sid = src_segs[i].id
        if dst_segs[i].id != sid:
            errors.append(f"[正文] 段落 id 错位：原稿 {sid} vs 优化稿 {dst_segs[i].id}")
            continue
        expected = mapping.get(sid, src_segs[i].text)
        actual = dst_segs[i].text
        if actual != expected:
            errors.append(
                f"[正文] {sid} 回写结果不符：期望 {expected[:28]!r}，实际 {actual[:28]!r}"
            )

    # 关键标题/简介不应从优化稿中消失（用 original 关键词抽查）
    for item in items:
        original = str(item.get("original", "")).strip()
        rewritten = str(item.get("rewritten", "")).strip()
        if len(original) <= 20 and re.search(r"[\u4e00-\u9fff]{2,}", original):
            # 短中文标题：优化稿全文应仍能找到 rewritten（即未被吞掉）
            joined = "\n".join(s.text for s in dst_segs)
            if rewritten and rewritten not in joined:
                errors.append(
                    f"[正文] 短标题/短句丢失：{item.get('id')} {rewritten[:24]!r} 不在优化稿中"
                )

    return errors


def verify_stem_content(stem: str, *, jd: bool = False, root: Path | None = None) -> list[str]:
    root = root or ROOT
    outbox = root / "outbox"
    jsons = root / "jsons"
    inbox = root / "inbox"
    suffix = "_replacements_jd.json" if jd else "_replacements.json"
    opt_suffix = "_定制版.docx" if jd else "_优化版.docx"

    replacements = jsons / f"{stem}{suffix}"
    if not replacements.exists():
        replacements = outbox / f"{stem}{suffix}"
    segments = jsons / f"{stem}_segments.json"
    if not segments.exists():
        segments = outbox / f"{stem}_segments.json"
    optimized = outbox / f"{stem}{opt_suffix}"

    inbox_docx = inbox / f"{stem}.docx"
    if not inbox_docx.exists():
        # pdf 暂不做正文逐段核对
        return []

    errors: list[str] = []
    if replacements.exists() and segments.exists():
        errors.extend(verify_replacements_against_segments(replacements, segments))
    if replacements.exists() and optimized.exists():
        errors.extend(verify_optimized_docx(inbox_docx, optimized, replacements))

    diff_html = outbox / (f"{stem}_diff_jd.html" if jd else f"{stem}_diff.html")
    if replacements.exists() and diff_html.exists():
        errors.extend(verify_diff_html_notes(diff_html, replacements))

    return errors


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Verify replacements/optimized content integrity")
    parser.add_argument("--stem", required=True)
    parser.add_argument("--jd", action="store_true")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    errors = verify_stem_content(args.stem, jd=args.jd, root=Path(args.root))
    if errors:
        print(f"[FAIL] {args.stem} 内容验收失败（{len(errors)} 项）：")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    print(f"[PASS] {args.stem} 内容验收通过")


if __name__ == "__main__":
    main()

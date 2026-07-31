"""PDF segment extract / text-layer rewrite (best-effort, not pixel-perfect layout)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

SKIP_RE = re.compile(
    r"("
    r"^[\d\s\-–—./]+$"
    r"|@"
    r"|https?://"
    r"|^(电话|手机|邮箱|微信|地址|出生|籍贯)[:：]"
    r")"
)


@dataclass
class Segment:
    id: str
    text: str
    kind: str
    editable: bool
    source: str
    page: int = 0
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)


def _is_editable(text: str) -> bool:
    t = text.strip()
    if len(t) < 8:
        return False
    if SKIP_RE.search(t):
        return False
    return True


def extract_pdf_segments(path: str) -> List[Segment]:
    doc = fitz.open(path)
    segments: List[Segment] = []
    n = 0
    for page_index, page in enumerate(doc):
        # blocks: (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = page.get_text("blocks")
        for bi, block in enumerate(blocks):
            if block[6] != 0:  # not text
                continue
            text = (block[4] or "").strip()
            if not text:
                continue
            # normalize newlines inside block to single spaces for editing unit
            flat = re.sub(r"\s+", " ", text).strip()
            if not flat:
                continue
            sid = f"pdf-p{page_index}-b{bi}-{n}"
            segments.append(
                Segment(
                    id=sid,
                    text=flat,
                    kind="pdf_block",
                    editable=_is_editable(flat),
                    source="pdf",
                    page=page_index,
                    bbox=(block[0], block[1], block[2], block[3]),
                )
            )
            n += 1
    doc.close()
    return segments


def _pick_cjk_font() -> Optional[str]:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def apply_pdf_replacements(src_path: str, dst_path: str, mapping: Dict[str, str], segments: List[dict]) -> int:
    """
    Best-effort PDF rewrite: redact original block bbox and insert rewritten text.
    Layout/fonts will NOT fully match the original; prefer DOCX for true style lock.
    """
    by_id = {s["id"]: s for s in segments}
    doc = fitz.open(src_path)
    fontfile = _pick_cjk_font()
    applied = 0
    for sid, new_text in mapping.items():
        meta = by_id.get(sid)
        if not meta:
            continue
        old = meta.get("text", "")
        if new_text == old:
            continue
        page = doc[meta["page"]]
        bbox = fitz.Rect(meta["bbox"])
        page.add_redact_annot(bbox, fill=(1, 1, 1))
        page.apply_redactions()
        fontsize = max(8, min(14, (bbox.y1 - bbox.y0) * 0.7))
        if fontfile:
            page.insert_textbox(
                bbox,
                new_text,
                fontsize=fontsize,
                fontfile=fontfile,
                align=0,
                color=(0, 0, 0),
            )
        else:
            page.insert_textbox(
                bbox,
                new_text,
                fontsize=fontsize,
                fontname="helv",
                align=0,
                color=(0, 0, 0),
            )
        applied += 1
    doc.save(dst_path)
    doc.close()
    return applied


def write_pdf_text_fallback(dst_txt_path: str, segments: List[dict], mapping: Dict[str, str]) -> None:
    """Always write a plain-text optimized manuscript for PDF jobs."""
    lines = []
    for s in segments:
        sid = s["id"]
        text = mapping.get(sid, s["text"])
        lines.append(text)
        lines.append("")
    with open(dst_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")


def segments_to_dicts(segments: List[Segment]) -> list:
    out = []
    for s in segments:
        d = asdict(s)
        d["bbox"] = list(s.bbox)
        out.append(d)
    return out

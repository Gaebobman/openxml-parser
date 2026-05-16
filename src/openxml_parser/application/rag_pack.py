from __future__ import annotations

from dataclasses import dataclass

from openxml_parser.application.config import ParserConfig
from openxml_parser.domain.entities import ParsedDocument


@dataclass
class RagChunk:
    chunk_id: str
    page_number: int
    text: str
    metadata: dict[str, object]


def build_rag_chunks(parsed_document: ParsedDocument, config: ParserConfig) -> list[RagChunk]:
    caption_by_target = _caption_relation_map(parsed_document)
    chunks: list[RagChunk] = []
    idx = 1
    for page in parsed_document.pages:
        blocks = []
        for e in page.elements:
            txt = (e.text or "").strip()
            if txt:
                blocks.append(txt)
            if config.chunk_include_captions:
                caption = caption_by_target.get(e.element_id)
                if isinstance(caption, str) and caption.strip():
                    blocks.append(f"[CAPTION] {caption.strip()}")
        page_text = "\n\n".join(blocks).strip()
        if not page_text:
            continue
        parts = _split_text(page_text, config.chunk_max_chars)
        for part in parts:
            chunks.append(
                RagChunk(
                    chunk_id=f"CH_{idx:05d}",
                    page_number=page.page_number,
                    text=part,
                    metadata={
                        "source_path": parsed_document.source_path,
                        "page_number": page.page_number,
                    },
                )
            )
            idx += 1
    return chunks


def _caption_relation_map(parsed_document: ParsedDocument) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in parsed_document.relations:
        if rel.relation_type != "caption_of":
            continue
        caption_text = rel.metadata.get("caption_text")
        if isinstance(caption_text, str) and caption_text.strip():
            out[rel.target_element_id] = caption_text.strip()
    return out


def _split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    out: list[str] = []
    cur = []
    cur_len = 0
    for para in text.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        add_len = len(p) + (2 if cur else 0)
        if cur and (cur_len + add_len > max_chars):
            out.append("\n\n".join(cur))
            cur = [p]
            cur_len = len(p)
        else:
            cur.append(p)
            cur_len += add_len
    if cur:
        out.append("\n\n".join(cur))
    return out


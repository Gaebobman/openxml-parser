from __future__ import annotations

from dataclasses import dataclass

from openxml_parser.application.config import ParserConfig
from openxml_parser.domain.entities import BlockKind, ParsedDocument


@dataclass
class RagChunk:
    chunk_id: str
    page_number: int
    text: str
    metadata: dict[str, object]


def build_rag_chunks(parsed_document: ParsedDocument, config: ParserConfig) -> list[RagChunk]:
    if parsed_document.blocks:
        return _build_rag_chunks_from_blocks(parsed_document, config)
    return _build_rag_chunks_legacy(parsed_document, config)


def _build_rag_chunks_from_blocks(
    parsed_document: ParsedDocument,
    config: ParserConfig,
) -> list[RagChunk]:
    caption_by_target = _caption_relation_map(parsed_document)
    element_by_id = {
        e.element_id: e
        for page in parsed_document.pages
        for e in page.elements
    }
    chunks: list[RagChunk] = []
    idx = 1

    for block in parsed_document.blocks:
        if block.kind == BlockKind.CONTAINER:
            continue

        parts: list[str] = []
        if block.title_text and block.kind == BlockKind.HEADING:
            parts.append(block.title_text)
        for element_id in block.element_ids:
            element = element_by_id.get(element_id)
            if element is None:
                continue
            txt = _element_display_text(element, config)
            if txt and txt != block.title_text.strip():
                parts.append(txt)
            if config.chunk_include_captions:
                caption = caption_by_target.get(element_id)
                if isinstance(caption, str) and caption.strip():
                    parts.append(f"[CAPTION] {caption.strip()}")

        block_text = "\n\n".join(parts).strip()
        if not block_text:
            continue

        style_meta = _element_style_metadata(element_by_id, block.element_ids)
        for part in _split_text(block_text, config.chunk_max_chars):
            metadata: dict[str, object] = {
                "source_path": parsed_document.source_path,
                "page_number": block.page_number,
                "block_id": block.block_id,
                "block_kind": block.kind.value,
                "element_ids": list(block.element_ids),
            }
            if block.kind == BlockKind.HEADING:
                metadata["outline_level"] = block.level
                if block.parent_block_id:
                    metadata["parent_block_id"] = block.parent_block_id
            if block.section_path:
                metadata["section_path"] = block.section_path
            metadata.update(style_meta)
            chunks.append(
                RagChunk(
                    chunk_id=f"CH_{idx:05d}",
                    page_number=block.page_number,
                    text=part,
                    metadata=metadata,
                )
            )
            idx += 1
    return chunks


def _build_rag_chunks_legacy(parsed_document: ParsedDocument, config: ParserConfig) -> list[RagChunk]:
    caption_by_target = _caption_relation_map(parsed_document)
    chunks: list[RagChunk] = []
    idx = 1
    for page in parsed_document.pages:
        for e in page.elements:
            parts: list[str] = []
            txt = _element_display_text(e, config)
            if txt:
                parts.append(txt)
            if config.chunk_include_captions:
                caption = caption_by_target.get(e.element_id)
                if isinstance(caption, str) and caption.strip():
                    parts.append(f"[CAPTION] {caption.strip()}")
            element_text = "\n\n".join(parts).strip()
            if not element_text:
                continue
            for part in _split_text(element_text, config.chunk_max_chars):
                metadata: dict[str, object] = {
                    "source_path": parsed_document.source_path,
                    "page_number": page.page_number,
                    "element_id": e.element_id,
                }
                metadata.update(_element_style_metadata({e.element_id: e}, [e.element_id]))
                chunks.append(
                    RagChunk(
                        chunk_id=f"CH_{idx:05d}",
                        page_number=page.page_number,
                        text=part,
                        metadata=metadata,
                    )
                )
                idx += 1
    return chunks


def _element_display_text(element, config: ParserConfig) -> str:
    text = (element.text or "").strip()
    if config.preserve_text_formatting:
        fmt = element.metadata.get("formatted_text")
        if isinstance(fmt, str) and fmt.strip():
            return fmt.strip()
    return text


def _element_style_metadata(
    element_by_id: dict[str, object],
    element_ids: list[str],
) -> dict[str, object]:
    for element_id in element_ids:
        element = element_by_id.get(element_id)
        if element is None:
            continue
        out: dict[str, object] = {}
        for key in ("paragraph_style", "is_mostly_bold", "list_level", "line_pattern", "is_heading"):
            if key in element.metadata:
                out[key] = element.metadata[key]
        if out:
            return out
    return {}


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
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split_at = text.rfind("\n\n", start, end)
            if split_at > start:
                end = split_at
        parts.append(text[start:end].strip())
        start = end
    return [p for p in parts if p]

from __future__ import annotations

from openxml_parser.domain.entities import DocumentBlock, ParsedDocument
from openxml_parser.infrastructure.structure.registry import structure_builder_for_path


def build_document_blocks(parsed: ParsedDocument) -> list[DocumentBlock]:
    """Populate logical blocks (L3) for all pages."""
    builder = structure_builder_for_path(parsed.source_path)
    blocks: list[DocumentBlock] = []
    for page in parsed.pages:
        page_blocks = builder.build(page, relations=parsed.relations)
        blocks.extend(page_blocks)
    return blocks

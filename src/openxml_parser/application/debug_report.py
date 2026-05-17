from __future__ import annotations

from openxml_parser.domain.entities import ParsedDocument


def build_debug_report(parsed_document: ParsedDocument) -> dict[str, object]:
    pages = []
    for page in parsed_document.pages:
        pages.append(
            {
                "page_number": page.page_number,
                "num_elements": len(page.elements),
                "elements": [
                    {
                        "element_id": e.element_id,
                        "type": e.element_type.value,
                        "bbox": {
                            "x": e.bbox.x,
                            "y": e.bbox.y,
                            "width": e.bbox.width,
                            "height": e.bbox.height,
                        },
                        "text_preview": (e.text or "")[:120],
                    }
                    for e in page.elements
                ],
                "caption_candidate_decisions": page.metadata.get("caption_candidate_decisions", []),
            }
        )
    return {
        "source_path": parsed_document.source_path,
        "num_pages": len(parsed_document.pages),
        "num_blocks": len(parsed_document.blocks),
        "num_relations": len(parsed_document.relations),
        "blocks": [
            {
                "block_id": b.block_id,
                "kind": b.kind.value,
                "level": b.level,
                "title_text": b.title_text[:120],
                "parent_block_id": b.parent_block_id,
                "section_path": b.section_path,
                "element_ids": b.element_ids,
                "page_number": b.page_number,
            }
            for b in parsed_document.blocks
        ],
        "relations": [
            {
                "relation_type": r.relation_type,
                "source_element_id": r.source_element_id,
                "target_element_id": r.target_element_id,
                "confidence": r.confidence,
            }
            for r in parsed_document.relations
        ],
        "pages": pages,
    }


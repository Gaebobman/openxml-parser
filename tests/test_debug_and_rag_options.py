from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.debug_report import build_debug_report
from document_inteligence.application.rag_pack import build_rag_chunks
from document_inteligence.domain.entities import (
    DocumentElement,
    DocumentPage,
    ElementRelation,
    ElementType,
    ParsedDocument,
)
from document_inteligence.domain.value_objects import BBox


def _text_element(element_id: str, text: str) -> DocumentElement:
    return DocumentElement(
        element_id=element_id,
        element_type=ElementType.TEXT,
        page_number=1,
        z_order=1,
        bbox=BBox(x=0.1, y=0.1, width=0.5, height=0.1),
        text=text,
        metadata={},
    )


def _image_element(element_id: str) -> DocumentElement:
    return DocumentElement(
        element_id=element_id,
        element_type=ElementType.IMAGE,
        page_number=1,
        z_order=2,
        bbox=BBox(x=0.1, y=0.3, width=0.3, height=0.2),
        text=None,
        metadata={},
    )


def test_debug_report_contains_candidate_decisions() -> None:
    page = DocumentPage(
        page_number=1,
        width=1.0,
        height=1.0,
        elements=[_text_element("T1", "title")],
        metadata={"caption_candidate_decisions": [{"target_element_id": "I1", "rejected_reason": "no_candidate"}]},
    )
    doc = ParsedDocument(source_path="x.pptx", pages=[page], relations=[])
    debug = build_debug_report(doc)
    decisions = debug["pages"][0]["caption_candidate_decisions"]
    assert isinstance(decisions, list)
    assert decisions[0]["rejected_reason"] == "no_candidate"


def test_rag_chunk_can_include_caption_lines() -> None:
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[_text_element("T1", "본문"), _image_element("I1")])
    relation = ElementRelation(
        relation_type="caption_of",
        source_element_id="T1",
        target_element_id="I1",
        confidence=0.8,
        metadata={"caption_text": "그림 설명"},
    )
    doc = ParsedDocument(source_path="x.pptx", pages=[page], relations=[relation])

    chunks = build_rag_chunks(doc, ParserConfig(chunk_include_captions=True, chunk_max_chars=500))
    assert "[CAPTION] 그림 설명" in chunks[0].text


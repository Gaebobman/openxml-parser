from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.rag_pack import build_rag_chunks
from document_inteligence.application.relationships import detect_relations
from document_inteligence.domain.entities import DocumentElement, DocumentPage, ElementType, ParsedDocument
from document_inteligence.domain.repositories import CaptionVerifier
from document_inteligence.domain.value_objects import BBox


def _el(element_id: str, t: ElementType, x: float, y: float, w: float, h: float, text: str | None = None):
    return DocumentElement(
        element_id=element_id,
        element_type=t,
        page_number=1,
        z_order=1,
        bbox=BBox(x=x, y=y, width=w, height=h),
        text=text,
        metadata={},
    )


def test_detect_caption_relation() -> None:
    image = _el("IMG1", ElementType.IMAGE, 0.1, 0.2, 0.3, 0.2)
    caption = _el("TXT1", ElementType.TEXT, 0.1, 0.42, 0.3, 0.05, "Figure caption")
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[image, caption])
    relations = detect_relations([page], ParserConfig(caption_max_gap=0.08, alignment_tolerance=0.2))
    rel = next(r for r in relations if r.relation_type == "caption_of" and r.target_element_id == "IMG1")
    assert isinstance(rel.metadata.get("score_breakdown"), dict)
    assert rel.metadata.get("rejected_reason") is None


class _AlwaysYesVerifier(CaptionVerifier):
    def verify(
        self,
        *,
        page_number: int,
        image_element_id: str,
        caption_element_id: str,
        caption_text: str,
    ) -> tuple[bool, float]:
        return (True, 0.91)


def test_detect_caption_uses_vlm_fallback_for_ambiguous_case() -> None:
    image = _el("IMG1", ElementType.IMAGE, 0.1, 0.2, 0.3, 0.2)
    # intentionally weak keyword signal but close enough for fallback range
    caption = _el("TXT1", ElementType.TEXT, 0.1, 0.43, 0.3, 0.05, "간단 설명")
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[image, caption])
    config = ParserConfig(caption_max_gap=0.3, caption_rule_threshold=0.95, caption_vlm_threshold=0.2)
    relations = detect_relations([page], config, caption_verifier=_AlwaysYesVerifier())
    rel = next(r for r in relations if r.relation_type == "caption_of")
    assert rel.metadata.get("method") == "vlm_fallback"
    assert rel.confidence == 0.91


def test_build_rag_chunks_splits_long_text() -> None:
    text = "A" * 800 + "\n\n" + "B" * 800
    page = DocumentPage(
        page_number=1,
        width=1.0,
        height=1.0,
        elements=[_el("T1", ElementType.TEXT, 0.1, 0.1, 0.5, 0.3, text)],
    )
    doc = ParsedDocument(source_path="x.pptx", pages=[page])
    chunks = build_rag_chunks(doc, ParserConfig(chunk_max_chars=900))
    assert len(chunks) == 2
    assert chunks[0].page_number == 1


def test_conflict_resolution_allows_single_caption_text_assignment() -> None:
    image1 = _el("IMG1", ElementType.IMAGE, 0.1, 0.2, 0.2, 0.2)
    image2 = _el("IMG2", ElementType.IMAGE, 0.5, 0.2, 0.2, 0.2)
    # one caption spanning both images; should map to one best target only
    caption = _el("TXT1", ElementType.TEXT, 0.1, 0.42, 0.6, 0.05, "Figure comparison")
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[image1, image2, caption])
    relations = detect_relations([page], ParserConfig(caption_max_gap=0.3, alignment_tolerance=0.2))
    caption_rels = [r for r in relations if r.relation_type == "caption_of"]
    assert len(caption_rels) == 1


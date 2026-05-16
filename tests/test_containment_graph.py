from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.containment_graph import resolve_containment
from document_inteligence.domain.entities import DocumentElement, DocumentPage, ElementType
from document_inteligence.domain.value_objects import BBox


def _el(
    element_id: str,
    *,
    element_type: ElementType,
    bbox: BBox,
    text: str | None = None,
    metadata: dict[str, object] | None = None,
) -> DocumentElement:
    return DocumentElement(
        element_id=element_id,
        element_type=element_type,
        page_number=1,
        z_order=1,
        bbox=bbox,
        text=text,
        metadata=metadata or {},
    )


def test_text_inside_text_merges_into_paragraph() -> None:
    outer = _el("OUTER", element_type=ElementType.TEXT,
                 bbox=BBox(x=0.1, y=0.1, width=0.5, height=0.4), text="외부 텍스트")
    inner = _el("INNER", element_type=ElementType.TEXT,
                 bbox=BBox(x=0.15, y=0.15, width=0.3, height=0.2), text="내부 텍스트")
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[outer, inner])

    resolve_containment(page, ParserConfig(containment_threshold=0.5))

    assert inner.metadata.get("absorbed_by") == "OUTER"
    assert "내부 텍스트" in (outer.text or "")
    assert "외부 텍스트" in (outer.text or "")
    assert outer.metadata.get("merged_children") == ["INNER"]


def test_shape_as_bbox_groups_children() -> None:
    container = _el("BOX", element_type=ElementType.UNKNOWN,
                     bbox=BBox(x=0.05, y=0.05, width=0.6, height=0.6), text="")
    text1 = _el("T1", element_type=ElementType.TEXT,
                 bbox=BBox(x=0.1, y=0.1, width=0.4, height=0.1), text="첫 줄")
    text2 = _el("T2", element_type=ElementType.TEXT,
                 bbox=BBox(x=0.1, y=0.25, width=0.4, height=0.1), text="둘째 줄")
    img = _el("I1", element_type=ElementType.IMAGE,
              bbox=BBox(x=0.1, y=0.4, width=0.2, height=0.15),
              metadata={"image": {"filename": "img.png"}})
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[container, text1, text2, img])

    resolve_containment(page, ParserConfig(containment_threshold=0.5))

    assert text1.metadata.get("absorbed_by") == "BOX"
    assert text2.metadata.get("absorbed_by") == "BOX"
    assert img.metadata.get("absorbed_by") == "BOX"
    absorbed = container.metadata.get("absorbed_children")
    assert isinstance(absorbed, list) and len(absorbed) == 3


def test_non_overlapping_elements_remain_independent() -> None:
    e1 = _el("A", element_type=ElementType.TEXT,
             bbox=BBox(x=0.0, y=0.0, width=0.3, height=0.3), text="왼쪽")
    e2 = _el("B", element_type=ElementType.TEXT,
             bbox=BBox(x=0.5, y=0.5, width=0.3, height=0.3), text="오른쪽")
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[e1, e2])

    resolve_containment(page, ParserConfig(containment_threshold=0.5))

    assert "absorbed_by" not in e1.metadata
    assert "absorbed_by" not in e2.metadata

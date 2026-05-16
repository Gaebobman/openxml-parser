from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.markdown_renderer import render_markdown
from document_inteligence.application.table_absorber import absorb_overlapping_elements
from document_inteligence.domain.entities import DocumentElement, DocumentPage, ElementType, ParsedDocument
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


def test_absorb_overlapping_elements_moves_text_into_table_cell() -> None:
    table = _el(
        "TB1",
        element_type=ElementType.TABLE,
        bbox=BBox(x=0.1, y=0.1, width=0.6, height=0.4),
        metadata={
            "table_cells": [
                {
                    "row": 0,
                    "col": 0,
                    "text": "제목",
                    "is_spanned": False,
                    "span_width": 1,
                    "span_height": 1,
                    "cell_bbox": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.2},
                },
                {
                    "row": 0,
                    "col": 1,
                    "text": "값",
                    "is_spanned": False,
                    "span_width": 1,
                    "span_height": 1,
                    "cell_bbox": {"x": 0.4, "y": 0.1, "width": 0.3, "height": 0.2},
                },
            ]
        },
    )
    text_box = _el(
        "TXT1",
        element_type=ElementType.TEXT,
        bbox=BBox(x=0.11, y=0.11, width=0.25, height=0.18),
        text="셀 내부 텍스트",
    )
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[table, text_box])

    absorb_overlapping_elements(page, ParserConfig(table_cell_containment_threshold=0.2))

    assert text_box.metadata.get("absorbed_by_table") is True
    cells = table.metadata["table_cells"]
    first_cell = cells[0]
    absorbed = first_cell.get("absorbed_elements")
    assert isinstance(absorbed, list) and len(absorbed) == 1
    assert absorbed[0]["element_id"] == "TXT1"
    assert absorbed[0]["content"] == "셀 내부 텍스트"


def test_containment_ratio_absorbs_small_image_inside_large_cell() -> None:
    """Large merged cell with an image fully contained inside."""
    table = _el(
        "TB1",
        element_type=ElementType.TABLE,
        bbox=BBox(x=0.01, y=0.15, width=0.98, height=0.85),
        metadata={
            "table_cells": [
                {
                    "row": 0, "col": 0, "text": "header",
                    "is_spanned": False, "span_width": 8, "span_height": 1,
                    "cell_bbox": {"x": 0.01, "y": 0.15, "width": 0.98, "height": 0.04},
                },
                {
                    "row": 1, "col": 0, "text": None,
                    "is_spanned": False, "span_width": 8, "span_height": 1,
                    "is_merge_origin": True,
                    "cell_bbox": {"x": 0.01, "y": 0.19, "width": 0.98, "height": 0.81},
                },
            ]
        },
    )
    img = _el(
        "IMG1",
        element_type=ElementType.IMAGE,
        bbox=BBox(x=0.04, y=0.21, width=0.57, height=0.19),
        metadata={"image": {"filename": "img.png"}},
    )
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[table, img])
    absorb_overlapping_elements(page, ParserConfig(table_cell_containment_threshold=0.5))

    assert img.metadata.get("absorbed_by_table") is True
    body_cell = table.metadata["table_cells"][1]
    absorbed = body_cell.get("absorbed_elements")
    assert isinstance(absorbed, list) and len(absorbed) == 1
    assert absorbed[0]["element_id"] == "IMG1"


def test_absorbed_elements_rendered_in_spatial_order() -> None:
    """Elements absorbed out-of-order should be rendered top-to-bottom."""
    table = _el(
        "TB1",
        element_type=ElementType.TABLE,
        bbox=BBox(x=0.0, y=0.0, width=1.0, height=1.0),
        metadata={
            "table_cells": [
                {
                    "row": 0, "col": 0, "text": None,
                    "is_spanned": False, "span_width": 1, "span_height": 1,
                    "cell_bbox": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                },
            ]
        },
    )
    bottom = _el("B", element_type=ElementType.TEXT,
                  bbox=BBox(x=0.1, y=0.8, width=0.3, height=0.1), text="아래")
    top = _el("T", element_type=ElementType.TEXT,
              bbox=BBox(x=0.1, y=0.1, width=0.3, height=0.1), text="위")
    page = DocumentPage(page_number=1, width=1.0, height=1.0,
                        elements=[table, bottom, top])
    absorb_overlapping_elements(page, ParserConfig(table_cell_containment_threshold=0.1))

    md = render_markdown(ParsedDocument(source_path="x.pptx", pages=[page]),
                         config=ParserConfig(table_render_html=True))
    assert md.index("위") < md.index("아래")


def test_render_html_table_supports_span_and_absorbed_image() -> None:
    table = _el(
        "TB1",
        element_type=ElementType.TABLE,
        bbox=BBox(x=0.1, y=0.1, width=0.8, height=0.5),
        metadata={
            "table_cells": [
                {
                    "row": 0,
                    "col": 0,
                    "text": "헤더",
                    "is_spanned": False,
                    "span_width": 2,
                    "span_height": 1,
                    "is_merge_origin": True,
                    "absorbed_elements": [{"element_id": "IMG1", "type": "image", "content": "![IMG1](img.png)", "containment": 0.7}],
                },
                {"row": 0, "col": 1, "text": None, "is_spanned": True, "span_width": 1, "span_height": 1},
                {"row": 1, "col": 0, "text": "A", "is_spanned": False, "span_width": 1, "span_height": 1},
                {"row": 1, "col": 1, "text": "B", "is_spanned": False, "span_width": 1, "span_height": 1},
            ]
        },
    )
    absorbed_img = _el(
        "IMG1",
        element_type=ElementType.IMAGE,
        bbox=BBox(x=0.12, y=0.12, width=0.1, height=0.1),
        metadata={"image": {"filename": "img.png"}, "absorbed_by_table": True},
    )
    page = DocumentPage(page_number=1, width=1.0, height=1.0, elements=[table, absorbed_img])
    md = render_markdown(ParsedDocument(source_path="x.pptx", pages=[page]), config=ParserConfig(table_render_html=True))

    assert "<table>" in md
    assert 'colspan="2"' in md
    assert '<img src="img.png" alt="IMG1"/>' in md
    assert md.count('<img src="img.png" alt="IMG1"/>') == 1

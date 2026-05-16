from __future__ import annotations

from openxml_parser.application.markdown_renderer import render_markdown
from openxml_parser.application.reading_order import order_page_elements
from openxml_parser.domain.entities import DocumentElement, DocumentPage, ElementType, ParsedDocument
from openxml_parser.domain.value_objects import BBox


def _el(
    element_id: str,
    *,
    x: float,
    y: float,
    element_type: ElementType = ElementType.TEXT,
    text: str | None = None,
    metadata: dict[str, object] | None = None,
) -> DocumentElement:
    return DocumentElement(
        element_id=element_id,
        element_type=element_type,
        page_number=1,
        z_order=1,
        bbox=BBox(x=x, y=y, width=0.1, height=0.05),
        text=text,
        metadata=metadata or {},
    )


def test_order_page_elements_top_to_bottom_then_left_to_right() -> None:
    page = DocumentPage(
        page_number=1,
        width=1.0,
        height=1.0,
        elements=[
            _el("B", x=0.7, y=0.1, text="B"),
            _el("A", x=0.1, y=0.1, text="A"),
            _el("C", x=0.2, y=0.3, text="C"),
        ],
    )
    ordered = order_page_elements(page)
    assert [e.element_id for e in ordered] == ["A", "B", "C"]


def test_render_markdown_renders_title_text_image_and_table() -> None:
    table_meta = {
        "table_cells": [
            {"row": 0, "col": 0, "text": "H1", "is_spanned": False, "span_width": 1, "span_height": 1},
            {"row": 0, "col": 1, "text": "H2", "is_spanned": False, "span_width": 1, "span_height": 1},
            {"row": 1, "col": 0, "text": "A", "is_spanned": False, "span_width": 1, "span_height": 1},
            {"row": 1, "col": 1, "text": "B", "is_spanned": False, "span_width": 1, "span_height": 1},
        ]
    }
    page = DocumentPage(
        page_number=1,
        width=1.0,
        height=1.0,
        elements=[
            _el("T1", x=0.1, y=0.1, text="문서 제목", metadata={"is_placeholder": True}),
            _el("TXT", x=0.1, y=0.2, text="본문 내용"),
            _el("IMG", x=0.1, y=0.3, element_type=ElementType.IMAGE, metadata={"image": {"filename": "img.png"}}),
            _el("TB1", x=0.1, y=0.4, element_type=ElementType.TABLE, metadata=table_meta),
        ],
    )
    md = render_markdown(ParsedDocument(source_path="x.pptx", pages=[page]))

    assert "# 문서 제목" in md
    assert "본문 내용" in md
    assert '<img src="img.png" alt="IMG"/>' in md
    assert "<table>" in md
    assert "<thead>" in md
    assert "<th>H1</th>" in md
    assert "<td>A</td>" in md


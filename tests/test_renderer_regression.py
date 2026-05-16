"""Regression tests for markdown_renderer.py.

Covers: colgroup, header-rowspan expansion, absorbed element
before/after ordering, and column-break markers.
"""
from __future__ import annotations

from openxml_parser.application.config import ParserConfig
from openxml_parser.application.markdown_renderer import (
    _col_width_percentages,
    _group_separator,
    _infer_header_rows,
    render_markdown,
)
from openxml_parser.domain.entities import (
    DocumentElement,
    DocumentPage,
    ElementType,
    ParsedDocument,
)
from openxml_parser.domain.value_objects import BBox


def _el(
    eid: str,
    *,
    etype: ElementType = ElementType.TEXT,
    bbox: BBox | None = None,
    text: str | None = None,
    metadata: dict | None = None,
) -> DocumentElement:
    return DocumentElement(
        element_id=eid,
        element_type=etype,
        page_number=1,
        z_order=1,
        bbox=bbox or BBox(x=0, y=0, width=0.1, height=0.1),
        text=text,
        metadata=metadata or {},
    )


# -------------------------------------------------------------------
# colgroup / _col_width_percentages
# -------------------------------------------------------------------

class TestColWidthPercentages:
    def test_normal_widths(self):
        pcts = _col_width_percentages([1000, 3000])
        assert pcts is not None
        assert len(pcts) == 2
        assert abs(pcts[0] - 25.0) < 0.1
        assert abs(pcts[1] - 75.0) < 0.1

    def test_zero_total_returns_none(self):
        assert _col_width_percentages([0, 0, 0]) is None

    def test_negative_total_returns_none(self):
        assert _col_width_percentages([-100, -200]) is None

    def test_non_numeric_returns_none(self):
        assert _col_width_percentages(["abc", 100]) is None

    def test_empty_list_returns_none(self):
        assert _col_width_percentages([]) is None


class TestColgroupRendering:
    def test_colgroup_in_html_table(self):
        table = _el(
            "TB", etype=ElementType.TABLE, text="a | b",
            metadata={
                "table_col_widths": [3000, 1000],
                "table_cells": [
                    {"row": 0, "col": 0, "text": "A", "is_spanned": False,
                     "span_width": 1, "span_height": 1},
                    {"row": 0, "col": 1, "text": "B", "is_spanned": False,
                     "span_width": 1, "span_height": 1},
                ],
            },
        )
        page = DocumentPage(page_number=1, width=1, height=1, elements=[table])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
            config=ParserConfig(table_render_html=True),
        )
        assert "<colgroup>" in md
        assert 'style="width:75.0%"' in md
        assert 'style="width:25.0%"' in md

    def test_no_colgroup_when_widths_missing(self):
        table = _el(
            "TB", etype=ElementType.TABLE, text="a | b",
            metadata={
                "table_cells": [
                    {"row": 0, "col": 0, "text": "A", "is_spanned": False,
                     "span_width": 1, "span_height": 1},
                ],
            },
        )
        page = DocumentPage(page_number=1, width=1, height=1, elements=[table])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
            config=ParserConfig(table_render_html=True),
        )
        assert "<colgroup>" not in md


# -------------------------------------------------------------------
# Header rowspan expansion
# -------------------------------------------------------------------

class TestHeaderRowspanExpansion:
    def test_rowspan2_puts_both_rows_in_thead(self):
        by_row = {
            0: [
                {"row": 0, "col": 0, "text": "Title", "is_spanned": False,
                 "span_width": 2, "span_height": 2, "is_merge_origin": True},
                {"row": 0, "col": 2, "text": "H1", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
            ],
            1: [
                {"row": 1, "col": 2, "text": "H2", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
            ],
            2: [
                {"row": 2, "col": 0, "text": "D1", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
                {"row": 2, "col": 1, "text": "D2", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
                {"row": 2, "col": 2, "text": "D3", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
            ],
        }
        header = _infer_header_rows(by_row, max_row=2)
        assert 0 in header
        assert 1 in header
        assert 2 not in header

    def test_no_rowspan_keeps_single_header(self):
        by_row = {
            0: [
                {"row": 0, "col": 0, "text": "H1", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
            ],
            1: [
                {"row": 1, "col": 0, "text": "D1", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
            ],
        }
        header = _infer_header_rows(by_row, max_row=1)
        assert header == {0}

    def test_rowspan_exceeds_table_rows(self):
        """rowspan=5 but table only has 2 rows."""
        by_row = {
            0: [
                {"row": 0, "col": 0, "text": "Big", "is_spanned": False,
                 "span_width": 1, "span_height": 5},
            ],
            1: [
                {"row": 1, "col": 0, "text": "D", "is_spanned": False,
                 "span_width": 1, "span_height": 1},
            ],
        }
        header = _infer_header_rows(by_row, max_row=1)
        assert 0 in header
        assert 1 in header

    def test_rendered_html_rowspan_in_thead(self):
        """Verify the actual HTML puts both rows in <thead>."""
        table = _el(
            "TB", etype=ElementType.TABLE, text="",
            metadata={
                "table_cells": [
                    {"row": 0, "col": 0, "text": "Title",
                     "is_spanned": False, "span_width": 2, "span_height": 2,
                     "is_merge_origin": True},
                    {"row": 0, "col": 1, "text": None, "is_spanned": True,
                     "span_width": 1, "span_height": 1},
                    {"row": 0, "col": 2, "text": "H1",
                     "is_spanned": False, "span_width": 1, "span_height": 1},
                    {"row": 1, "col": 0, "text": None, "is_spanned": True,
                     "span_width": 1, "span_height": 1},
                    {"row": 1, "col": 1, "text": None, "is_spanned": True,
                     "span_width": 1, "span_height": 1},
                    {"row": 1, "col": 2, "text": "Sub",
                     "is_spanned": False, "span_width": 1, "span_height": 1},
                    {"row": 2, "col": 0, "text": "A",
                     "is_spanned": False, "span_width": 1, "span_height": 1},
                    {"row": 2, "col": 1, "text": "B",
                     "is_spanned": False, "span_width": 1, "span_height": 1},
                    {"row": 2, "col": 2, "text": "C",
                     "is_spanned": False, "span_width": 1, "span_height": 1},
                ],
            },
        )
        page = DocumentPage(page_number=1, width=1, height=1, elements=[table])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
            config=ParserConfig(table_render_html=True),
        )
        thead_start = md.index("<thead>")
        thead_end = md.index("</thead>")
        tbody_start = md.index("<tbody>")
        thead_section = md[thead_start:thead_end]
        tbody_section = md[tbody_start:]

        assert thead_section.count("<tr>") == 2
        assert "Sub" in thead_section
        assert "A" in tbody_section
        assert "Sub" not in tbody_section


# -------------------------------------------------------------------
# Absorbed element before/after ordering
# -------------------------------------------------------------------

class TestAbsorbedElementOrdering:
    def test_header_above_midpoint_rendered_before_base(self):
        """Absorbed element near cell top should appear before base text."""
        table = _el(
            "TB", etype=ElementType.TABLE, text="",
            metadata={
                "table_cells": [
                    {
                        "row": 0, "col": 0, "text": "본문 내용",
                        "is_spanned": False, "span_width": 1, "span_height": 1,
                        "cell_bbox": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                        "absorbed_elements": [
                            {"element_id": "H1", "type": "text",
                             "content": "섹션헤더", "y": 0.1, "x": 0.1},
                        ],
                    },
                ],
            },
        )
        page = DocumentPage(page_number=1, width=1, height=1, elements=[table])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
            config=ParserConfig(table_render_html=True),
        )
        assert md.index("섹션헤더") < md.index("본문 내용")

    def test_footer_below_midpoint_rendered_after_base(self):
        """Absorbed element near cell bottom should appear after base text."""
        table = _el(
            "TB", etype=ElementType.TABLE, text="",
            metadata={
                "table_cells": [
                    {
                        "row": 0, "col": 0, "text": "본문",
                        "is_spanned": False, "span_width": 1, "span_height": 1,
                        "cell_bbox": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                        "absorbed_elements": [
                            {"element_id": "F1", "type": "text",
                             "content": "푸터", "y": 0.9, "x": 0.1},
                        ],
                    },
                ],
            },
        )
        page = DocumentPage(page_number=1, width=1, height=1, elements=[table])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
            config=ParserConfig(table_render_html=True),
        )
        assert md.index("본문") < md.index("푸터")

    def test_no_cell_bbox_falls_back_to_after(self):
        """Without cell_bbox, all absorbed go after base text."""
        table = _el(
            "TB", etype=ElementType.TABLE, text="",
            metadata={
                "table_cells": [
                    {
                        "row": 0, "col": 0, "text": "기본",
                        "is_spanned": False, "span_width": 1, "span_height": 1,
                        "absorbed_elements": [
                            {"element_id": "X", "type": "text",
                             "content": "흡수됨", "y": 0.01, "x": 0.01},
                        ],
                    },
                ],
            },
        )
        page = DocumentPage(page_number=1, width=1, height=1, elements=[table])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
            config=ParserConfig(table_render_html=True),
        )
        assert md.index("기본") < md.index("흡수됨")


# -------------------------------------------------------------------
# Column-break / spatial_group
# -------------------------------------------------------------------

class TestColumnBreak:
    def test_vertical_split_produces_column_break(self):
        e1 = _el("A", text="왼쪽", metadata={"spatial_group": "0.v0"})
        e2 = _el("B", text="오른쪽", metadata={"spatial_group": "0.v1"})
        page = DocumentPage(page_number=1, width=1, height=1, elements=[e1, e2])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
        )
        assert "<!-- column-break -->" in md

    def test_horizontal_split_no_column_break(self):
        e1 = _el("A", text="위", metadata={"spatial_group": "0.h0"})
        e2 = _el("B", text="아래", metadata={"spatial_group": "0.h1"})
        page = DocumentPage(page_number=1, width=1, height=1, elements=[e1, e2])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
        )
        assert "<!-- column-break -->" not in md

    def test_same_group_no_separator(self):
        e1 = _el("A", text="하나", metadata={"spatial_group": "0.v0"})
        e2 = _el("B", text="둘", metadata={"spatial_group": "0.v0"})
        page = DocumentPage(page_number=1, width=1, height=1, elements=[e1, e2])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
        )
        assert "<!-- column-break -->" not in md

    def test_integer_spatial_group_no_crash(self):
        """Non-string spatial_group should not crash."""
        e1 = _el("A", text="하나", metadata={"spatial_group": 1})
        e2 = _el("B", text="둘", metadata={"spatial_group": 2})
        page = DocumentPage(page_number=1, width=1, height=1, elements=[e1, e2])
        md = render_markdown(
            ParsedDocument(source_path="t.pptx", pages=[page]),
        )
        assert "하나" in md
        assert "둘" in md


class TestGroupSeparatorUnit:
    def test_v_divergence(self):
        assert _group_separator("0.h0.v0", "0.h0.v1") == "<!-- column-break -->"

    def test_h_divergence(self):
        assert _group_separator("0.h0", "0.h1") is None

    def test_identical(self):
        assert _group_separator("0.v0", "0.v0") is None

    def test_prefix_subset(self):
        assert _group_separator("0.v0.h1", "0.v0") is None

"""Tests for text formatting extraction (bold, italic, underline)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from document_inteligence.infrastructure.ingestors.pptx_table_xml import (
    NS,
    paragraphs_with_formatting,
    _wrap_run,
    _RunStyle,
    _parse_run_style,
    _detect_dominant_style,
    _merge_adjacent_runs,
)


def _make_rPr(**attrs) -> ET.Element:
    return ET.fromstring(
        '<a:rPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        + " ".join(f'{k}="{v}"' for k, v in attrs.items())
        + "/>"
    )


class TestWrapRun:
    def test_bold_markdown(self):
        assert _wrap_run("hello", _RunStyle(bold=True), "markdown") == "**hello**"

    def test_italic_markdown(self):
        assert _wrap_run("hello", _RunStyle(italic=True), "markdown") == "*hello*"

    def test_underline_markdown(self):
        assert _wrap_run("hello", _RunStyle(underline=True), "markdown") == "<u>hello</u>"

    def test_bold_italic_markdown(self):
        assert _wrap_run("hello", _RunStyle(bold=True, italic=True), "markdown") == "***hello***"

    def test_all_three_markdown(self):
        s = _RunStyle(bold=True, italic=True, underline=True)
        assert _wrap_run("hello", s, "markdown") == "***<u>hello</u>***"

    def test_bold_html(self):
        assert _wrap_run("hello", _RunStyle(bold=True), "html") == "<b>hello</b>"

    def test_italic_html(self):
        assert _wrap_run("hello", _RunStyle(italic=True), "html") == "<i>hello</i>"

    def test_no_formatting(self):
        assert _wrap_run("hello", _RunStyle(), "markdown") == "hello"


class TestParseRunStyle:
    def test_bold(self):
        rPr = _make_rPr(b="1")
        assert _parse_run_style(rPr) == _RunStyle(bold=True)

    def test_italic(self):
        rPr = _make_rPr(i="1")
        assert _parse_run_style(rPr) == _RunStyle(italic=True)

    def test_underline(self):
        rPr = _make_rPr(u="sng")
        assert _parse_run_style(rPr) == _RunStyle(underline=True)

    def test_none(self):
        assert _parse_run_style(None) == _RunStyle()


class TestDominantStyle:
    def test_all_bold_suppressed(self):
        runs = [("Hello", _RunStyle(bold=True)), ("World", _RunStyle(bold=True))]
        dom = _detect_dominant_style(runs)
        assert dom.bold is True
        assert dom.italic is False

    def test_mixed_bold_not_suppressed(self):
        runs = [
            ("Hello ", _RunStyle(bold=True)),
            ("this is a longer normal text segment", _RunStyle()),
        ]
        dom = _detect_dominant_style(runs)
        assert dom.bold is False

    def test_empty_runs(self):
        assert _detect_dominant_style([]) == _RunStyle()


class TestMergeAdjacentRuns:
    def test_same_style_merged(self):
        runs = [("A", _RunStyle(bold=True)), ("B", _RunStyle(bold=True))]
        merged = _merge_adjacent_runs(runs, _RunStyle())
        assert len(merged) == 1
        assert merged[0][0] == "AB"

    def test_different_style_not_merged(self):
        runs = [("A", _RunStyle(bold=True)), ("B", _RunStyle())]
        merged = _merge_adjacent_runs(runs, _RunStyle())
        assert len(merged) == 2

    def test_dominant_suppresses_then_merges(self):
        dom = _RunStyle(bold=True)
        runs = [("A", _RunStyle(bold=True)), ("B", _RunStyle(bold=True))]
        merged = _merge_adjacent_runs(runs, dom)
        assert len(merged) == 1
        assert merged[0][1] == _RunStyle()


class TestParagraphsWithFormatting:
    def test_single_bold_run_dominant_suppressed(self):
        xml = (
            '<root xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:p><a:r><a:rPr b="1"/><a:t>Bold</a:t></a:r></a:p>'
            "</root>"
        )
        root = ET.fromstring(xml)
        ps = root.findall("a:p", NS)
        result = paragraphs_with_formatting(ps, NS, mode="markdown")
        assert result == "Bold"

    def test_mixed_runs_bold_minority_preserved(self):
        xml = (
            '<root xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:p>'
            '<a:r><a:rPr/><a:t>Normal text that is longer than </a:t></a:r>'
            '<a:r><a:rPr b="1"/><a:t>Bold</a:t></a:r>'
            '</a:p>'
            "</root>"
        )
        root = ET.fromstring(xml)
        ps = root.findall("a:p", NS)
        result = paragraphs_with_formatting(ps, NS, mode="markdown")
        assert result == "Normal text that is longer than **Bold**"

    def test_html_mode_italic_minority(self):
        xml = (
            '<root xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:p>'
            '<a:r><a:rPr/><a:t>Normal text that is much longer </a:t></a:r>'
            '<a:r><a:rPr i="1"/><a:t>Italic</a:t></a:r>'
            '</a:p>'
            "</root>"
        )
        root = ET.fromstring(xml)
        ps = root.findall("a:p", NS)
        result = paragraphs_with_formatting(ps, NS, mode="html")
        assert result == "Normal text that is much longer <i>Italic</i>"

    def test_adjacent_bold_runs_merged(self):
        xml = (
            '<root xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:p>'
            '<a:r><a:rPr/><a:t>Start </a:t></a:r>'
            '<a:r><a:rPr b="1"/><a:t>A</a:t></a:r>'
            '<a:r><a:rPr b="1"/><a:t>B</a:t></a:r>'
            '<a:r><a:rPr/><a:t> End</a:t></a:r>'
            '</a:p>'
            "</root>"
        )
        root = ET.fromstring(xml)
        ps = root.findall("a:p", NS)
        result = paragraphs_with_formatting(ps, NS, mode="markdown")
        assert "****" not in result
        assert "**AB**" in result

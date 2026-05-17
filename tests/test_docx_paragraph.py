from __future__ import annotations

import xml.etree.ElementTree as ET

from openxml_parser.infrastructure.ingestors.docx_paragraph import paragraph_text_and_meta

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def test_run_inside_drawing_not_duplicated_as_paragraph_text() -> None:
    xml = f"""
    <w:p xmlns:w="{W_NS}"
         xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
      <w:r>
        <w:drawing>
          <wps:txbx>
            <w:txbxContent>
              <w:p><w:r><w:t>Inside box</w:t></w:r></w:p>
            </w:txbxContent>
          </wps:txbx>
        </w:drawing>
      </w:r>
    </w:p>
    """
    p = ET.fromstring(xml)
    text, _ = paragraph_text_and_meta(p)
    assert text == ""


def test_heading_and_list_metadata() -> None:
    xml = f"""
    <w:p xmlns:w="{W_NS}">
      <w:pPr>
        <w:pStyle w:val="Heading2"/>
        <w:numPr><w:ilvl w:val="1"/></w:numPr>
      </w:pPr>
      <w:r><w:t>Title line</w:t></w:r>
    </w:p>
    """
    p = ET.fromstring(xml)
    text, meta = paragraph_text_and_meta(p)
    assert meta.get("is_heading") is True
    assert meta.get("heading_level") == 2
    assert meta.get("is_list_item") is True
    assert meta.get("outline_inferred") is None
    assert text.endswith("Title line")
    assert text.startswith("  - ")


def test_bracket_line_records_passive_pattern_only() -> None:
    xml = f"""
    <w:p xmlns:w="{W_NS}">
      <w:r><w:rPr><w:b/></w:rPr><w:t>[Sample Project]2025.01-2025.02</w:t></w:r>
    </w:p>
    """
    p = ET.fromstring(xml)
    text, meta = paragraph_text_and_meta(p)
    assert meta.get("outline_inferred") is None
    assert meta.get("is_heading") is not True
    assert meta.get("line_pattern") == "bracket_leading"
    assert meta.get("formatted_text") == "**[Sample Project]2025.01-2025.02**"
    assert "[Sample Project]" in text


def test_bracket_line_with_slash_keeps_pattern_not_heading() -> None:
    xml = f"""
    <w:p xmlns:w="{W_NS}">
      <w:r><w:t>[O社 KPI 분석/보고서]2025.10</w:t></w:r>
    </w:p>
    """
    _, meta = paragraph_text_and_meta(ET.fromstring(xml))
    assert meta.get("line_pattern") == "bracket_leading"
    assert meta.get("outline_inferred") is None
    assert meta.get("is_heading") is not True


def test_bold_short_label_gets_formatted_text_not_heading() -> None:
    xml = f"""
    <w:p xmlns:w="{W_NS}">
      <w:r><w:rPr><w:b/></w:rPr><w:t>성과</w:t></w:r>
    </w:p>
    """
    _, meta = paragraph_text_and_meta(ET.fromstring(xml))
    assert meta.get("is_mostly_bold") is True
    assert meta.get("formatted_text") == "**성과**"
    assert meta.get("outline_inferred") is None
    assert meta.get("is_heading") is not True


def test_author_line_not_heading() -> None:
    xml = f'<w:p xmlns:w="{W_NS}"><w:r><w:rPr><w:b/></w:rPr><w:t>제1저자, IEEE Access, 2025</w:t></w:r></w:p>'
    p = ET.fromstring(xml)
    _, meta = paragraph_text_and_meta(p)
    assert meta.get("is_heading") is not True
    assert meta.get("outline_inferred") is None

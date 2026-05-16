from __future__ import annotations

import xml.etree.ElementTree as ET

from document_inteligence.infrastructure.ingestors.docx_paragraph import paragraph_text_and_meta

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
    assert text.endswith("Title line")
    assert text.startswith("  - ")

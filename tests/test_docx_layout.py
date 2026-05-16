from __future__ import annotations

import xml.etree.ElementTree as ET

from openxml_parser.infrastructure.ingestors.docx_layout import (
    LayoutCursor,
    drawing_bbox,
    paragraph_flow_bbox,
    parse_page_metrics,
    split_body_sections,
    table_flow_bbox,
    textbox_text,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = {
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
WPS_NS = {
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "w": W_NS,
}


def test_parse_page_metrics_from_sect_pr() -> None:
    xml = f"""
    <w:sectPr xmlns:w="{W_NS}">
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/>
    </w:sectPr>
    """
    metrics = parse_page_metrics(ET.fromstring(xml))
    assert metrics.page_width_twips == 12240
    assert metrics.margin_top_twips == 720
    assert 0.0 < metrics.margin_top_norm < 0.1


def test_split_body_sections_at_sect_pr() -> None:
    body_xml = f"""
    <w:body xmlns:w="{W_NS}">
      <w:p><w:r><w:t>Page1</w:t></w:r></w:p>
      <w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>
      <w:p><w:r><w:t>Page2</w:t></w:r></w:p>
    </w:body>
    """
    body = ET.fromstring(body_xml)
    sections = split_body_sections(body)
    assert len(sections) == 2
    assert len(sections[0][0]) == 1
    assert sections[0][1] is not None


def test_floating_anchor_bbox_uses_page_coordinates() -> None:
    metrics = parse_page_metrics(
        ET.fromstring(
            f'<w:sectPr xmlns:w="{W_NS}"><w:pgSz w:w="12240" w:h="15840"/>'
            f'<w:pgMar w:left="0" w:right="0" w:top="0" w:bottom="0"/></w:sectPr>'
        )
    )
    drawing_xml = f"""
    <w:drawing xmlns:w="{W_NS}" xmlns:wp="{WP_NS["wp"]}" xmlns:a="{WP_NS["a"]}"
               xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <wp:anchor>
        <wp:positionH relativeFrom="page"><wp:posOffset>914400</wp:posOffset></wp:positionH>
        <wp:positionV relativeFrom="page"><wp:posOffset>1828800</wp:posOffset></wp:positionV>
        <wp:extent cx="1828800" cy="914400"/>
      </wp:anchor>
    </w:drawing>
    """
    drawing = ET.fromstring(drawing_xml)
    fallback = paragraph_flow_bbox(
        ET.fromstring(f'<w:p xmlns:w="{W_NS}"><w:r><w:t>x</w:t></w:r></w:p>'),
        metrics,
        LayoutCursor(y=0.1),
    )
    bbox = drawing_bbox(drawing, metrics, fallback=fallback)
    assert bbox.x > 0.05
    assert bbox.y > 0.1
    assert bbox.width > 0.05


def test_textbox_text_extraction() -> None:
    xml = f"""
    <w:drawing xmlns:w="{W_NS}" xmlns:wps="{WPS_NS["wps"]}">
      <wps:wsp>
        <wps:txbx>
          <w:txbxContent>
            <w:p><w:r><w:t>Box label</w:t></w:r></w:p>
          </w:txbxContent>
        </wps:txbx>
      </wps:wsp>
    </w:drawing>
    """
    assert textbox_text(ET.fromstring(xml)) == "Box label"


def test_table_flow_advances_cursor() -> None:
    metrics = parse_page_metrics(None)
    cursor = LayoutCursor(y=0.1)
    bbox = table_flow_bbox(3, metrics, cursor)
    assert bbox.height > 0.05
    assert cursor.y > 0.1

from __future__ import annotations

import xml.etree.ElementTree as ET

from document_inteligence.infrastructure.ingestors.pptx_table_xml import NS, _parse_table


def test_parse_table_handles_gridspan_and_vmerge() -> None:
    xml = """
    <a:tbl xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
      <a:tblGrid>
        <a:gridCol w="1000"/>
        <a:gridCol w="1000"/>
      </a:tblGrid>
      <a:tr h="500">
        <a:tc gridSpan="2" rowSpan="2">
          <a:txBody><a:p><a:r><a:t>HEADER</a:t></a:r></a:p></a:txBody>
        </a:tc>
      </a:tr>
      <a:tr h="500">
        <a:tc vMerge="1"><a:txBody><a:p/></a:txBody></a:tc>
        <a:tc vMerge="1"><a:txBody><a:p/></a:txBody></a:tc>
      </a:tr>
    </a:tbl>
    """
    root = ET.fromstring(xml)
    parsed = _parse_table(root)

    assert len(parsed.col_widths) == 2
    assert len(parsed.row_heights) == 2
    assert len(parsed.cells) == 4

    origin = next(c for c in parsed.cells if c.row == 0 and c.col == 0)
    assert origin.text == "HEADER"
    assert origin.is_merge_origin is True
    assert origin.span_width == 2
    assert origin.span_height == 2

    covered = next(c for c in parsed.cells if c.row == 1 and c.col == 1)
    assert covered.is_spanned is True


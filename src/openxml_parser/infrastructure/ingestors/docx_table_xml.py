from __future__ import annotations

import xml.etree.ElementTree as ET

from openxml_parser.infrastructure.ingestors.pptx_table_xml import (
    ParsedTable,
    ParsedTableCell,
    _MERGE_CONTINUE_VALUES,
)
from openxml_parser.infrastructure.ingestors._ooxml_utils import text_content

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def parse_word_table(tbl: ET.Element) -> ParsedTable:
    col_widths = _word_col_widths(tbl)
    rows = tbl.findall("w:tr", W_NS)
    row_heights = [1.0 for _ in rows]
    col_count = max(len(col_widths), 1)
    if not col_widths:
        col_widths = [1.0 for _ in range(col_count)]

    cells: list[ParsedTableCell] = []
    occupied: dict[tuple[int, int], bool] = {}

    for r_idx, tr in enumerate(rows):
        c_idx = 0
        for tc in tr.findall("w:tc", W_NS):
            while (r_idx, c_idx) in occupied:
                c_idx += 1
            grid_span = _word_grid_span(tc)
            row_span = _word_row_span(tc)
            vmerge = _word_vmerge(tc)
            is_continue = vmerge in _MERGE_CONTINUE_VALUES

            text = _word_cell_text(tc)
            for dr in range(row_span):
                for dc in range(grid_span):
                    rr, cc = r_idx + dr, c_idx + dc
                    is_origin = dr == 0 and dc == 0 and not is_continue
                    is_spanned = (dr > 0 or dc > 0 or is_continue) and not is_origin
                    if is_continue and dr == 0 and dc == 0:
                        is_spanned = True
                        is_origin = False
                    cells.append(
                        ParsedTableCell(
                            row=rr,
                            col=cc,
                            text=text if is_origin else None,
                            is_spanned=is_spanned,
                            span_width=grid_span if is_origin else 1,
                            span_height=row_span if is_origin else 1,
                            is_merge_origin=is_origin,
                        )
                    )
                    occupied[(rr, cc)] = True
            c_idx += grid_span

    return ParsedTable(col_widths=col_widths, row_heights=row_heights, cells=cells)


def _word_col_widths(tbl: ET.Element) -> list[float]:
    out: list[float] = []
    grid = tbl.find("w:tblGrid", W_NS)
    if grid is None:
        return out
    for col in grid.findall("w:gridCol", W_NS):
        w = col.get(f"{{{W_NS['w']}}}w") or col.get("w")
        try:
            out.append(float(w) if w else 1.0)
        except ValueError:
            out.append(1.0)
    return out


def _word_grid_span(tc: ET.Element) -> int:
    tc_pr = tc.find("w:tcPr", W_NS)
    if tc_pr is None:
        return 1
    val = tc_pr.get(f"{{{W_NS['w']}}}gridSpan") or tc_pr.get("gridSpan")
    return int(val) if val else 1


def _word_row_span(tc: ET.Element) -> int:
    tc_pr = tc.find("w:tcPr", W_NS)
    if tc_pr is None:
        return 1
    val = tc_pr.get(f"{{{W_NS['w']}}}rowSpan") or tc_pr.get("rowSpan")
    return int(val) if val else 1


def _word_vmerge(tc: ET.Element) -> str | None:
    tc_pr = tc.find("w:tcPr", W_NS)
    if tc_pr is None:
        return None
    el = tc_pr.find("w:vMerge", W_NS)
    if el is None:
        return None
    return el.get(f"{{{W_NS['w']}}}val") or el.get("val") or "continue"


def _word_cell_text(tc: ET.Element) -> str | None:
    paragraphs = tc.findall(".//w:p", W_NS)
    if not paragraphs:
        return None
    lines = [text_content(p, ns=W_NS) for p in paragraphs]
    lines = [ln for ln in lines if ln]
    joined = "\n".join(lines).strip()
    return joined or None

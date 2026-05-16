from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from document_inteligence.domain.entities import (
    DocumentElement,
    DocumentPage,
    ElementType,
    ParsedDocument,
)
from document_inteligence.domain.repositories import DocumentIngestor
from document_inteligence.infrastructure.ingestors._ooxml_utils import synthetic_bbox


class XlsxIngestor(DocumentIngestor):
    def supports(self, path: str) -> bool:
        return Path(path).suffix.lower() in {".xlsx", ".xlsm", ".xltx", ".xltm"}

    def ingest(self, path: str) -> ParsedDocument:
        wb = load_workbook(path, data_only=True, read_only=False)
        pages: list[DocumentPage] = []

        for page_idx, sheet_name in enumerate(wb.sheetnames, start=1):
            ws = wb[sheet_name]
            elements = _sheet_to_elements(ws, page_number=page_idx, sheet_name=sheet_name)
            pages.append(
                DocumentPage(
                    page_number=page_idx,
                    width=1.0,
                    height=1.0,
                    elements=elements,
                    metadata={
                        "source_format": "xlsx",
                        "sheet_name": sheet_name,
                        "layout_mode": "grid",
                    },
                )
            )
        wb.close()
        return ParsedDocument(source_path=str(path), pages=pages)


def _sheet_to_elements(ws, *, page_number: int, sheet_name: str) -> list[DocumentElement]:
    if ws.max_row is None or ws.max_column is None:
        return []

    max_row = ws.max_row or 1
    max_col = ws.max_column or 1
    merged_map = _build_merged_cell_map(ws)

    cells_meta: list[dict[str, object]] = []
    matrix_text: list[list[str]] = []

    for r in range(1, max_row + 1):
        row_vals: list[str] = []
        for c in range(1, max_col + 1):
            key = (r - 1, c - 1)
            info = merged_map.get(key)
            if info and info.get("is_spanned"):
                row_vals.append("")
                cells_meta.append(
                    {
                        "row": r - 1,
                        "col": c - 1,
                        "text": None,
                        "is_spanned": True,
                        "span_width": 1,
                        "span_height": 1,
                        "is_merge_origin": False,
                    }
                )
                continue

            value = ws.cell(row=r, column=c).value
            text = _cell_display(value)
            row_vals.append(text)

            span_w, span_h = 1, 1
            is_origin = True
            if info:
                span_w = int(info.get("span_width", 1))
                span_h = int(info.get("span_height", 1))
                is_origin = bool(info.get("is_origin", True))

            cells_meta.append(
                {
                    "row": r - 1,
                    "col": c - 1,
                    "text": text or None,
                    "is_spanned": False,
                    "span_width": span_w,
                    "span_height": span_h,
                    "is_merge_origin": is_origin,
                }
            )
        matrix_text.append(row_vals)

    pipe_lines = [" | ".join(row) for row in matrix_text if any(cell.strip() for cell in row)]
    pipe_text = "\n".join(pipe_lines) if pipe_lines else None

    col_widths = [1.0 for _ in range(max_col)]
    row_heights = [1.0 for _ in range(max_row)]

    return [
        DocumentElement(
            element_id=f"E_{page_number:03d}_0001",
            element_type=ElementType.TABLE,
            page_number=page_number,
            z_order=1,
            bbox=synthetic_bbox(0, row_height=0.9),
            text=pipe_text,
            metadata={
                "source_format": "xlsx",
                "sheet_name": sheet_name,
                "table_col_widths": col_widths,
                "table_row_heights": row_heights,
                "table_cells": cells_meta,
            },
        )
    ]


def _cell_display(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _build_merged_cell_map(ws) -> dict[tuple[int, int], dict[str, object]]:
    out: dict[tuple[int, int], dict[str, object]] = {}
    for merged in ws.merged_cells.ranges:
        min_row, min_col = merged.min_row - 1, merged.min_col - 1
        max_row, max_col = merged.max_row - 1, merged.max_col - 1
        span_w = max_col - min_col + 1
        span_h = max_row - min_row + 1
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                is_origin = r == min_row and c == min_col
                out[(r, c)] = {
                    "is_spanned": not is_origin,
                    "is_origin": is_origin,
                    "span_width": span_w if is_origin else 1,
                    "span_height": span_h if is_origin else 1,
                }
    return out

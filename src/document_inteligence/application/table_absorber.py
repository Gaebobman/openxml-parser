from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.domain.entities import DocumentElement, DocumentPage, ElementType


def absorb_overlapping_elements(page: DocumentPage, config: ParserConfig) -> None:
    tables = [e for e in page.elements if e.element_type == ElementType.TABLE]
    if not tables:
        return

    tables_by_area = sorted(tables, key=lambda t: t.bbox.width * t.bbox.height, reverse=True)

    candidates = [
        e for e in page.elements
        if e.element_type != ElementType.GROUP
        and not bool(e.metadata.get("absorbed_by"))
    ]
    for table in tables_by_area:
        if bool(table.metadata.get("absorbed_by_table")):
            continue
        cells = _table_cells_with_bbox(table)
        if not cells:
            continue
        for candidate in candidates:
            if candidate.element_id == table.element_id:
                continue
            if bool(candidate.metadata.get("absorbed_by_table")):
                continue
            best_idx, best_ratio = _best_cell_match(candidate, cells)
            if best_idx < 0 or best_ratio < config.table_cell_containment_threshold:
                continue
            _attach_candidate_to_cell(table, cells[best_idx], candidate, best_ratio)
            candidate.metadata["absorbed_by_table"] = True
            candidate.metadata["absorbed_into_table_id"] = table.element_id


def _table_cells_with_bbox(table: DocumentElement) -> list[dict[str, object]]:
    raw = table.metadata.get("table_cells")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, object]] = []
    for cell in raw:
        if not isinstance(cell, dict):
            continue
        bbox = cell.get("cell_bbox")
        if not isinstance(bbox, dict):
            continue
        if bool(cell.get("is_spanned")):
            continue
        out.append(cell)
    return out


def _best_cell_match(candidate: DocumentElement, cells: list[dict[str, object]]) -> tuple[int, float]:
    best_idx = -1
    best_ratio = 0.0
    for idx, cell in enumerate(cells):
        cell_bbox = cell.get("cell_bbox")
        if not isinstance(cell_bbox, dict):
            continue
        ratio = bbox_containment_ratio(
            inner=candidate.bbox.__dict__,
            outer=cell_bbox,
        )
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = idx
    return best_idx, best_ratio


def bbox_containment_ratio(*, inner: dict[str, float], outer: dict[str, float]) -> float:
    """Return fraction of *inner* area that overlaps with *outer*."""
    ax1 = float(inner.get("x", 0.0))
    ay1 = float(inner.get("y", 0.0))
    ax2 = ax1 + float(inner.get("width", 0.0))
    ay2 = ay1 + float(inner.get("height", 0.0))

    bx1 = float(outer.get("x", 0.0))
    by1 = float(outer.get("y", 0.0))
    bx2 = bx1 + float(outer.get("width", 0.0))
    by2 = by1 + float(outer.get("height", 0.0))

    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    intersection = inter_w * inter_h
    if intersection <= 0.0:
        return 0.0

    area_inner = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    if area_inner <= 0.0:
        return 0.0
    return intersection / area_inner


def _attach_candidate_to_cell(
    table: DocumentElement,
    cell: dict[str, object],
    candidate: DocumentElement,
    containment: float,
) -> None:
    absorbed = cell.get("absorbed_elements")
    if not isinstance(absorbed, list):
        absorbed = []
        cell["absorbed_elements"] = absorbed

    entry: dict[str, object] = {
        "element_id": candidate.element_id,
        "type": candidate.element_type.value,
        "content": _candidate_content(candidate),
        "containment": containment,
        "y": candidate.bbox.y,
        "x": candidate.bbox.x,
    }
    if candidate.element_type == ElementType.IMAGE:
        image_meta = candidate.metadata.get("image")
        if isinstance(image_meta, dict):
            w = int(image_meta.get("display_width_px", 0))
            if w > 0:
                entry["display_width_px"] = w
    absorbed.append(entry)

    table.metadata["has_absorbed_elements"] = True


def _candidate_content(candidate: DocumentElement) -> str:
    if candidate.element_type == ElementType.IMAGE:
        image_meta = candidate.metadata.get("image")
        if isinstance(image_meta, dict):
            ref = image_meta.get("relative_path") or image_meta.get("filename")
            if isinstance(ref, str) and ref:
                return f"![{candidate.element_id}]({ref})"
        return f"![{candidate.element_id}](image-not-exported)"
    if candidate.element_type == ElementType.TABLE:
        return _nested_table_html(candidate)
    return (candidate.text or "").strip()


def _nested_table_html(table_el: DocumentElement) -> str:
    raw_cells = table_el.metadata.get("table_cells")
    if not isinstance(raw_cells, list) or not raw_cells:
        return (table_el.text or "").strip()

    usable = [c for c in raw_cells if isinstance(c, dict) and not bool(c.get("is_spanned"))]
    if not usable:
        return (table_el.text or "").strip()

    max_row = max(int(c.get("row", 0)) for c in usable)
    by_row: dict[int, list[dict[str, object]]] = {}
    for c in usable:
        r = int(c.get("row", 0))
        by_row.setdefault(r, []).append(c)
    for row_cells in by_row.values():
        row_cells.sort(key=lambda c: int(c.get("col", 0)))

    lines: list[str] = ["<table>"]
    for row_idx in range(max_row + 1):
        cells = by_row.get(row_idx, [])
        parts = ["<tr>"]
        for c in cells:
            attrs: list[str] = []
            cs = int(c.get("span_width", 1))
            rs = int(c.get("span_height", 1))
            if cs > 1:
                attrs.append(f'colspan="{cs}"')
            if rs > 1:
                attrs.append(f'rowspan="{rs}"')
            attr_text = (" " + " ".join(attrs)) if attrs else ""
            text = str(c.get("text") or "").strip()
            parts.append(f"<td{attr_text}>{text}</td>")
        parts.append("</tr>")
        lines.append("".join(parts))
    lines.append("</table>")
    return "\n".join(lines)

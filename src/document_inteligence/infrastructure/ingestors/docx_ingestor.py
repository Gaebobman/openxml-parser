from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from document_inteligence.domain.entities import (
    DocumentElement,
    DocumentPage,
    ElementType,
    ParsedDocument,
)
from document_inteligence.domain.repositories import DocumentIngestor
from document_inteligence.domain.value_objects import BBox
from document_inteligence.infrastructure.ingestors._ooxml_utils import (
    local_name,
    read_zip_xml,
    text_content,
)
from document_inteligence.infrastructure.ingestors.docx_layout import (
    LayoutCursor,
    anchor_z_order,
    default_page_metrics,
    drawing_bbox,
    paragraph_flow_bbox,
    parse_page_metrics,
    split_body_sections,
    table_flow_bbox,
    textbox_text,
)
from document_inteligence.infrastructure.ingestors.docx_paragraph import paragraph_text_and_meta
from document_inteligence.infrastructure.ingestors.docx_table_xml import parse_word_table

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
A_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
WP_NS = {"wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}
R_NS = {
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": W_NS["w"],
    "a": A_NS["a"],
}


def _table_cells_metadata(parsed_table, *, metrics, table_bbox: BBox) -> list[dict[str, object]]:
    cells: list[dict[str, object]] = []
    row_count = max((c.row for c in parsed_table.cells), default=0) + 1
    col_count = max((c.col for c in parsed_table.cells), default=0) + 1
    row_h_norm = table_bbox.height / max(row_count, 1)
    col_w_norm = table_bbox.width / max(col_count, 1)

    for cell in parsed_table.cells:
        if cell.is_spanned:
            cells.append(
                {
                    "row": cell.row,
                    "col": cell.col,
                    "text": cell.text,
                    "is_spanned": cell.is_spanned,
                    "span_width": cell.span_width,
                    "span_height": cell.span_height,
                    "is_merge_origin": cell.is_merge_origin,
                }
            )
            continue
        cell_bbox = {
            "x": table_bbox.x + cell.col * col_w_norm,
            "y": table_bbox.y + cell.row * row_h_norm,
            "width": col_w_norm * cell.span_width,
            "height": row_h_norm * cell.span_height,
        }
        cells.append(
            {
                "row": cell.row,
                "col": cell.col,
                "text": cell.text,
                "is_spanned": cell.is_spanned,
                "span_width": cell.span_width,
                "span_height": cell.span_height,
                "is_merge_origin": cell.is_merge_origin,
                "cell_bbox": cell_bbox,
            }
        )
    return cells


class DocxIngestor(DocumentIngestor):
    def __init__(self, asset_output_dir: str | None = None) -> None:
        self._asset_output_dir = Path(asset_output_dir) if asset_output_dir else None

    def supports(self, path: str) -> bool:
        return Path(path).suffix.lower() in {".docx", ".docm"}

    def ingest(self, path: str) -> ParsedDocument:
        docx_path = Path(path)
        with zipfile.ZipFile(docx_path) as zf:
            rels = _load_relationships(zf)
            body = read_zip_xml(zf, "word/document.xml")
            body_el = body.find("w:body", W_NS)
            if body_el is None:
                return ParsedDocument(source_path=str(docx_path), pages=[])

            sections = split_body_sections(body_el)
            pages: list[DocumentPage] = []
            for page_idx, (block_nodes, sect_pr) in enumerate(sections, start=1):
                metrics = parse_page_metrics(sect_pr)
                elements = _blocks_to_elements(
                    block_nodes,
                    page_number=page_idx,
                    metrics=metrics,
                    zf=zf,
                    rels=rels,
                    asset_output_dir=self._asset_output_dir,
                )
                pages.append(
                    DocumentPage(
                        page_number=page_idx,
                        width=1.0,
                        height=1.0,
                        elements=elements,
                        metadata={
                            "source_format": "docx",
                            "layout_mode": "page_metrics",
                            "page_width_twips": metrics.page_width_twips,
                            "page_height_twips": metrics.page_height_twips,
                        },
                    )
                )

        if not pages:
            metrics = default_page_metrics()
            pages = [
                DocumentPage(
                    page_number=1,
                    width=1.0,
                    height=1.0,
                    elements=[],
                    metadata={"source_format": "docx", "layout_mode": "page_metrics"},
                )
            ]
        return ParsedDocument(source_path=str(docx_path), pages=pages)


def _blocks_to_elements(
    nodes: list[ET.Element],
    *,
    page_number: int,
    metrics,
    zf: zipfile.ZipFile,
    rels: dict[str, str],
    asset_output_dir: Path | None,
) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    cursor = LayoutCursor(y=metrics.margin_top_norm)
    order = 0

    for node in nodes:
        tag = local_name(node.tag)
        order += 1
        eid = f"E_{page_number:03d}_{order:04d}"

        if tag == "p":
            flow_bbox = paragraph_flow_bbox(node, metrics, cursor)
            text, para_meta = paragraph_text_and_meta(node)
            drawings = node.findall(".//w:drawing", W_NS)

            if text:
                para_meta["layout"] = "flow"
                elements.append(
                    DocumentElement(
                        element_id=eid,
                        element_type=ElementType.TEXT,
                        page_number=page_number,
                        z_order=order,
                        bbox=flow_bbox,
                        text=text,
                        metadata=para_meta,
                    )
                )

            for draw in drawings:
                order += 1
                tb_text = textbox_text(draw)
                draw_bbox = drawing_bbox(draw, metrics, fallback=flow_bbox)
                z = anchor_z_order(draw, order)

                if tb_text:
                    elements.append(
                        DocumentElement(
                            element_id=f"E_{page_number:03d}_{order:04d}",
                            element_type=ElementType.TEXT,
                            page_number=page_number,
                            z_order=z,
                            bbox=draw_bbox,
                            text=tb_text,
                            metadata={
                                "source_format": "docx",
                                "layout": "floating_textbox",
                                "is_floating": True,
                            },
                        )
                    )
                    continue

                img = _extract_drawing_image(
                    draw,
                    zf=zf,
                    rels=rels,
                    page_number=page_number,
                    z_order=z,
                    asset_output_dir=asset_output_dir,
                    bbox=draw_bbox,
                )
                if img:
                    is_floating = draw.find(".//wp:anchor", WP_NS) is not None
                    img.metadata["layout"] = "floating" if is_floating else "inline"
                    img.metadata["is_floating"] = is_floating
                    elements.append(img)
            continue

        if tag == "tbl":
            rows = node.findall("w:tr", W_NS)
            tbl_bbox = table_flow_bbox(len(rows), metrics, cursor)
            parsed = parse_word_table(node)
            pipe_text = _table_plain_text(parsed)
            elements.append(
                DocumentElement(
                    element_id=eid,
                    element_type=ElementType.TABLE,
                    page_number=page_number,
                    z_order=order,
                    bbox=tbl_bbox,
                    text=pipe_text,
                    metadata={
                        "source_format": "docx",
                        "layout": "flow",
                        "table_col_widths": parsed.col_widths,
                        "table_row_heights": parsed.row_heights,
                        "table_cells": _table_cells_metadata(parsed, metrics=metrics, table_bbox=tbl_bbox),
                    },
                )
            )
            continue

        text = text_content(node, ns=W_NS)
        if text:
            flow_bbox = paragraph_flow_bbox(node, metrics, cursor)
            elements.append(
                DocumentElement(
                    element_id=eid,
                    element_type=ElementType.UNKNOWN,
                    page_number=page_number,
                    z_order=order,
                    bbox=flow_bbox,
                    text=text,
                    metadata={"source_format": "docx", "xml_tag": tag, "layout": "flow"},
                )
            )

    return elements


def _table_plain_text(parsed) -> str | None:
    usable = [c for c in parsed.cells if not c.is_spanned and c.text]
    if not usable:
        return None
    rows: dict[int, list[str]] = {}
    for c in usable:
        rows.setdefault(c.row, []).append(c.text or "")
    lines = [" | ".join(rows[r]) for r in sorted(rows)]
    return "\n".join(lines) if lines else None


def _load_relationships(zf: zipfile.ZipFile) -> dict[str, str]:
    rel_path = "word/_rels/document.xml.rels"
    if rel_path not in zf.namelist():
        return {}
    root = read_zip_xml(zf, rel_path)
    out: dict[str, str] = {}
    for rel in root:
        if local_name(rel.tag) != "Relationship":
            continue
        rid = rel.get("Id")
        target = rel.get("Target")
        if rid and target:
            out[rid] = target
    return out


def _extract_drawing_image(
    drawing: ET.Element,
    *,
    zf: zipfile.ZipFile,
    rels: dict[str, str],
    page_number: int,
    z_order: int,
    asset_output_dir: Path | None,
    bbox: BBox,
) -> DocumentElement | None:
    blip = drawing.find(".//a:blip", A_NS)
    if blip is None:
        return None
    embed = blip.get(f"{{{R_NS['r']}}}embed") or blip.get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    )
    if not embed or embed not in rels:
        return None
    target = rels[embed].lstrip("/")
    if not target.startswith("word/"):
        target = f"word/{target}"
    if target not in zf.namelist():
        alt = f"word/media/{Path(target).name}"
        if alt not in zf.namelist():
            return None
        target = alt

    blob = zf.read(target)
    ext = Path(target).suffix.lstrip(".") or "png"
    filename = Path(target).name
    rel_path = filename
    if asset_output_dir is not None:
        asset_output_dir.mkdir(parents=True, exist_ok=True)
        out_file = asset_output_dir / filename
        out_file.write_bytes(blob)
        rel_path = f"{asset_output_dir.name}/{filename}"

    return DocumentElement(
        element_id=f"E_{page_number:03d}_{z_order:04d}",
        element_type=ElementType.IMAGE,
        page_number=page_number,
        z_order=z_order,
        bbox=bbox,
        text=None,
        metadata={
            "source_format": "docx",
            "image": {
                "filename": filename,
                "relative_path": rel_path,
                "content_type": f"image/{ext}",
            },
        },
    )

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
    synthetic_bbox,
    text_content,
)
from document_inteligence.infrastructure.ingestors.docx_paragraph import paragraph_text_and_meta
from document_inteligence.infrastructure.ingestors.docx_table_xml import parse_word_table

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
A_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
WP_NS = {
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": A_NS["a"],
}
EMU_PER_PAGE_WIDTH = 6_000_000  # nominal page width EMU for anchor normalization
R_NS = {
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": W_NS["w"],
    "a": A_NS["a"],
}
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _table_cells_metadata(parsed_table) -> list[dict[str, object]]:
    return [
        {
            "row": cell.row,
            "col": cell.col,
            "text": cell.text,
            "is_spanned": cell.is_spanned,
            "span_width": cell.span_width,
            "span_height": cell.span_height,
            "is_merge_origin": cell.is_merge_origin,
        }
        for cell in parsed_table.cells
    ]


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

            blocks = _split_body_blocks(body_el)
            pages: list[DocumentPage] = []
            for page_idx, block_nodes in enumerate(blocks, start=1):
                elements = _blocks_to_elements(
                    block_nodes,
                    page_number=page_idx,
                    zf=zf,
                    rels=rels,
                    docx_path=docx_path,
                    asset_output_dir=self._asset_output_dir,
                )
                pages.append(
                    DocumentPage(
                        page_number=page_idx,
                        width=1.0,
                        height=1.0,
                        elements=elements,
                        metadata={"source_format": "docx", "layout_mode": "structural"},
                    )
                )

        if not pages:
            pages = [
                DocumentPage(
                    page_number=1,
                    width=1.0,
                    height=1.0,
                    elements=[],
                    metadata={"source_format": "docx"},
                )
            ]
        return ParsedDocument(source_path=str(docx_path), pages=pages)


def _split_body_blocks(body_el: ET.Element) -> list[list[ET.Element]]:
    """Split body children into pages at section boundaries (w:sectPr)."""
    current: list[ET.Element] = []
    pages: list[list[ET.Element]] = []

    for child in list(body_el):
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "sectPr":
            if current:
                pages.append(current)
                current = []
            continue
        current.append(child)

    if current:
        pages.append(current)
    if not pages:
        pages = [[]]
    return pages


def _blocks_to_elements(
    nodes: list[ET.Element],
    *,
    page_number: int,
    zf: zipfile.ZipFile,
    rels: dict[str, str],
    docx_path: Path,
    asset_output_dir: Path | None,
) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    order = 0

    for node in nodes:
        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
        order += 1
        eid = f"E_{page_number:03d}_{order:04d}"
        bbox = synthetic_bbox(order - 1)

        if tag == "p":
            text, para_meta = paragraph_text_and_meta(node)
            drawings = node.findall(".//w:drawing", W_NS)
            if text:
                elements.append(
                    DocumentElement(
                        element_id=eid,
                        element_type=ElementType.TEXT,
                        page_number=page_number,
                        z_order=order,
                        bbox=bbox,
                        text=text,
                        metadata=para_meta,
                    )
                )
            for draw in drawings:
                order += 1
                draw_bbox = _drawing_bbox(draw, fallback_index=order - 1)
                img = _extract_drawing_image(
                    draw,
                    zf=zf,
                    rels=rels,
                    page_number=page_number,
                    z_order=order,
                    asset_output_dir=asset_output_dir,
                    bbox=draw_bbox,
                )
                if img:
                    elements.append(img)
            continue

        if tag == "tbl":
            parsed = parse_word_table(node)
            pipe_text = _table_plain_text(parsed)
            elements.append(
                DocumentElement(
                    element_id=eid,
                    element_type=ElementType.TABLE,
                    page_number=page_number,
                    z_order=order,
                    bbox=bbox,
                    text=pipe_text,
                    metadata={
                        "source_format": "docx",
                        "table_col_widths": parsed.col_widths,
                        "table_row_heights": parsed.row_heights,
                        "table_cells": _table_cells_metadata(parsed),
                    },
                )
            )
            continue

        text = text_content(node, ns=W_NS)
        if text:
            elements.append(
                DocumentElement(
                    element_id=eid,
                    element_type=ElementType.UNKNOWN,
                    page_number=page_number,
                    z_order=order,
                    bbox=bbox,
                    text=text,
                    metadata={"source_format": "docx", "xml_tag": tag},
                )
            )

    return elements


def _drawing_bbox(drawing: ET.Element, *, fallback_index: int) -> BBox:
    """Approximate bbox from wp:inline / wp:anchor extent and offsets."""

    container = drawing.find(".//wp:inline", WP_NS) or drawing.find(".//wp:anchor", WP_NS)
    if container is None:
        return synthetic_bbox(fallback_index)

    extent = container.find("wp:extent", WP_NS)
    pos = container.find("wp:positionH/wp:posOffset", WP_NS)
    pos_v = container.find("wp:positionV/wp:posOffset", WP_NS)
    if extent is None:
        return synthetic_bbox(fallback_index)

    try:
        cx = int(extent.get("cx", "0"))
        cy = int(extent.get("cy", "0"))
        left = int(pos.text) if pos is not None and pos.text else 0
        top = int(pos_v.text) if pos_v is not None and pos_v.text else fallback_index * 500_000
        width = max(cx / EMU_PER_PAGE_WIDTH, 0.05)
        height = max(cy / EMU_PER_PAGE_WIDTH, 0.03)
        x = max(0.0, min(left / EMU_PER_PAGE_WIDTH, 0.95))
        y = max(0.0, min(top / EMU_PER_PAGE_WIDTH, 0.95))
        return BBox(x=x, y=y, width=min(width, 1.0 - x), height=min(height, 1.0 - y))
    except (TypeError, ValueError):
        return synthetic_bbox(fallback_index)


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
    embed = blip.get(f"{{{R_NS['r']}}}embed") or blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
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

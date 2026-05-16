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
from document_inteligence.infrastructure.ingestors._ooxml_utils import (
    local_name,
    read_zip_xml,
    sorted_section_paths,
    synthetic_bbox,
    text_content,
)


class HwpxIngestor(DocumentIngestor):
    def __init__(self, asset_output_dir: str | None = None) -> None:
        self._asset_output_dir = Path(asset_output_dir) if asset_output_dir else None

    def supports(self, path: str) -> bool:
        return Path(path).suffix.lower() == ".hwpx"

    def ingest(self, path: str) -> ParsedDocument:
        hwpx_path = Path(path)
        with zipfile.ZipFile(hwpx_path) as zf:
            section_paths = sorted_section_paths(
                zf.namelist(), prefix="Contents/section", suffix=".xml"
            )
            if not section_paths:
                section_paths = sorted(
                    n for n in zf.namelist() if "section" in n.lower() and n.endswith(".xml")
                )

            bindata = _index_bindata(zf)
            pages: list[DocumentPage] = []

            for page_idx, sec_path in enumerate(section_paths, start=1):
                root = read_zip_xml(zf, sec_path)
                elements = _section_to_elements(
                    root,
                    page_number=page_idx,
                    zf=zf,
                    bindata=bindata,
                    asset_output_dir=self._asset_output_dir,
                )
                pages.append(
                    DocumentPage(
                        page_number=page_idx,
                        width=1.0,
                        height=1.0,
                        elements=elements,
                        metadata={"source_format": "hwpx", "layout_mode": "structural"},
                    )
                )

        if not pages:
            pages = [
                DocumentPage(
                    page_number=1,
                    width=1.0,
                    height=1.0,
                    elements=[],
                    metadata={"source_format": "hwpx"},
                )
            ]
        return ParsedDocument(source_path=str(hwpx_path), pages=pages)


def _index_bindata(zf: zipfile.ZipFile) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in zf.namelist():
        if name.startswith("BinData/") and not name.endswith("/"):
            out[Path(name).name] = name
    return out


def _section_to_elements(
    root: ET.Element,
    *,
    page_number: int,
    zf: zipfile.ZipFile,
    bindata: dict[str, str],
    asset_output_dir: Path | None,
) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    order = 0

    for block in _iter_blocks(root):
        ln = local_name(block.tag)
        order += 1
        eid = f"E_{page_number:03d}_{order:04d}"
        bbox = synthetic_bbox(order - 1)

        if ln == "p":
            text = _hwpx_paragraph_text(block)
            if text:
                elements.append(
                    DocumentElement(
                        element_id=eid,
                        element_type=ElementType.TEXT,
                        page_number=page_number,
                        z_order=order,
                        bbox=bbox,
                        text=text,
                        metadata={"source_format": "hwpx"},
                    )
                )
            continue

        if ln == "tbl":
            cells_meta, pipe_text = _parse_hwpx_table(block)
            elements.append(
                DocumentElement(
                    element_id=eid,
                    element_type=ElementType.TABLE,
                    page_number=page_number,
                    z_order=order,
                    bbox=bbox,
                    text=pipe_text,
                    metadata={
                        "source_format": "hwpx",
                        "table_cells": cells_meta,
                    },
                )
            )
            continue

        if ln in {"pic", "img"}:
            img = _extract_hwpx_image(
                block,
                zf=zf,
                bindata=bindata,
                page_number=page_number,
                z_order=order,
                asset_output_dir=asset_output_dir,
            )
            if img:
                elements.append(img)

    return elements


def _iter_blocks(root: ET.Element):
    """Yield top-level block elements (p/tbl/pic) per section."""
    for child in root:
        ln = local_name(child.tag)
        if ln in {"p", "tbl", "pic", "img"}:
            yield child
        elif ln in {"sec", "section"}:
            yield from _iter_blocks(child)


def _hwpx_paragraph_text(p: ET.Element) -> str:
    parts: list[str] = []
    for node in p.iter():
        if local_name(node.tag) == "t" and node.text:
            parts.append(node.text)
    return "".join(parts).strip()


def _parse_hwpx_table(tbl: ET.Element) -> tuple[list[dict[str, object]], str | None]:
    rows = list(tbl)
    if not rows or local_name(rows[0].tag) != "tr":
        rows = [el for el in tbl.iter() if local_name(el.tag) == "tr"]

    cells_meta: list[dict[str, object]] = []
    matrix: list[list[str]] = []

    for r_idx, tr in enumerate(rows):
        row_cells = [el for el in tr if local_name(el.tag) == "tc"]
        row_text: list[str] = []
        for c_idx, tc in enumerate(row_cells):
            text = _hwpx_paragraph_text(tc) or text_content(tc)
            row_text.append(text)
            cells_meta.append(
                {
                    "row": r_idx,
                    "col": c_idx,
                    "text": text or None,
                    "is_spanned": False,
                    "span_width": 1,
                    "span_height": 1,
                    "is_merge_origin": True,
                }
            )
        matrix.append(row_text)

    lines = [" | ".join(row) for row in matrix if any(c.strip() for c in row)]
    return cells_meta, ("\n".join(lines) if lines else None)


def _extract_hwpx_image(
    node: ET.Element,
    *,
    zf: zipfile.ZipFile,
    bindata: dict[str, str],
    page_number: int,
    z_order: int,
    asset_output_dir: Path | None,
) -> DocumentElement | None:
    ref = None
    for el in node.iter():
        for attr in ("href", "binaryItemIDRef", "binItemIDRef"):
            val = el.get(attr)
            if val:
                ref = val
                break
        if ref:
            break

    if not ref:
        return None

    key = Path(ref).name
    zip_path = bindata.get(key) or bindata.get(ref)
    if not zip_path:
        for name, path in bindata.items():
            if key in name or ref in path:
                zip_path = path
                break
    if not zip_path:
        return None

    blob = zf.read(zip_path)
    filename = Path(zip_path).name
    ext = Path(filename).suffix.lstrip(".") or "png"
    rel_path = filename
    if asset_output_dir is not None:
        asset_output_dir.mkdir(parents=True, exist_ok=True)
        out = asset_output_dir / filename
        out.write_bytes(blob)
        rel_path = f"{asset_output_dir.name}/{filename}"

    return DocumentElement(
        element_id=f"E_{page_number:03d}_{z_order:04d}",
        element_type=ElementType.IMAGE,
        page_number=page_number,
        z_order=z_order,
        bbox=synthetic_bbox(z_order - 1),
        metadata={
            "source_format": "hwpx",
            "image": {
                "filename": filename,
                "relative_path": rel_path,
                "content_type": f"image/{ext}",
            },
        },
    )

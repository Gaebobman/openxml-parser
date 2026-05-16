"""Absorb small text labels overlaid on images as annotations.

When a PPTX slide has diagram labels placed on top of an image,
they appear as independent text elements. This module detects
spatial containment and absorbs those labels into the image's
metadata so they render as compact annotations instead of
scattered paragraphs.
"""
from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.table_absorber import bbox_containment_ratio
from document_inteligence.domain.entities import DocumentElement, DocumentPage, ElementType


def absorb_image_annotations(page: DocumentPage, config: ParserConfig) -> None:
    images = sorted(
        [e for e in page.elements if e.element_type == ElementType.IMAGE],
        key=lambda e: e.bbox.width * e.bbox.height,
        reverse=True,
    )
    if not images:
        return

    threshold = config.image_annotation_containment_threshold
    max_len = config.image_annotation_max_text_len

    for image in images:
        annotations: list[dict[str, object]] = []
        outer = {
            "x": image.bbox.x,
            "y": image.bbox.y,
            "width": image.bbox.width,
            "height": image.bbox.height,
        }
        for elem in page.elements:
            if elem.element_id == image.element_id:
                continue
            if elem.element_type not in (ElementType.TEXT, ElementType.UNKNOWN):
                continue
            if _already_absorbed(elem):
                continue
            text = (elem.text or "").strip()
            if not text:
                continue
            if len(text) > max_len:
                continue
            inner = {
                "x": elem.bbox.x,
                "y": elem.bbox.y,
                "width": elem.bbox.width,
                "height": elem.bbox.height,
            }
            ratio = bbox_containment_ratio(inner=inner, outer=outer)
            if ratio < threshold:
                continue
            annotations.append({
                "element_id": elem.element_id,
                "text": text,
                "y": elem.bbox.y,
                "x": elem.bbox.x,
                "containment": ratio,
            })
            elem.metadata["absorbed_by_image"] = image.element_id

        if annotations:
            annotations.sort(key=lambda a: (float(a["y"]), float(a["x"])))
            image.metadata["annotations"] = annotations


def _already_absorbed(e: DocumentElement) -> bool:
    return bool(
        e.metadata.get("absorbed_by")
        or e.metadata.get("absorbed_by_table")
        or e.metadata.get("absorbed_by_image")
    )

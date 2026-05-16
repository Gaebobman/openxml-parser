"""Tests for noise filtering and image annotation absorption."""
from __future__ import annotations

import pytest

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.image_annotation_absorber import absorb_image_annotations
from document_inteligence.domain.entities import DocumentElement, DocumentPage, ElementType
from document_inteligence.domain.value_objects import BBox

# Re-use the private helper via import of the module under test.
from document_inteligence.application.use_cases import _is_noise


def _elem(eid: str, etype: ElementType, bbox: BBox, text: str | None = None, **meta) -> DocumentElement:
    return DocumentElement(
        element_id=eid, element_type=etype, page_number=1, z_order=0,
        bbox=bbox, text=text, metadata=dict(meta),
    )


class TestNoiseFilter:
    def test_empty_unknown_is_noise(self):
        e = _elem("e1", ElementType.UNKNOWN, BBox(0.1, 0.1, 0.01, 0.01))
        assert _is_noise(e, ParserConfig()) is True

    def test_empty_text_is_noise(self):
        e = _elem("e1", ElementType.TEXT, BBox(0.1, 0.1, 0.1, 0.1), text="")
        assert _is_noise(e, ParserConfig()) is True

    def test_whitespace_text_is_noise(self):
        e = _elem("e1", ElementType.TEXT, BBox(0.1, 0.1, 0.1, 0.1), text="   ")
        assert _is_noise(e, ParserConfig()) is True

    def test_normal_text_not_noise(self):
        e = _elem("e1", ElementType.TEXT, BBox(0.1, 0.1, 0.1, 0.1), text="Hello")
        assert _is_noise(e, ParserConfig()) is False

    def test_image_not_noise(self):
        e = _elem("e1", ElementType.IMAGE, BBox(0.1, 0.1, 0.2, 0.2))
        assert _is_noise(e, ParserConfig()) is False

    def test_tiny_empty_element_is_noise(self):
        cfg = ParserConfig(min_element_area=0.001)
        e = _elem("e1", ElementType.UNKNOWN, BBox(0.5, 0.5, 0.001, 0.001))
        assert _is_noise(e, cfg) is True

    def test_tiny_element_with_text_not_noise(self):
        cfg = ParserConfig(min_element_area=0.001)
        e = _elem("e1", ElementType.TEXT, BBox(0.5, 0.5, 0.001, 0.001), text="A")
        assert _is_noise(e, cfg) is False


class TestImageAnnotationAbsorption:
    def test_text_inside_image_absorbed(self):
        img = _elem("img1", ElementType.IMAGE, BBox(0.1, 0.1, 0.5, 0.5))
        label = _elem("lbl1", ElementType.TEXT, BBox(0.2, 0.2, 0.05, 0.03), text="Label")
        page = DocumentPage(page_number=1, width=1000, height=1000, elements=[img, label])
        absorb_image_annotations(page, ParserConfig())
        assert label.metadata.get("absorbed_by_image") == "img1"
        assert "annotations" in img.metadata
        assert len(img.metadata["annotations"]) == 1
        assert img.metadata["annotations"][0]["text"] == "Label"

    def test_long_text_not_absorbed(self):
        img = _elem("img1", ElementType.IMAGE, BBox(0.1, 0.1, 0.5, 0.5))
        long = _elem("lbl1", ElementType.TEXT, BBox(0.2, 0.2, 0.05, 0.03), text="A" * 100)
        page = DocumentPage(page_number=1, width=1000, height=1000, elements=[img, long])
        absorb_image_annotations(page, ParserConfig())
        assert long.metadata.get("absorbed_by_image") is None

    def test_text_outside_image_not_absorbed(self):
        img = _elem("img1", ElementType.IMAGE, BBox(0.1, 0.1, 0.2, 0.2))
        far = _elem("lbl1", ElementType.TEXT, BBox(0.8, 0.8, 0.05, 0.03), text="Far")
        page = DocumentPage(page_number=1, width=1000, height=1000, elements=[img, far])
        absorb_image_annotations(page, ParserConfig())
        assert far.metadata.get("absorbed_by_image") is None

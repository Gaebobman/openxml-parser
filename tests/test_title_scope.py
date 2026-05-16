"""Tests for title_of spatial scoping."""
from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.relationships import _is_title_target
from document_inteligence.domain.entities import DocumentElement, ElementType
from document_inteligence.domain.value_objects import BBox


def _elem(eid: str, bbox: BBox) -> DocumentElement:
    return DocumentElement(
        element_id=eid, element_type=ElementType.TEXT, page_number=1, z_order=0,
        bbox=bbox, text="x", metadata={},
    )


class TestTitleScope:
    def test_target_below_within_distance(self):
        title = _elem("t1", BBox(0.1, 0.05, 0.3, 0.05))
        target = _elem("e1", BBox(0.1, 0.15, 0.3, 0.1))
        assert _is_title_target(title, target, ParserConfig(title_max_y_distance=0.5)) is True

    def test_target_above_title_rejected(self):
        title = _elem("t1", BBox(0.1, 0.5, 0.3, 0.05))
        target = _elem("e1", BBox(0.1, 0.1, 0.3, 0.1))
        assert _is_title_target(title, target, ParserConfig(title_max_y_distance=0.5)) is False

    def test_target_too_far_below_rejected(self):
        title = _elem("t1", BBox(0.1, 0.05, 0.3, 0.05))
        target = _elem("e1", BBox(0.1, 0.8, 0.3, 0.1))
        assert _is_title_target(title, target, ParserConfig(title_max_y_distance=0.3)) is False

    def test_target_immediately_below(self):
        title = _elem("t1", BBox(0.1, 0.1, 0.3, 0.05))
        target = _elem("e1", BBox(0.1, 0.15, 0.3, 0.1))
        assert _is_title_target(title, target, ParserConfig(title_max_y_distance=0.01)) is True

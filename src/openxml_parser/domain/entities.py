from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .value_objects import BBox


class ElementType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    CHART = "chart"
    GROUP = "group"
    UNKNOWN = "unknown"


@dataclass
class DocumentElement:
    element_id: str
    element_type: ElementType
    page_number: int
    z_order: int
    bbox: BBox
    text: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ElementRelation:
    relation_type: str
    source_element_id: str
    target_element_id: str
    confidence: float
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class DocumentPage:
    page_number: int
    width: float
    height: float
    elements: list[DocumentElement] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    source_path: str
    pages: list[DocumentPage] = field(default_factory=list)
    relations: list[ElementRelation] = field(default_factory=list)


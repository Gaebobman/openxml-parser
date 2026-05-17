from __future__ import annotations

from openxml_parser.domain.repositories import StructureBuilder
from openxml_parser.infrastructure.structure.outline_structure import OutlineStructureBuilder


def structure_builder_for_path(path: str) -> StructureBuilder:
    del path
    return OutlineStructureBuilder()

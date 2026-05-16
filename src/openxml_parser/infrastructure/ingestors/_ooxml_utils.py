from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from openxml_parser.domain.value_objects import BBox


def clamp_01(value: float) -> float:
    return max(0.0, min(1.0, value))


def synthetic_bbox(index: int, *, row_height: float = 0.08) -> BBox:
    """Flow-layout placeholder bbox from document order (0-based index)."""
    h = row_height
    y = clamp_01(index * h)
    return BBox(x=0.02, y=y, width=0.96, height=h)


def read_zip_xml(zf: zipfile.ZipFile, path: str) -> ET.Element:
    with zf.open(path) as fh:
        return ET.fromstring(fh.read())


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def text_content(element: ET.Element, *, ns: dict[str, str] | None = None) -> str:
    parts: list[str] = []
    tag = f"{{{ns['w']}}}t" if ns and "w" in ns else None
    if tag:
        for node in element.iter(tag):
            if node.text:
                parts.append(node.text)
    else:
        for node in element.iter():
            if local_name(node.tag) == "t" and node.text:
                parts.append(node.text)
    return "".join(parts).strip()


def sorted_section_paths(names: list[str], *, prefix: str, suffix: str = ".xml") -> list[str]:
    paths = [n for n in names if n.startswith(prefix) and n.endswith(suffix)]

    def key(name: str) -> int:
        stem = Path(name).stem
        digits = "".join(ch for ch in stem if ch.isdigit())
        return int(digits) if digits else 0

    return sorted(paths, key=key)

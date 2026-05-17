from __future__ import annotations

from openxml_parser.domain.entities import BlockKind, DocumentBlock, DocumentElement
from openxml_parser.domain.value_objects import BBox


def merge_bbox(existing: BBox | None, element: DocumentElement) -> BBox:
    b = element.bbox
    if existing is None:
        return BBox(x=b.x, y=b.y, width=b.width, height=b.height)
    x0 = min(existing.x, b.x)
    y0 = min(existing.y, b.y)
    x1 = max(existing.x + existing.width, b.x + b.width)
    y1 = max(existing.y + existing.height, b.y + b.height)
    return BBox(x=x0, y=y0, width=max(x1 - x0, 0.0), height=max(y1 - y0, 0.0))


def normalize_outline_level(level: int | None, *, default: int = 2) -> int:
    if level is None:
        return default
    return max(1, min(int(level), 6))


class BlockAccumulator:
    """Mutable builder for DocumentBlock instances."""

    def __init__(self, page_number: int) -> None:
        self.page_number = page_number
        self.blocks: list[DocumentBlock] = []
        self._counter = 0
        self._by_id: dict[str, DocumentBlock] = {}

    def create(
        self,
        *,
        kind: BlockKind,
        title_text: str,
        element: DocumentElement | None = None,
        parent_block_id: str | None = None,
        level: int | None = None,
        extra_element_ids: list[str] | None = None,
    ) -> DocumentBlock:
        self._counter += 1
        block_id = f"B_{self.page_number:03d}_{self._counter:04d}"
        element_ids: list[str] = list(extra_element_ids or [])
        bbox: BBox | None = None
        if element is not None:
            if element.element_id not in element_ids:
                element_ids.append(element.element_id)
            bbox = merge_bbox(None, element)

        parent = self._by_id.get(parent_block_id) if parent_block_id else None
        section_path: list[str] = []
        if parent is not None:
            section_path = list(parent.section_path)
        label = title_text.strip() or kind.value
        if kind == BlockKind.HEADING:
            section_path.append(label)

        lvl = normalize_outline_level(level, default=2 if kind == BlockKind.HEADING else 0)
        block = DocumentBlock(
            block_id=block_id,
            kind=kind,
            page_number=self.page_number,
            level=lvl,
            title_text=title_text.strip(),
            element_ids=element_ids,
            parent_block_id=parent_block_id,
            section_path=section_path,
            bbox=bbox,
        )
        self.blocks.append(block)
        self._by_id[block_id] = block
        return block

    def append_element(self, block: DocumentBlock | None, element: DocumentElement) -> None:
        if block is None:
            return
        if element.element_id not in block.element_ids:
            block.element_ids.append(element.element_id)
        block.bbox = merge_bbox(block.bbox, element)

    def get(self, block_id: str | None) -> DocumentBlock | None:
        if block_id is None:
            return None
        return self._by_id.get(block_id)

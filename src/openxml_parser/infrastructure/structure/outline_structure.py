from __future__ import annotations

from openxml_parser.domain.entities import (
    BlockKind,
    DocumentBlock,
    DocumentElement,
    DocumentPage,
    ElementRelation,
    ElementType,
)
from openxml_parser.domain.repositories import StructureBuilder
from openxml_parser.infrastructure.structure._helpers import BlockAccumulator, normalize_outline_level


class OutlineStructureBuilder(StructureBuilder):
    """Build blocks from native outline signals only (Word Heading, PPTX placeholder)."""

    def build(
        self,
        page: DocumentPage,
        *,
        relations: list[ElementRelation],
    ) -> list[DocumentBlock]:
        acc = BlockAccumulator(page.page_number)
        root_id = _page_container(acc, page)

        stack: list[tuple[int, str]] = []
        title_sources = {
            rel.source_element_id
            for rel in relations
            if rel.relation_type == "title_of"
        }
        title_block_by_element: dict[str, str] = {}

        def parent_for_heading(level: int) -> str | None:
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                return stack[-1][1]
            return root_id

        def current_parent_id() -> str | None:
            if stack:
                return stack[-1][1]
            return root_id

        for element in page.elements:
            if _skip_element(element):
                continue

            outline_level = _outline_level(element)
            if outline_level is not None:
                title = _element_title(element)
                parent_id = parent_for_heading(outline_level)
                block = acc.create(
                    kind=BlockKind.HEADING,
                    title_text=title,
                    element=element,
                    parent_block_id=parent_id,
                    level=outline_level,
                )
                stack.append((outline_level, block.block_id))
                if element.element_id in title_sources:
                    title_block_by_element[element.element_id] = block.block_id
                continue

            parent_id = _resolve_parent(
                element,
                relations=relations,
                title_block_by_element=title_block_by_element,
                default_parent_id=current_parent_id(),
            )

            if element.element_type == ElementType.TABLE:
                acc.create(
                    kind=BlockKind.TABLE,
                    title_text=_element_title(element) or "table",
                    element=element,
                    parent_block_id=parent_id,
                )
                continue

            if element.element_type == ElementType.IMAGE:
                acc.create(
                    kind=BlockKind.FIGURE,
                    title_text="figure",
                    element=element,
                    parent_block_id=parent_id,
                )
                continue

            kind = BlockKind.LIST_ITEM if element.metadata.get("is_list_item") else BlockKind.PARAGRAPH
            if parent_id:
                acc.append_element(acc.get(parent_id), element)
            else:
                acc.create(
                    kind=kind,
                    title_text=_element_title(element) or kind.value,
                    element=element,
                )

        return acc.blocks


def _page_container(acc: BlockAccumulator, page: DocumentPage) -> str | None:
    fmt = page.metadata.get("source_format")
    if fmt == "pptx":
        block = acc.create(
            kind=BlockKind.CONTAINER,
            title_text=f"Slide {page.page_number}",
            level=1,
        )
        return block.block_id
    if fmt == "xlsx":
        name = str(page.metadata.get("sheet_name") or f"Sheet {page.page_number}")
        block = acc.create(kind=BlockKind.CONTAINER, title_text=name, level=1)
        return block.block_id
    if fmt == "hwpx":
        block = acc.create(
            kind=BlockKind.CONTAINER,
            title_text=f"Section {page.page_number}",
            level=1,
        )
        return block.block_id
    return None


def _outline_level(element: DocumentElement) -> int | None:
    if element.metadata.get("is_heading"):
        return normalize_outline_level(int(element.metadata.get("heading_level", 2) or 2))
    if bool(element.metadata.get("is_placeholder")):
        return 3
    return None


def _resolve_parent(
    element: DocumentElement,
    *,
    relations: list[ElementRelation],
    title_block_by_element: dict[str, str],
    default_parent_id: str | None,
) -> str | None:
    for rel in relations:
        if rel.relation_type == "title_of" and rel.target_element_id == element.element_id:
            return title_block_by_element.get(rel.source_element_id, default_parent_id)
    return default_parent_id


def _skip_element(element: DocumentElement) -> bool:
    return bool(
        element.metadata.get("absorbed_by")
        or element.metadata.get("absorbed_by_table")
        or element.metadata.get("absorbed_by_image")
    )


def _element_title(element: DocumentElement) -> str:
    return (element.text or "").strip()

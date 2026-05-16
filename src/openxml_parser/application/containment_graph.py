from __future__ import annotations

from openxml_parser.application.config import ParserConfig
from openxml_parser.application.table_absorber import bbox_containment_ratio
from openxml_parser.domain.entities import DocumentElement, DocumentPage, ElementType


def resolve_containment(page: DocumentPage, config: ParserConfig) -> None:
    """Detect spatial containment between non-table elements and merge/group."""
    elements = page.elements
    if len(elements) < 2:
        return

    parent_map = _build_parent_map(elements, config.containment_threshold)
    _apply_merges(elements, parent_map)


def _build_parent_map(
    elements: list[DocumentElement],
    threshold: float,
) -> dict[str, str]:
    """For each child find the tightest (smallest-area) parent that contains it."""
    parent_map: dict[str, str] = {}
    by_id = {e.element_id: e for e in elements}

    sortable = sorted(elements, key=lambda e: _area(e), reverse=True)

    for i, candidate_parent in enumerate(sortable):
        if candidate_parent.element_type == ElementType.TABLE:
            continue
        if bool(candidate_parent.metadata.get("absorbed_by")):
            continue

        for j in range(i + 1, len(sortable)):
            child = sortable[j]
            if child.element_id == candidate_parent.element_id:
                continue
            if child.element_type == ElementType.TABLE:
                continue
            if bool(child.metadata.get("absorbed_by")):
                continue

            ratio = bbox_containment_ratio(
                inner=child.bbox.__dict__,
                outer=candidate_parent.bbox.__dict__,
            )
            if ratio < threshold:
                continue

            existing_parent_id = parent_map.get(child.element_id)
            if existing_parent_id is not None:
                existing_parent = by_id.get(existing_parent_id)
                if existing_parent and _area(existing_parent) < _area(candidate_parent):
                    continue

            parent_map[child.element_id] = candidate_parent.element_id
    return parent_map


def _apply_merges(
    elements: list[DocumentElement],
    parent_map: dict[str, str],
) -> None:
    by_id = {e.element_id: e for e in elements}

    children_of: dict[str, list[str]] = {}
    for child_id, parent_id in parent_map.items():
        children_of.setdefault(parent_id, []).append(child_id)

    for parent_id, child_ids in children_of.items():
        parent = by_id.get(parent_id)
        if parent is None:
            continue

        child_elements = [by_id[cid] for cid in child_ids if cid in by_id]
        child_elements.sort(key=lambda e: (e.bbox.y, e.bbox.x))

        if _is_text_merge(parent, child_elements):
            _merge_text(parent, child_elements)
        elif _is_shape_group(parent, child_elements):
            _merge_as_group(parent, child_elements)


def _is_text_merge(parent: DocumentElement, children: list[DocumentElement]) -> bool:
    if parent.element_type != ElementType.TEXT:
        return False
    return all(c.element_type == ElementType.TEXT for c in children)


def _is_shape_group(parent: DocumentElement, children: list[DocumentElement]) -> bool:
    return parent.element_type in {ElementType.UNKNOWN, ElementType.TEXT, ElementType.GROUP}


def _merge_text(parent: DocumentElement, children: list[DocumentElement]) -> None:
    parts: list[str] = []
    parent_text = (parent.text or "").strip()
    if parent_text:
        parts.append(parent_text)
    for child in children:
        child_text = (child.text or "").strip()
        if child_text and child_text not in parts:
            parts.append(child_text)
        child.metadata["absorbed_by"] = parent.element_id
    if parts:
        parent.text = "\n".join(parts)
    merged_ids = [c.element_id for c in children]
    parent.metadata["merged_children"] = merged_ids


def _merge_as_group(parent: DocumentElement, children: list[DocumentElement]) -> None:
    parts: list[str] = []
    parent_text = (parent.text or "").strip()
    if parent_text:
        parts.append(parent_text)

    absorbed_items: list[dict[str, object]] = []
    for child in children:
        child.metadata["absorbed_by"] = parent.element_id
        content = _child_content(child)
        if content:
            absorbed_items.append({
                "element_id": child.element_id,
                "type": child.element_type.value,
                "content": content,
            })
            if child.element_type == ElementType.TEXT:
                text = (child.text or "").strip()
                if text and text not in parts:
                    parts.append(text)

    if parts:
        parent.text = "\n".join(parts)
    if absorbed_items:
        parent.metadata["absorbed_children"] = absorbed_items


def _child_content(child: DocumentElement) -> str:
    if child.element_type == ElementType.IMAGE:
        image_meta = child.metadata.get("image")
        if isinstance(image_meta, dict):
            ref = image_meta.get("relative_path") or image_meta.get("filename")
            if isinstance(ref, str) and ref:
                return f"![{child.element_id}]({ref})"
        return f"![{child.element_id}](image-not-exported)"
    return (child.text or "").strip()


def _area(element: DocumentElement) -> float:
    return max(0.0, element.bbox.width) * max(0.0, element.bbox.height)

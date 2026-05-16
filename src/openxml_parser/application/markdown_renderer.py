from __future__ import annotations

import re

from openxml_parser.application.config import ParserConfig
from openxml_parser.domain.entities import DocumentElement, DocumentPage, ElementRelation, ElementType, ParsedDocument


def render_markdown(
    parsed_document: ParsedDocument,
    *,
    include_slide_comment: bool = True,
    config: ParserConfig | None = None,
) -> str:
    cfg = config or ParserConfig()
    rel_by_target = _caption_relation_map(parsed_document.relations)
    chunks: list[str] = []
    for page in parsed_document.pages:
        chunks.append(_render_page(page, include_slide_comment=include_slide_comment, rel_by_target=rel_by_target, config=cfg))
    return "\n\n---\n\n".join([c for c in chunks if c.strip()]).strip() + "\n"


def _render_page(
    page: DocumentPage,
    *,
    include_slide_comment: bool,
    rel_by_target: dict[str, str],
    config: ParserConfig,
) -> str:
    lines: list[str] = []
    if include_slide_comment:
        lines.append(f"<!-- Page {page.page_number} -->")
        lines.append("")

    title_used = False
    seen_captions: set[str] = set()
    prev_group: str | None = None
    for element in page.elements:
        if bool(element.metadata.get("absorbed_by_table")) or bool(element.metadata.get("absorbed_by")):
            continue
        block = _render_element(element, title_used=title_used, config=config)
        if not block:
            continue

        cur_group_raw = element.metadata.get("spatial_group")
        cur_group = str(cur_group_raw) if cur_group_raw is not None else None
        if prev_group is not None and cur_group is not None and cur_group != prev_group:
            sep = _group_separator(prev_group, cur_group)
            if sep:
                lines.append(sep)
                lines.append("")
        prev_group = cur_group

        if block.startswith("# "):
            title_used = True
        lines.append(block)
        caption = rel_by_target.get(element.element_id)
        if caption and caption not in seen_captions:
            lines.append(f"> {caption}")
            seen_captions.add(caption)
        lines.append("")
    return "\n".join(lines).strip()


def _render_element(element: DocumentElement, *, title_used: bool, config: ParserConfig) -> str:
    if element.element_type == ElementType.TEXT:
        text = (element.text or "").strip()
        if not text:
            return ""
        display = text.replace("\t", " · ")
        if config.preserve_text_formatting:
            fmt = element.metadata.get("formatted_text")
            if isinstance(fmt, str) and fmt.strip():
                display = fmt.strip()
        if not title_used and _looks_like_title(element, config):
            return f"# {text}"
        if bool(element.metadata.get("is_heading")):
            level = int(element.metadata.get("heading_level", 2) or 2)
            level = max(2, min(level, 6))
            return f"{'#' * level} {display}"
        return _preserve_linebreaks(display)

    if element.element_type == ElementType.IMAGE:
        image_meta = element.metadata.get("image")
        if isinstance(image_meta, dict):
            ref = image_meta.get("relative_path") or image_meta.get("filename")
            if isinstance(ref, str) and ref:
                img_tag = _render_img_tag(ref, element.element_id, image_meta)
            else:
                img_tag = _render_img_tag("image-not-exported", element.element_id)
        else:
            img_tag = _render_img_tag("image-not-exported", element.element_id)
        annotations = element.metadata.get("annotations")
        if isinstance(annotations, list) and annotations:
            labels = [str(a.get("text", "")) for a in annotations if a.get("text")]
            if labels:
                return img_tag + "\n\n*" + " | ".join(labels) + "*"
        return img_tag

    if element.element_type == ElementType.TABLE:
        rendered = _render_table(element, config=config, use_formatting=config.preserve_text_formatting)
        if rendered:
            return rendered
        return _preserve_linebreaks((element.text or "").strip())

    if element.element_type == ElementType.CHART:
        return f"> [chart] {element.text.strip()}" if element.text else "> [chart]"

    return _preserve_linebreaks((element.text or "").strip())


def _looks_like_title(element: DocumentElement, config: ParserConfig) -> bool:
    if bool(element.metadata.get("is_placeholder")):
        return True
    if bool(element.metadata.get("is_heading")):
        return True
    text = (element.text or "").strip()
    if not text:
        return False
    return len(text) <= config.title_max_len and "\n" not in text


def _render_table(element: DocumentElement, *, config: ParserConfig, use_formatting: bool = False) -> str:
    cells_raw = element.metadata.get("table_cells")
    if not isinstance(cells_raw, list) or not cells_raw:
        return ""

    usable = [c for c in cells_raw if isinstance(c, dict) and not bool(c.get("is_spanned"))]
    if not usable:
        return ""

    col_widths_raw = element.metadata.get("table_col_widths")
    col_pcts = _col_width_percentages(col_widths_raw) if isinstance(col_widths_raw, list) else None

    if not config.table_render_html:
        return _render_table_markdown(usable)
    return _render_table_html(usable, use_formatting=use_formatting, col_pcts=col_pcts)


def _render_table_markdown(usable: list[dict[str, object]]) -> str:
    max_row = max(int(c.get("row", 0)) for c in usable)
    max_col = max(int(c.get("col", 0)) for c in usable)
    matrix = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]

    for c in usable:
        r = int(c.get("row", 0))
        col = int(c.get("col", 0))
        text = c.get("text")
        matrix[r][col] = str(text).strip() if text is not None else ""

    if not matrix:
        return ""
    header = matrix[0]
    body = matrix[1:] if len(matrix) > 1 else []

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _render_table_html(
    usable: list[dict[str, object]],
    *,
    use_formatting: bool = False,
    col_pcts: list[float] | None = None,
) -> str:
    max_row = max(int(c.get("row", 0)) for c in usable)
    by_row: dict[int, list[dict[str, object]]] = {}
    for c in usable:
        r = int(c.get("row", 0))
        by_row.setdefault(r, []).append(c)
    for row_cells in by_row.values():
        row_cells.sort(key=lambda c: int(c.get("col", 0)))

    header_rows = _infer_header_rows(by_row, max_row)
    lines: list[str] = ["<table>"]

    if col_pcts:
        lines.append("<colgroup>")
        for pct in col_pcts:
            lines.append(f'<col style="width:{pct:.1f}%"/>')
        lines.append("</colgroup>")

    if header_rows:
        lines.append("<thead>")
        for row_idx in header_rows:
            lines.append(_render_html_row(by_row.get(row_idx, []), header=True, use_formatting=use_formatting))
        lines.append("</thead>")

    body_rows = [r for r in range(max_row + 1) if r not in header_rows]
    lines.append("<tbody>")
    for row_idx in body_rows:
        lines.append(_render_html_row(by_row.get(row_idx, []), header=False, use_formatting=use_formatting))
    lines.append("</tbody>")
    lines.append("</table>")
    return "\n".join(lines)


def _infer_header_rows(by_row: dict[int, list[dict[str, object]]], max_row: int) -> set[int]:
    if max_row < 0:
        return set()
    first_row = by_row.get(0, [])
    if not first_row:
        return set()
    score = _header_score(first_row, row_index=0)
    if score < 0.45:
        return set()
    header = {0}
    max_span = max(int(c.get("span_height", 1)) for c in first_row)
    for r in range(1, min(max_span, max_row + 1)):
        header.add(r)
    return header


def _header_score(cells: list[dict[str, object]], *, row_index: int) -> float:
    if not cells:
        return 0.0
    structure_signal = 0.0
    style_signal = 0.0
    text_signal = 0.0

    if row_index == 0:
        structure_signal += 0.5
    if any(int(c.get("span_width", 1)) > 1 or int(c.get("span_height", 1)) > 1 for c in cells):
        structure_signal += 0.3

    short_like = 0
    for c in cells:
        txt = _cell_content_text(c)
        if txt and len(txt) <= 30 and "\n" not in txt:
            short_like += 1
    text_signal += short_like / max(len(cells), 1)

    # style metadata may not exist; when absent this remains 0.
    return (0.5 * structure_signal) + (0.3 * style_signal) + (0.2 * text_signal)


def _render_html_row(cells: list[dict[str, object]], *, header: bool, use_formatting: bool = False) -> str:
    tag = "th" if header else "td"
    parts = ["<tr>"]
    for c in cells:
        attrs: list[str] = []
        col_span = int(c.get("span_width", 1))
        row_span = int(c.get("span_height", 1))
        if col_span > 1:
            attrs.append(f'colspan="{col_span}"')
        if row_span > 1:
            attrs.append(f'rowspan="{row_span}"')
        attr_text = (" " + " ".join(attrs)) if attrs else ""
        content = _cell_content_text(c, use_formatting=use_formatting)
        parts.append(f"<{tag}{attr_text}>{content}</{tag}>")
    parts.append("</tr>")
    return "".join(parts)


def _cell_content_text(cell: dict[str, object], *, use_formatting: bool = False) -> str:
    if use_formatting:
        fmt = cell.get("formatted_text")
        if isinstance(fmt, str) and fmt.strip():
            base = _nl_to_br(fmt.strip())
        else:
            base = _nl_to_br(str(cell.get("text") or "").strip())
    else:
        base = _nl_to_br(str(cell.get("text") or "").strip())
    absorbed = cell.get("absorbed_elements")
    if not isinstance(absorbed, list) or not absorbed:
        return base
    sorted_absorbed = sorted(
        [item for item in absorbed if isinstance(item, dict)],
        key=lambda item: (float(item.get("y", 0)), float(item.get("x", 0))),
    )

    cell_bbox = cell.get("cell_bbox")
    cell_mid_y = _cell_vertical_midpoint(cell_bbox)

    before_parts: list[str] = []
    after_parts: list[str] = []
    for item in sorted_absorbed:
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        w = int(item.get("display_width_px", 0))
        rendered = _md_image_to_html(_nl_to_br(content.strip()), width=w)
        item_y = float(item.get("y", 0))
        if cell_mid_y is not None and item_y < cell_mid_y:
            before_parts.append(rendered)
        else:
            after_parts.append(rendered)

    parts = before_parts + ([base] if base else []) + after_parts
    return "<br/>".join(parts)


def _col_width_percentages(raw_widths: list[object]) -> list[float] | None:
    """Convert raw EMU column widths to percentage values."""
    nums = []
    for v in raw_widths:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            return None
    total = sum(nums)
    if total <= 0:
        return None
    return [n / total * 100 for n in nums]


def _cell_vertical_midpoint(cell_bbox: dict[str, float] | None) -> float | None:
    """Return the vertical midpoint (normalised) of a cell bbox."""
    if not isinstance(cell_bbox, dict):
        return None
    y = cell_bbox.get("y")
    h = cell_bbox.get("height")
    if y is None or h is None:
        return None
    return float(y) + float(h) / 2


def _nl_to_br(text: str) -> str:
    """Convert newlines to HTML <br/> for use inside table cells."""
    if "\n" not in text:
        return text
    return "<br/>".join(line.rstrip() for line in text.split("\n"))


def _preserve_linebreaks(text: str) -> str:
    """Convert \\n to Markdown line breaks (trailing two spaces)."""
    if "\n" not in text:
        return text
    return "  \n".join(line.rstrip() for line in text.split("\n"))


def _render_img_tag(
    src: str,
    alt: str,
    image_meta: dict[str, object] | None = None,
) -> str:
    w = int(image_meta.get("display_width_px", 0)) if image_meta else 0
    attrs = f'src="{src}" alt="{alt}"'
    if w > 0:
        attrs += f' width="{w}"'
    return f"<img {attrs}/>"


_MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _md_image_to_html(text: str, *, width: int = 0) -> str:
    """Convert Markdown image syntax to <img> tag for use inside HTML blocks."""
    if width > 0:
        return _MD_IMG_RE.sub(rf'<img src="\2" alt="\1" width="{width}"/>', text)
    return _MD_IMG_RE.sub(r'<img src="\2" alt="\1"/>', text)


def _group_separator(prev_group: str, cur_group: str) -> str | None:
    """Return a visual separator when spatial groups change.

    Only emits a separator when the transition involves a vertical
    cut boundary (column change) rather than a horizontal cut
    (row change within the same region).
    """
    prev_parts = prev_group.split(".")
    cur_parts = cur_group.split(".")
    shared_depth = 0
    for a, b in zip(prev_parts, cur_parts):
        if a == b:
            shared_depth += 1
        else:
            break
    diff_parts = cur_parts[shared_depth:]
    if not diff_parts:
        return None
    diverge = diff_parts[0]
    if diverge.startswith("v"):
        return "<!-- column-break -->"
    return None


def _caption_relation_map(relations: list[ElementRelation]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in relations:
        if rel.relation_type != "caption_of":
            continue
        caption_text = rel.metadata.get("caption_text")
        if isinstance(caption_text, str) and caption_text.strip():
            out[rel.target_element_id] = caption_text.strip()
    return out


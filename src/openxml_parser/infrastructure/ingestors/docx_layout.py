from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from openxml_parser.domain.value_objects import BBox
from openxml_parser.infrastructure.ingestors._ooxml_utils import clamp_01, local_name

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
WP_NS = {
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
WPS_NS = {
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "w": W_NS["w"],
}

EMU_PER_INCH = 914_400
TWIPS_PER_INCH = 1_440
EMU_PER_TWIP = EMU_PER_INCH / TWIPS_PER_INCH

# Default US Letter content area (twips), margins 1 inch
_DEFAULT_PAGE_W = 12_240
_DEFAULT_PAGE_H = 15_840
_DEFAULT_MARGIN = 1_440


@dataclass(frozen=True)
class DocxPageMetrics:
    page_width_twips: float
    page_height_twips: float
    margin_left_twips: float
    margin_right_twips: float
    margin_top_twips: float
    margin_bottom_twips: float

    @property
    def content_width_twips(self) -> float:
        return max(self.page_width_twips - self.margin_left_twips - self.margin_right_twips, 1.0)

    @property
    def content_height_twips(self) -> float:
        return max(self.page_height_twips - self.margin_top_twips - self.margin_bottom_twips, 1.0)

    @property
    def margin_left_norm(self) -> float:
        return clamp_01(self.margin_left_twips / self.page_width_twips)

    @property
    def margin_top_norm(self) -> float:
        return clamp_01(self.margin_top_twips / self.page_height_twips)

    @property
    def content_width_norm(self) -> float:
        return clamp_01(self.content_width_twips / self.page_width_twips)

    @property
    def content_height_norm(self) -> float:
        return clamp_01(self.content_height_twips / self.page_height_twips)


@dataclass
class LayoutCursor:
    y: float
    block_index: int = 0

    def advance(self, height: float) -> None:
        self.y = clamp_01(self.y + height)
        self.block_index += 1


def default_page_metrics() -> DocxPageMetrics:
    return DocxPageMetrics(
        page_width_twips=_DEFAULT_PAGE_W,
        page_height_twips=_DEFAULT_PAGE_H,
        margin_left_twips=_DEFAULT_MARGIN,
        margin_right_twips=_DEFAULT_MARGIN,
        margin_top_twips=_DEFAULT_MARGIN,
        margin_bottom_twips=_DEFAULT_MARGIN,
    )


def parse_page_metrics(sect_pr: ET.Element | None) -> DocxPageMetrics:
    if sect_pr is None:
        return default_page_metrics()

    pg_sz = sect_pr.find("w:pgSz", W_NS)
    pg_mar = sect_pr.find("w:pgMar", W_NS)

    def _twips(el: ET.Element | None, attr: str, default: float) -> float:
        if el is None:
            return default
        raw = el.get(f"{{{W_NS['w']}}}{attr}") or el.get(attr)
        try:
            return float(raw) if raw else default
        except ValueError:
            return default

    return DocxPageMetrics(
        page_width_twips=_twips(pg_sz, "w", _DEFAULT_PAGE_W),
        page_height_twips=_twips(pg_sz, "h", _DEFAULT_PAGE_H),
        margin_left_twips=_twips(pg_mar, "left", _DEFAULT_MARGIN),
        margin_right_twips=_twips(pg_mar, "right", _DEFAULT_MARGIN),
        margin_top_twips=_twips(pg_mar, "top", _DEFAULT_MARGIN),
        margin_bottom_twips=_twips(pg_mar, "bottom", _DEFAULT_MARGIN),
    )


def split_body_sections(body_el: ET.Element) -> list[tuple[list[ET.Element], ET.Element | None]]:
    """Return (block nodes, section properties) per logical page."""
    sections: list[tuple[list[ET.Element], ET.Element | None]] = []
    current: list[ET.Element] = []
    trailing_sect: ET.Element | None = body_el.find("w:sectPr", W_NS)

    for child in list(body_el):
        if local_name(child.tag) == "sectPr":
            sections.append((current, child))
            current = []
            trailing_sect = None
            continue
        current.append(child)

    if current:
        sect = _sect_pr_from_nodes(current) or trailing_sect
        sections.append((current, sect))

    if not sections:
        sections = [([], trailing_sect)]
    return sections


def _sect_pr_from_nodes(nodes: list[ET.Element]) -> ET.Element | None:
    if not nodes:
        return None
    last = nodes[-1]
    if local_name(last.tag) != "p":
        return None
    p_pr = last.find("w:pPr", W_NS)
    if p_pr is None:
        return None
    return p_pr.find("w:sectPr", W_NS)


def _twips_attr(el: ET.Element | None, attr: str, default: float = 0.0) -> float:
    if el is None:
        return default
    raw = el.get(f"{{{W_NS['w']}}}{attr}") or el.get(attr)
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def paragraph_flow_bbox(p: ET.Element, metrics: DocxPageMetrics, cursor: LayoutCursor) -> BBox:
    p_pr = p.find("w:pPr", W_NS)
    before = 0.0
    after = 0.0
    line_twips = 240.0
    indent_left = 0.0
    indent_right = 0.0

    if p_pr is not None:
        spacing = p_pr.find("w:spacing", W_NS)
        if spacing is not None:
            before = _twips_attr(spacing, "before")
            after = _twips_attr(spacing, "after")
            line_raw = _twips_attr(spacing, "line", 240.0)
            line_rule = spacing.get(f"{{{W_NS['w']}}}lineRule") or spacing.get("lineRule") or "auto"
            if line_rule == "auto" and line_raw:
                line_twips = line_raw / 20.0
            elif line_raw:
                line_twips = line_raw

        ind = p_pr.find("w:ind", W_NS)
        if ind is not None:
            indent_left = _twips_attr(ind, "left")
            indent_right = _twips_attr(ind, "right")

    before_n = before / metrics.content_height_twips
    after_n = after / metrics.content_height_twips
    line_n = max(line_twips / metrics.content_height_twips, 0.025)

    cursor.y = clamp_01(cursor.y + before_n)
    x = clamp_01(metrics.margin_left_norm + indent_left / metrics.page_width_twips)
    width = clamp_01(metrics.content_width_norm - indent_left / metrics.page_width_twips - indent_right / metrics.page_width_twips)
    height = min(line_n, max(0.02, 1.0 - cursor.y))

    bbox = BBox(x=x, y=cursor.y, width=max(width, 0.1), height=height)
    cursor.y = clamp_01(cursor.y + height + after_n)
    cursor.block_index += 1
    return bbox


def table_flow_bbox(row_count: int, metrics: DocxPageMetrics, cursor: LayoutCursor) -> BBox:
    row_h = max(0.035, min(0.08 * max(row_count, 1), metrics.content_height_norm * 0.85))
    x = metrics.margin_left_norm
    width = metrics.content_width_norm
    cursor.y = clamp_01(cursor.y)
    height = min(row_h, max(0.05, 1.0 - cursor.y))
    bbox = BBox(x=x, y=cursor.y, width=width, height=height)
    cursor.y = clamp_01(cursor.y + height)
    cursor.block_index += 1
    return bbox


def drawing_bbox(drawing: ET.Element, metrics: DocxPageMetrics, *, fallback: BBox) -> BBox:
    anchor = drawing.find(".//wp:anchor", WP_NS)
    inline = drawing.find(".//wp:inline", WP_NS)
    container = anchor if anchor is not None else inline
    if container is None:
        return fallback

    extent = container.find("wp:extent", WP_NS)
    if extent is None:
        return fallback

    try:
        cx = int(extent.get("cx", "0"))
        cy = int(extent.get("cy", "0"))
    except ValueError:
        return fallback

    if anchor is not None:
        x_emu = _resolve_axis_emu(anchor, "H", metrics, span_emu=cx)
        y_emu = _resolve_axis_emu(anchor, "V", metrics, span_emu=cy)
    else:
        x_emu = metrics.margin_left_twips * EMU_PER_TWIP
        y_emu = metrics.margin_top_twips * EMU_PER_TWIP

    page_w_emu = metrics.page_width_twips * EMU_PER_TWIP
    page_h_emu = metrics.page_height_twips * EMU_PER_TWIP

    x = clamp_01(x_emu / page_w_emu) if page_w_emu else fallback.x
    y = clamp_01(y_emu / page_h_emu) if page_h_emu else fallback.y
    w = clamp_01(cx / page_w_emu) if page_w_emu else fallback.width
    h = clamp_01(cy / page_h_emu) if page_h_emu else fallback.height

    w = max(min(w, 1.0 - x), 0.03)
    h = max(min(h, 1.0 - y), 0.03)
    return BBox(x=x, y=y, width=w, height=h)


def _resolve_axis_emu(
    container: ET.Element,
    axis: str,
    metrics: DocxPageMetrics,
    *,
    span_emu: int,
) -> float:
    pos = container.find(f"wp:position{axis}", WP_NS)
    if pos is None:
        return metrics.margin_top_twips * EMU_PER_TWIP if axis == "V" else metrics.margin_left_twips * EMU_PER_TWIP

    relative = pos.get("relativeFrom", "page")
    align_el = pos.find(f"wp:align", WP_NS)
    offset_el = pos.find(f"wp:posOffset", WP_NS)
    offset = int(offset_el.text) if offset_el is not None and offset_el.text else 0

    if axis == "H":
        base = metrics.margin_left_twips * EMU_PER_TWIP
        span = metrics.content_width_twips * EMU_PER_TWIP
        page = metrics.page_width_twips * EMU_PER_TWIP
    else:
        base = metrics.margin_top_twips * EMU_PER_TWIP
        span = metrics.content_height_twips * EMU_PER_TWIP
        page = metrics.page_height_twips * EMU_PER_TWIP

    if relative in {"margin", "column", "leftMargin", "rightMargin"}:
        origin = base
    else:
        origin = 0.0

    if align_el is not None and align_el.text:
        align = align_el.text
        if align in {"left", "inside"}:
            return origin + offset
        if align in {"right", "outside"}:
            return origin + span - span_emu - offset
        if align == "center":
            return origin + (span - span_emu) / 2 + offset

    return origin + offset


def textbox_text(drawing: ET.Element) -> str | None:
    """Extract text from WordprocessingML text box in a drawing."""
    txbx = drawing.find(".//wps:txbx", WPS_NS)
    if txbx is None:
        txbx = drawing.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent")
    if txbx is None:
        for el in drawing.iter():
            if local_name(el.tag) == "txbxContent":
                txbx = el
                break
    if txbx is None:
        return None

    lines: list[str] = []
    for p in txbx.findall(".//w:p", W_NS):
        parts: list[str] = []
        for t in p.findall(".//w:t", W_NS):
            if t.text:
                parts.append(t.text)
        line = "".join(parts).strip()
        if line:
            lines.append(line)
    joined = "\n".join(lines).strip()
    return joined or None


def anchor_z_order(drawing: ET.Element, base: int) -> int:
    anchor = drawing.find(".//wp:anchor", WP_NS)
    if anchor is None:
        return base
    behind = anchor.get("behindDoc", "0")
    if behind in {"1", "true"}:
        return max(base - 1000, 0)
    return base + 100

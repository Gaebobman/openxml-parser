from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


@dataclass
class _CellSlot:
    text: str
    col_span: int
    vmerge: str | None
    row_span: int
    formatted_text: str = ""


@dataclass
class ParsedTableCell:
    row: int
    col: int
    text: str | None
    is_spanned: bool
    span_width: int
    span_height: int
    is_merge_origin: bool
    formatted_text: str | None = None


@dataclass
class ParsedTable:
    col_widths: list[float]
    row_heights: list[float]
    cells: list[ParsedTableCell]


def extract_tables_from_pptx(pptx_path: Path) -> dict[int, list[ParsedTable]]:
    out: dict[int, list[ParsedTable]] = {}
    with zipfile.ZipFile(pptx_path) as zf:
        slide_paths = _list_slide_paths(zf)
        for slide_idx, slide_path in enumerate(slide_paths, start=1):
            root = _read_xml(zf, slide_path)
            tables: list[ParsedTable] = []
            for tbl in root.findall(".//a:tbl", NS):
                tables.append(_parse_table(tbl))
            if tables:
                out[slide_idx] = tables
    return out


def _read_xml(zf: zipfile.ZipFile, path: str) -> ET.Element:
    with zf.open(path) as file:
        return ET.fromstring(file.read())


def _list_slide_paths(zf: zipfile.ZipFile) -> list[str]:
    slide_paths = [n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]

    def key(name: str) -> int:
        stem = Path(name).stem
        num = "".join(ch for ch in stem if ch.isdigit())
        return int(num) if num else 0

    return sorted(slide_paths, key=key)


def _parse_table(tbl: ET.Element) -> ParsedTable:
    col_widths = _table_col_widths(tbl)
    row_heights = _table_row_heights(tbl)
    tr_nodes = tbl.findall("a:tr", NS)

    col_count = max(len(col_widths), _estimate_columns(tbl), 1)
    if not row_heights:
        row_heights = [1.0 for _ in tr_nodes]
    if len(row_heights) < len(tr_nodes):
        row_heights.extend([1.0 for _ in range(len(tr_nodes) - len(row_heights))])
    if not col_widths:
        col_widths = [1.0 for _ in range(col_count)]
    if len(col_widths) < col_count:
        col_widths.extend([1.0 for _ in range(col_count - len(col_widths))])

    tc_rows = [tr.findall("a:tc", NS) for tr in tr_nodes]
    grid_slots: list[list[_CellSlot | None]] = [[None for _ in range(col_count)] for _ in range(len(tc_rows))]

    for r_idx, tcs in enumerate(tc_rows):
        col_idx = 0
        tc_idx = 0
        while tc_idx < len(tcs):
            tc = tcs[tc_idx]
            if _is_hmerge_continue(_get_hmerge(tc)):
                tc_idx += 1
                continue
            while col_idx < col_count and grid_slots[r_idx][col_idx] is not None:
                col_idx += 1
            if col_idx >= col_count:
                break

            col_span = max(1, _get_grid_span(tc))
            next_idx = tc_idx + 1
            extra_hmerge = 0
            while next_idx < len(tcs) and _is_hmerge_continue(_get_hmerge(tcs[next_idx])):
                extra_hmerge += 1
                next_idx += 1
            if col_span == 1 and extra_hmerge > 0:
                col_span = 1 + extra_hmerge
            col_span = min(col_span, col_count - col_idx)

            slot = _CellSlot(
                text=_cell_text(tc),
                col_span=col_span,
                vmerge=_get_vmerge(tc),
                row_span=max(1, _get_row_span(tc)),
                formatted_text=_cell_formatted_text(tc),
            )
            for c in range(col_idx, col_idx + col_span):
                grid_slots[r_idx][c] = slot

            col_idx += col_span
            tc_idx = next_idx

    for r_idx, row in enumerate(grid_slots):
        c = 0
        while c < col_count:
            slot = row[c]
            if slot is None:
                c += 1
                continue
            if c > 0 and row[c - 1] is slot:
                c += 1
                continue
            if _is_vmerge_continue(slot.vmerge):
                c += slot.col_span
                continue
            if slot.row_span <= 1:
                span = 1
                for rr in range(r_idx + 1, len(grid_slots)):
                    if _row_has_vmerge_continue(grid_slots, rr, c, slot.col_span):
                        span += 1
                    else:
                        break
                slot.row_span = span
            c += slot.col_span

    cells: list[ParsedTableCell] = []
    for r_idx, row in enumerate(grid_slots):
        for c_idx, slot in enumerate(row):
            if slot is None:
                cells.append(
                    ParsedTableCell(
                        row=r_idx,
                        col=c_idx,
                        text=None,
                        is_spanned=True,
                        span_width=1,
                        span_height=1,
                        is_merge_origin=False,
                    )
                )
                continue

            is_origin = not (c_idx > 0 and row[c_idx - 1] is slot) and not _is_vmerge_continue(slot.vmerge)
            if is_origin:
                cells.append(
                    ParsedTableCell(
                        row=r_idx,
                        col=c_idx,
                        text=slot.text or None,
                        is_spanned=False,
                        span_width=max(1, slot.col_span),
                        span_height=max(1, slot.row_span),
                        is_merge_origin=(slot.col_span > 1 or slot.row_span > 1),
                        formatted_text=slot.formatted_text or None,
                    )
                )
            else:
                cells.append(
                    ParsedTableCell(
                        row=r_idx,
                        col=c_idx,
                        text=None,
                        is_spanned=True,
                        span_width=1,
                        span_height=1,
                        is_merge_origin=False,
                    )
                )
    return ParsedTable(col_widths=col_widths, row_heights=row_heights, cells=cells)


def _table_col_widths(tbl: ET.Element) -> list[float]:
    grid = tbl.find("a:tblGrid", NS)
    if grid is None:
        return []
    out: list[float] = []
    for col in grid.findall("a:gridCol", NS):
        out.append(float(_safe_int(col.get("w"), 1)))
    return out


def _table_row_heights(tbl: ET.Element) -> list[float]:
    out: list[float] = []
    for tr in tbl.findall("a:tr", NS):
        out.append(float(_safe_int(tr.get("h"), 1)))
    return out


def _cell_text(tc: ET.Element) -> str:
    tx_body = tc.find("a:txBody", NS)
    if tx_body is None:
        return ""
    return paragraphs_with_bullets(tx_body.findall("a:p", NS), NS)


def _cell_formatted_text(tc: ET.Element) -> str:
    tx_body = tc.find("a:txBody", NS)
    if tx_body is None:
        return ""
    return paragraphs_with_formatting(tx_body.findall("a:p", NS), NS, mode="html")


# ---------------------------------------------------------------------------
# Bullet / numbering prefix extraction
# ---------------------------------------------------------------------------
# Works with both stdlib xml.etree.ElementTree and lxml elements.

def paragraphs_with_bullets(p_elements: list, ns: dict) -> str:
    """Join <a:p> elements into text, prepending bullet/number prefixes."""
    lines: list[str] = []
    counters: dict[int, int] = {}
    for p in p_elements:
        runs = [t.text for t in p.findall(".//a:t", ns) if t.text]
        line = "".join(runs).strip()
        if not line:
            counters.clear()
            continue
        prefix = _bullet_prefix(p, counters, ns)
        lines.append(prefix + line)
    return "\n".join(lines)


def paragraphs_with_formatting(p_elements: list, ns: dict, *, mode: str = "markdown") -> str:
    """Join <a:p> elements preserving bold/italic/underline per run.

    *mode* selects the output wrapping style:
      - ``"markdown"``: ``**bold**``, ``*italic*``, ``<u>underline</u>``
      - ``"html"``:      ``<b>``, ``<i>``, ``<u>`` tags

    Dominant formatting (>= 80% of character count shares the same style)
    is suppressed — it's a default style, not emphasis.  Adjacent runs
    with the same effective style are merged before wrapping to avoid
    broken markers like ``****``.
    """
    all_runs = _collect_runs(p_elements, ns)
    dominant = _detect_dominant_style(all_runs)

    lines: list[str] = []
    counters: dict[int, int] = {}
    for p in p_elements:
        raw_runs: list[tuple[str, _RunStyle]] = []
        for r in p.findall("a:r", ns):
            t_el = r.find("a:t", ns)
            if t_el is None or not t_el.text:
                continue
            rPr = r.find("a:rPr", ns)
            raw_runs.append((t_el.text, _parse_run_style(rPr)))
        merged = _merge_adjacent_runs(raw_runs, dominant)
        line = "".join(_wrap_run(text, style, mode) for text, style in merged).strip()
        if not line:
            counters.clear()
            continue
        prefix = _bullet_prefix(p, counters, ns)
        lines.append(prefix + line)
    return "\n".join(lines)


@dataclass
class _RunStyle:
    bold: bool = False
    italic: bool = False
    underline: bool = False


def _parse_run_style(rPr) -> _RunStyle:
    if rPr is None:
        return _RunStyle()
    is_bold = rPr.get("b") in {"1", "true"}
    is_italic = rPr.get("i") in {"1", "true"}
    underline = rPr.get("u", "none")
    is_underline = underline not in {"none", "0", "", None}
    return _RunStyle(bold=is_bold, italic=is_italic, underline=is_underline)


def _collect_runs(p_elements: list, ns: dict) -> list[tuple[str, _RunStyle]]:
    runs: list[tuple[str, _RunStyle]] = []
    for p in p_elements:
        for r in p.findall("a:r", ns):
            t_el = r.find("a:t", ns)
            if t_el is None or not t_el.text:
                continue
            rPr = r.find("a:rPr", ns)
            runs.append((t_el.text, _parse_run_style(rPr)))
    return runs


def _detect_dominant_style(runs: list[tuple[str, _RunStyle]]) -> _RunStyle:
    """If >= 80% of characters share a style flag, suppress it."""
    if not runs:
        return _RunStyle()
    total_chars = sum(len(t) for t, _ in runs)
    if total_chars == 0:
        return _RunStyle()
    bold_chars = sum(len(t) for t, s in runs if s.bold)
    italic_chars = sum(len(t) for t, s in runs if s.italic)
    underline_chars = sum(len(t) for t, s in runs if s.underline)
    threshold = 0.8
    return _RunStyle(
        bold=bold_chars / total_chars >= threshold,
        italic=italic_chars / total_chars >= threshold,
        underline=underline_chars / total_chars >= threshold,
    )


def _effective_style(style: _RunStyle, dominant: _RunStyle) -> _RunStyle:
    return _RunStyle(
        bold=style.bold and not dominant.bold,
        italic=style.italic and not dominant.italic,
        underline=style.underline and not dominant.underline,
    )


def _merge_adjacent_runs(
    runs: list[tuple[str, _RunStyle]], dominant: _RunStyle,
) -> list[tuple[str, _RunStyle]]:
    """Merge consecutive runs whose effective style is identical."""
    if not runs:
        return []
    merged: list[tuple[str, _RunStyle]] = []
    for text, style in runs:
        eff = _effective_style(style, dominant)
        if merged and merged[-1][1] == eff:
            merged[-1] = (merged[-1][0] + text, eff)
        else:
            merged.append((text, eff))
    return merged


def _wrap_run(text: str, style: _RunStyle, mode: str) -> str:
    if not style.bold and not style.italic and not style.underline:
        return text
    result = text
    if mode == "html":
        if style.underline:
            result = f"<u>{result}</u>"
        if style.italic:
            result = f"<i>{result}</i>"
        if style.bold:
            result = f"<b>{result}</b>"
    else:
        if style.underline:
            result = f"<u>{result}</u>"
        if style.italic:
            result = f"*{result}*"
        if style.bold:
            result = f"**{result}**"
    return result


def _bullet_prefix(p, counters: dict[int, int], ns: dict) -> str:
    pPr = p.find("a:pPr", ns)
    if pPr is None:
        return ""

    level = int(pPr.get("lvl") or "0")

    if pPr.find("a:buNone", ns) is not None:
        return ""

    bu_auto = pPr.find("a:buAutoNum", ns)
    if bu_auto is not None:
        num_type = bu_auto.get("type", "arabicPeriod")
        start_at = int(bu_auto.get("startAt") or "1")
        if level not in counters:
            counters[level] = start_at
        else:
            counters[level] += 1
        for k in list(counters):
            if k > level:
                del counters[k]
        return _format_auto_num(counters[level], num_type)

    bu_char = pPr.find("a:buChar", ns)
    if bu_char is not None:
        char = bu_char.get("char", "\u2022")
        return f"{char} "

    return ""


_CIRCLED_NUMS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def _format_auto_num(n: int, num_type: str) -> str:
    if "circleNum" in num_type:
        idx = n - 1
        if 0 <= idx < len(_CIRCLED_NUMS):
            return f"{_CIRCLED_NUMS[idx]} "
        return f"({n}) "

    fmt = _AUTO_NUM_FORMATS.get(num_type)
    if fmt is None:
        return f"{n}. "
    return fmt(n)


def _roman(n: int) -> str:
    vals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    result = ""
    for val, sym in vals:
        while n >= val:
            result += sym
            n -= val
    return result


_AUTO_NUM_FORMATS: dict[str, object] = {
    "arabicPeriod": lambda n: f"{n}. ",
    "arabicParenR": lambda n: f"{n}) ",
    "arabicPlain": lambda n: f"{n} ",
    "alphaLcPeriod": lambda n: f"{chr(ord('a') + (n - 1) % 26)}. ",
    "alphaLcParenR": lambda n: f"{chr(ord('a') + (n - 1) % 26)}) ",
    "alphaUcPeriod": lambda n: f"{chr(ord('A') + (n - 1) % 26)}. ",
    "alphaUcParenR": lambda n: f"{chr(ord('A') + (n - 1) % 26)}) ",
    "romanLcPeriod": lambda n: f"{_roman(n).lower()}. ",
    "romanLcParenR": lambda n: f"{_roman(n).lower()}) ",
    "romanUcPeriod": lambda n: f"{_roman(n)}. ",
    "romanUcParenR": lambda n: f"{_roman(n)}) ",
}


def _get_grid_span(tc: ET.Element) -> int:
    if tc.get("gridSpan"):
        return _safe_int(tc.get("gridSpan"), 1)
    tc_pr = tc.find("a:tcPr", NS)
    if tc_pr is None:
        return 1
    return _safe_int(tc_pr.get("gridSpan"), 1)


def _get_row_span(tc: ET.Element) -> int:
    row_span = tc.get("rowSpan")
    if row_span:
        return _safe_int(row_span, 1)
    tc_pr = tc.find("a:tcPr", NS)
    if tc_pr is not None and tc_pr.get("rowSpan"):
        return _safe_int(tc_pr.get("rowSpan"), 1)
    return 1


def _get_vmerge(tc: ET.Element) -> str | None:
    vmerge = tc.get("vMerge")
    if vmerge:
        return vmerge
    tc_pr = tc.find("a:tcPr", NS)
    if tc_pr is not None:
        if tc_pr.get("vMerge"):
            return tc_pr.get("vMerge")
        vmerge_el = tc_pr.find("a:vMerge", NS)
        if vmerge_el is not None:
            val = vmerge_el.get("val")
            if val is None:
                return "continue"
            return val
    return None


def _get_hmerge(tc: ET.Element) -> str | None:
    hmerge = tc.get("hMerge")
    if hmerge:
        return hmerge
    tc_pr = tc.find("a:tcPr", NS)
    if tc_pr is not None:
        if tc_pr.get("hMerge"):
            return tc_pr.get("hMerge")
        hmerge_el = tc_pr.find("a:hMerge", NS)
        if hmerge_el is not None:
            val = hmerge_el.get("val")
            if val is None:
                return "continue"
            return val
    return None


_MERGE_CONTINUE_VALUES = {"1", "true", "continue"}


def _is_hmerge_continue(hmerge: str | None) -> bool:
    return hmerge in _MERGE_CONTINUE_VALUES


def _is_vmerge_continue(vmerge: str | None) -> bool:
    return vmerge in _MERGE_CONTINUE_VALUES


def _row_has_vmerge_continue(
    grid_slots: list[list[_CellSlot | None]],
    row_idx: int,
    col_idx: int,
    col_span: int,
) -> bool:
    row = grid_slots[row_idx]
    for c in range(col_idx, min(col_idx + col_span, len(row))):
        slot = row[c]
        if slot is None:
            return False
        if not _is_vmerge_continue(slot.vmerge):
            return False
    return True


def _estimate_columns(tbl: ET.Element) -> int:
    max_cols = 0
    for tr in tbl.findall("a:tr", NS):
        cur = 0
        tcs = tr.findall("a:tc", NS)
        tc_idx = 0
        while tc_idx < len(tcs):
            tc = tcs[tc_idx]
            if _is_hmerge_continue(_get_hmerge(tc)):
                tc_idx += 1
                continue
            col_span = max(1, _get_grid_span(tc))
            next_idx = tc_idx + 1
            extra_hmerge = 0
            while next_idx < len(tcs) and _is_hmerge_continue(_get_hmerge(tcs[next_idx])):
                extra_hmerge += 1
                next_idx += 1
            if col_span == 1 and extra_hmerge > 0:
                col_span = 1 + extra_hmerge
            cur += col_span
            tc_idx = next_idx
        if cur > max_cols:
            max_cols = cur
    return max_cols


def _safe_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


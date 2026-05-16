from __future__ import annotations

import xml.etree.ElementTree as ET

from openxml_parser.infrastructure.ingestors._ooxml_utils import local_name, text_content

W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def paragraph_text_and_meta(p: ET.Element) -> tuple[str, dict[str, object]]:
    """Extract visible text and structural metadata from a Word paragraph."""
    meta: dict[str, object] = {"source_format": "docx"}
    p_pr = p.find("w:pPr", W_NS)

    if p_pr is not None:
        p_style = p_pr.find("w:pStyle", W_NS)
        if p_style is not None:
            style_val = p_style.get(f"{{{W_NS['w']}}}val") or p_style.get("val")
            if style_val:
                meta["paragraph_style"] = style_val
                if str(style_val).lower().startswith("heading"):
                    digits = "".join(ch for ch in str(style_val) if ch.isdigit())
                    meta["heading_level"] = int(digits) if digits else 1
                    meta["is_heading"] = True

        num_pr = p_pr.find("w:numPr", W_NS)
        if num_pr is not None:
            ilvl_el = num_pr.find("w:ilvl", W_NS)
            ilvl = 0
            if ilvl_el is not None:
                raw = ilvl_el.get(f"{{{W_NS['w']}}}val") or ilvl_el.get("val") or "0"
                try:
                    ilvl = int(raw)
                except ValueError:
                    ilvl = 0
            meta["list_level"] = ilvl
            meta["is_list_item"] = True

    parts: list[str] = []
    for child in p:
        ln = local_name(child.tag)
        if ln == "r":
            if child.find(".//w:drawing", W_NS) is not None or child.find(".//w:pict", W_NS) is not None:
                continue
            t = _run_text(child)
            if t:
                parts.append(t)
        elif ln == "hyperlink":
            t = text_content(child, ns=W_NS)
            if t:
                parts.append(t)

    body = "".join(parts).strip()
    if meta.get("is_list_item") and body:
        indent = "  " * int(meta.get("list_level", 0))
        body = f"{indent}- {body}"

    return body, meta


def _run_text(run: ET.Element) -> str:
    """Text from run children only (exclude nested drawings/text boxes)."""
    parts: list[str] = []
    for node in run:
        if local_name(node.tag) == "t" and node.text:
            parts.append(node.text)
    return "".join(parts).strip()

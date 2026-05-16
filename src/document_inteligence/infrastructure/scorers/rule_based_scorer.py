"""Rule-based relation scorer.

Scores candidate relations using spatial heuristics (proximity,
alignment, size ratio, relative position, text-style hints) with
configurable weights.
"""
from __future__ import annotations

from document_inteligence.application.config import ParserConfig
from document_inteligence.domain.entities import DocumentElement, DocumentPage, ElementType
from document_inteligence.domain.repositories import RelationScorer

_CAPTION_KEYWORDS = frozenset(("figure", "fig.", "fig", "그림", "표", "table", "chart", "도표"))


class RuleBasedScorer(RelationScorer):

    def __init__(self, config: ParserConfig) -> None:
        self._cfg = config

    def score(
        self,
        source: DocumentElement,
        target: DocumentElement,
        page: DocumentPage,
    ) -> list[dict]:
        results: list[dict] = []

        if self._is_title_candidate(source) and source.element_id != target.element_id:
            results.append({
                "type": "title_of",
                "score": 0.7,
                "metadata": {},
            })

        caption_score = self._caption_score(source, target)
        if caption_score is not None:
            results.append(caption_score)

        return results

    # ------------------------------------------------------------------
    # Title detection
    # ------------------------------------------------------------------

    def _is_title_candidate(self, element: DocumentElement) -> bool:
        if bool(element.metadata.get("is_placeholder")):
            return True
        text = (element.text or "").strip()
        return (
            element.element_type == ElementType.TEXT
            and bool(text)
            and len(text) <= self._cfg.title_max_len
            and "\n" not in text
        )

    # ------------------------------------------------------------------
    # Caption / illustrates scoring
    # ------------------------------------------------------------------

    def _caption_score(
        self,
        text_elem: DocumentElement,
        visual_elem: DocumentElement,
    ) -> dict | None:
        if text_elem.element_type != ElementType.TEXT:
            return None
        if visual_elem.element_type not in {ElementType.IMAGE, ElementType.TABLE}:
            return None

        txt = (text_elem.text or "").strip()
        if not txt:
            return None

        cfg = self._cfg
        vx1 = visual_elem.bbox.x
        vx2 = vx1 + visual_elem.bbox.width
        vy1 = visual_elem.bbox.y
        vy2 = vy1 + visual_elem.bbox.height
        tx1 = text_elem.bbox.x
        tx2 = tx1 + text_elem.bbox.width
        ty1 = text_elem.bbox.y
        ty2 = ty1 + text_elem.bbox.height

        overlap = max(0.0, min(vx2, tx2) - max(vx1, tx1))
        min_width = max(min(vx2 - vx1, tx2 - tx1), 1e-6)
        overlap_ratio = overlap / min_width
        if overlap_ratio < (1.0 - cfg.alignment_tolerance):
            return None

        gap_below = ty1 - vy2
        gap_above = vy1 - ty2
        valid_gaps = [g for g in (gap_below, gap_above) if g >= 0.0]
        if not valid_gaps:
            return None
        gap = min(valid_gaps)
        if gap > cfg.caption_max_gap:
            return None

        proximity = max(0.0, 1.0 - (gap / max(cfg.caption_max_gap, 1e-6)))
        alignment = min(1.0, max(0.0, overlap_ratio))

        text_area = max(text_elem.bbox.width * text_elem.bbox.height, 1e-9)
        visual_area = max(visual_elem.bbox.width * visual_elem.bbox.height, 1e-9)
        ratio = text_area / visual_area
        size_ratio_score = 1.0 if ratio < 0.5 else max(0.0, 1.0 - ratio)

        is_below = gap_below >= 0 and gap_below <= cfg.caption_max_gap
        is_above = gap_above >= 0 and gap_above <= cfg.caption_max_gap
        position_score = 0.8 if is_below else (0.6 if is_above else 0.3)

        length = len(txt)
        length_score = 1.0 if 8 <= length <= 120 else 0.5 if 1 <= length <= 180 else 0.0
        keyword_score = 1.0 if any(k in txt.lower() for k in _CAPTION_KEYWORDS) else 0.0
        text_hint = max(length_score, keyword_score)
        bullet_penalty = 0.3 if txt.startswith(("-", "•", "·")) else 0.0

        raw = (
            cfg.rel_proximity_weight * proximity
            + cfg.rel_alignment_weight * alignment
            + cfg.rel_size_ratio_weight * size_ratio_score
            + cfg.rel_position_weight * position_score
            + cfg.rel_text_hint_weight * text_hint
            - bullet_penalty
        )
        final = max(0.0, min(1.0, raw))

        breakdown = {
            "proximity": round(proximity, 4),
            "alignment": round(alignment, 4),
            "size_ratio_score": round(size_ratio_score, 4),
            "position_score": round(position_score, 4),
            "text_hint": round(text_hint, 4),
            "bullet_penalty": round(bullet_penalty, 4),
            "raw_score": round(raw, 4),
            "final_score": round(final, 4),
        }

        if final >= cfg.caption_rule_threshold:
            rel_type = "caption_of"
        elif final >= cfg.caption_vlm_threshold:
            rel_type = "related_to"
        else:
            return None

        return {
            "type": rel_type,
            "score": final,
            "metadata": {
                "caption_text": txt,
                "score_breakdown": breakdown,
                "is_below": is_below,
            },
        }

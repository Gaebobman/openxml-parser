"""Relation detection between document elements.

Uses the ``RelationScorer`` port to score candidate pairs and an
optional ``RelationReranker`` to filter/reorder the candidates.
Falls back to the built-in ``RuleBasedScorer`` and
``NoopRelationReranker`` when no custom implementations are supplied.
"""
from __future__ import annotations

from openxml_parser.application.config import ParserConfig
from openxml_parser.domain.entities import (
    DocumentElement,
    DocumentPage,
    ElementRelation,
    ElementType,
)
from openxml_parser.domain.repositories import (
    CaptionVerifier,
    RelationReranker,
    RelationScorer,
)


def detect_relations(
    pages: list[DocumentPage],
    config: ParserConfig,
    caption_verifier: CaptionVerifier | None = None,
    scorer: RelationScorer | None = None,
    reranker: RelationReranker | None = None,
) -> list[ElementRelation]:
    if scorer is None:
        from openxml_parser.infrastructure.scorers.rule_based_scorer import (
            RuleBasedScorer,
        )
        scorer = RuleBasedScorer(config)
    if reranker is None:
        from openxml_parser.infrastructure.rerankers.noop_reranker import (
            NoopRelationReranker,
        )
        reranker = NoopRelationReranker()

    relations: list[ElementRelation] = []
    for page in pages:
        relations.extend(
            _detect_page_relations(page, config, caption_verifier, scorer, reranker)
        )
    return relations


def _detect_page_relations(
    page: DocumentPage,
    config: ParserConfig,
    caption_verifier: CaptionVerifier | None,
    scorer: RelationScorer,
    reranker: RelationReranker,
) -> list[ElementRelation]:
    out: list[ElementRelation] = []
    texts = [
        e for e in page.elements
        if e.element_type == ElementType.TEXT and (e.text or "").strip()
    ]
    visuals = [
        e for e in page.elements
        if e.element_type in {ElementType.IMAGE, ElementType.TABLE}
    ]
    candidate_decisions: list[dict[str, object]] = []

    # Skip elements already absorbed into table cells
    absorbed_ids = _absorbed_element_ids(page)

    # ---- title_of (spatially scoped) ----
    title = _find_title(texts, config)
    if title is not None:
        for target in page.elements:
            if target.element_id == title.element_id:
                continue
            if not _is_title_target(title, target, config):
                continue
            out.append(
                ElementRelation(
                    relation_type="title_of",
                    source_element_id=title.element_id,
                    target_element_id=target.element_id,
                    confidence=0.7,
                )
            )

    # ---- caption_of / related_to / illustrates ----
    scored_candidates: list[dict] = []
    for visual in visuals:
        visual_has_candidate = False
        for text in texts:
            if text.element_id in absorbed_ids:
                continue
            scores = scorer.score(text, visual, page)
            for s in scores:
                if s["type"] in ("caption_of", "related_to", "illustrates"):
                    scored_candidates.append({
                        "text": text,
                        "visual": visual,
                        "type": s["type"],
                        "score": s["score"],
                        "metadata": s.get("metadata", {}),
                    })
                    visual_has_candidate = True
        if not visual_has_candidate:
            candidate_decisions.append({
                "target_element_id": visual.element_id,
                "candidate_element_id": None,
                "candidate_rank": None,
                "rejected_reason": "no_candidate",
            })

    reranked = reranker.rerank(scored_candidates, page)

    # Apply VLM fallback for ambiguous candidates
    final_candidates = _apply_vlm_fallback(reranked, config, caption_verifier, page)

    # Greedy global assignment: confidence descending, no double-assign
    final_candidates.sort(key=lambda c: c["score"], reverse=True)
    used_text_ids: set[str] = set()
    used_visual_for_title: dict[str, set[str]] = {}

    for cand in final_candidates:
        text_elem: DocumentElement = cand["text"]
        visual_elem: DocumentElement = cand["visual"]
        rel_type: str = cand["type"]
        score: float = cand["score"]
        meta: dict = cand.get("metadata", {})

        decision: dict[str, object] = {
            "target_element_id": visual_elem.element_id,
            "candidate_element_id": text_elem.element_id,
            "rule_score": score,
            "score_breakdown": meta.get("score_breakdown", {}),
        }

        if text_elem.element_id in used_text_ids:
            decision["rejected_reason"] = "caption_already_assigned"
            candidate_decisions.append(decision)
            continue

        # If visual already has caption_of and this is title_of for same visual, skip title
        visual_rels = used_visual_for_title.setdefault(visual_elem.element_id, set())
        if rel_type == "caption_of" and "title_of" in visual_rels:
            pass
        if rel_type == "title_of" and "caption_of" in visual_rels:
            decision["rejected_reason"] = "caption_takes_priority"
            candidate_decisions.append(decision)
            continue

        used_text_ids.add(text_elem.element_id)
        visual_rels.add(rel_type)

        out.append(
            ElementRelation(
                relation_type=rel_type,
                source_element_id=text_elem.element_id,
                target_element_id=visual_elem.element_id,
                confidence=score,
                metadata={
                    "page_number": page.page_number,
                    "method": cand.get("method", "rule"),
                    "rule_score": score,
                    "caption_text": meta.get("caption_text", ""),
                    "score_breakdown": meta.get("score_breakdown", {}),
                    "rejected_reason": None,
                },
            )
        )
        decision["rejected_reason"] = None
        decision["method"] = cand.get("method", "rule")
        decision["confidence"] = score
        candidate_decisions.append(decision)

    page.metadata["caption_candidate_decisions"] = candidate_decisions
    return out


# ---- helpers ----

def _find_title(texts: list[DocumentElement], config: ParserConfig) -> DocumentElement | None:
    return next((t for t in texts if _looks_like_title(t, config)), None)


def _looks_like_title(element: DocumentElement, config: ParserConfig) -> bool:
    if bool(element.metadata.get("is_placeholder")):
        return True
    text = (element.text or "").strip()
    return bool(text) and len(text) <= config.title_max_len and "\n" not in text


def _is_title_target(
    title: DocumentElement, target: DocumentElement, config: ParserConfig
) -> bool:
    """Only link title to targets below it and within max Y distance."""
    if target.bbox.y < title.bbox.y:
        return False
    y_gap = target.bbox.y - (title.bbox.y + title.bbox.height)
    return y_gap <= config.title_max_y_distance


def _absorbed_element_ids(page: DocumentPage) -> set[str]:
    ids: set[str] = set()
    for e in page.elements:
        if e.metadata.get("absorbed_by"):
            ids.add(e.element_id)
        if e.metadata.get("absorbed_by_table"):
            ids.add(e.element_id)
    return ids


def _apply_vlm_fallback(
    candidates: list[dict],
    config: ParserConfig,
    verifier: CaptionVerifier | None,
    page: DocumentPage,
) -> list[dict]:
    """For 'related_to' candidates, try VLM promotion to caption_of."""
    result: list[dict] = []
    for cand in candidates:
        if cand["type"] == "related_to" and verifier is not None:
            text_elem: DocumentElement = cand["text"]
            visual_elem: DocumentElement = cand["visual"]
            is_caption, vlm_conf = verifier.verify(
                page_number=page.page_number,
                image_element_id=visual_elem.element_id,
                caption_element_id=text_elem.element_id,
                caption_text=(text_elem.text or "").strip(),
            )
            if is_caption:
                cand = {**cand, "type": "caption_of", "score": vlm_conf, "method": "vlm_fallback"}
            else:
                cand = {**cand, "method": "vlm_rejected"}
        result.append(cand)
    return result

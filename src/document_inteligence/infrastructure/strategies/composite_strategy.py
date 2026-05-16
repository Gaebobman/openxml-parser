"""Composite reading-order strategy.

Elements with a ``placeholder_idx`` metadata field are ordered by that
index first.  Remaining elements are ordered by a fallback strategy
(defaults to XY-Cut).
"""
from __future__ import annotations

from document_inteligence.domain.entities import DocumentElement, DocumentPage
from document_inteligence.domain.repositories import ReadingOrderStrategy
from document_inteligence.infrastructure.strategies.xy_cut_strategy import XYCutStrategy


class CompositeStrategy(ReadingOrderStrategy):
    """Placeholder-index first, then fallback strategy for the rest."""

    def __init__(self, fallback: ReadingOrderStrategy | None = None) -> None:
        self._fallback = fallback or XYCutStrategy()

    def order(
        self, elements: list[DocumentElement], page: DocumentPage
    ) -> list[DocumentElement]:
        if not elements:
            return []

        with_idx: list[tuple[int, DocumentElement]] = []
        without_idx: list[DocumentElement] = []
        for e in elements:
            pidx = e.metadata.get("placeholder_idx")
            if pidx is not None:
                with_idx.append((int(pidx), e))
            else:
                without_idx.append(e)

        indexed_ordered = [e for _, e in sorted(with_idx, key=lambda t: t[0])]
        for e in indexed_ordered:
            e.metadata.setdefault("spatial_group", "ph")
        rest_ordered = self._fallback.order(without_idx, page)
        return indexed_ordered + rest_ordered

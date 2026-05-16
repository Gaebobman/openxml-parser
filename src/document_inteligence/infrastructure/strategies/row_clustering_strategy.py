"""Row-clustering reading-order strategy.

This is the original reading-order algorithm extracted into a
:class:`ReadingOrderStrategy` implementation.
"""
from __future__ import annotations

from document_inteligence.domain.entities import DocumentElement, DocumentPage
from document_inteligence.domain.repositories import ReadingOrderStrategy


class RowClusteringStrategy(ReadingOrderStrategy):
    """Top-to-bottom, left-to-right with Y-tolerance row clustering."""

    def __init__(self, row_tolerance: float = 0.02) -> None:
        self._row_tolerance = row_tolerance

    def order(
        self, elements: list[DocumentElement], page: DocumentPage
    ) -> list[DocumentElement]:
        if not elements:
            return []

        sorted_by_y = sorted(elements, key=lambda e: (e.bbox.y, e.bbox.x, e.z_order))
        rows: list[list[DocumentElement]] = []

        for element in sorted_by_y:
            placed = False
            for row in rows:
                row_y = row[0].bbox.y
                if abs(element.bbox.y - row_y) <= self._row_tolerance:
                    row.append(element)
                    placed = True
                    break
            if not placed:
                rows.append([element])

        ordered: list[DocumentElement] = []
        for row in rows:
            row_sorted = sorted(row, key=lambda e: (e.bbox.x, e.z_order))
            ordered.extend(row_sorted)
        return ordered

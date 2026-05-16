from __future__ import annotations

from openxml_parser.domain.entities import DocumentElement, DocumentPage
from openxml_parser.domain.repositories import ReadingOrderStrategy
from openxml_parser.infrastructure.strategies.row_clustering_strategy import (
    RowClusteringStrategy,
)


def order_page_elements(
    page: DocumentPage,
    *,
    row_tolerance: float = 0.02,
    strategy: ReadingOrderStrategy | None = None,
) -> list[DocumentElement]:
    """Order elements using the given strategy (defaults to row clustering)."""
    if strategy is None:
        strategy = RowClusteringStrategy(row_tolerance=row_tolerance)
    return strategy.order(page.elements, page)


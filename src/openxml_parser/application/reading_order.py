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
    if _use_document_order(page):
        return sorted(page.elements, key=lambda e: (e.z_order, e.element_id))
    if strategy is None:
        strategy = RowClusteringStrategy(row_tolerance=row_tolerance)
    return strategy.order(page.elements, page)


def _use_document_order(page: DocumentPage) -> bool:
    """DOCX flow pages stack many paragraphs at y=1.0; keep XML ingest order."""
    if page.metadata.get("layout_mode") == "page_metrics":
        return True
    if page.metadata.get("source_format") == "docx":
        return True
    flow_count = sum(1 for e in page.elements if e.metadata.get("layout") == "flow")
    if flow_count >= max(3, len(page.elements) // 2):
        stacked = sum(1 for e in page.elements if e.metadata.get("layout") == "flow" and e.bbox.y >= 0.99)
        if stacked >= 3:
            return True
    return False


from __future__ import annotations

from dataclasses import asdict

from openxml_parser.application.config import ParserConfig
from openxml_parser.application.debug_report import build_debug_report
from openxml_parser.domain.entities import ParsedDocument
from openxml_parser.domain.repositories import (
    CaptionVerifier,
    DocumentIngestor,
    ReadingOrderStrategy,
)
from openxml_parser.application.reading_order import order_page_elements
from openxml_parser.application.markdown_renderer import render_markdown
from openxml_parser.application.rag_pack import RagChunk, build_rag_chunks
from openxml_parser.application.relationships import detect_relations
from openxml_parser.application.containment_graph import resolve_containment
from openxml_parser.application.table_absorber import absorb_overlapping_elements
from openxml_parser.application.image_annotation_absorber import absorb_image_annotations
from openxml_parser.domain.entities import DocumentElement, ElementType


def _build_reading_order_strategy(config: ParserConfig) -> ReadingOrderStrategy:
    name = config.reading_order_strategy
    if name == "row_clustering":
        from openxml_parser.infrastructure.strategies.row_clustering_strategy import (
            RowClusteringStrategy,
        )
        return RowClusteringStrategy(row_tolerance=config.row_tolerance)
    if name == "xy_cut":
        from openxml_parser.infrastructure.strategies.xy_cut_strategy import (
            XYCutStrategy,
        )
        return XYCutStrategy(gap_ratio=config.xy_cut_gap_ratio)
    from openxml_parser.infrastructure.strategies.composite_strategy import (
        CompositeStrategy,
    )
    from openxml_parser.infrastructure.strategies.xy_cut_strategy import (
        XYCutStrategy,
    )
    return CompositeStrategy(fallback=XYCutStrategy(gap_ratio=config.xy_cut_gap_ratio))


class ParseDocumentUseCase:
    """Application service: orchestrates ingestion via domain ports."""

    def __init__(
        self,
        ingestors: list[DocumentIngestor],
        config: ParserConfig | None = None,
        caption_verifier: CaptionVerifier | None = None,
        reading_order_strategy: ReadingOrderStrategy | None = None,
    ):
        self._ingestors = ingestors
        self._config = config or ParserConfig()
        self._caption_verifier = caption_verifier
        self._reading_order_strategy = (
            reading_order_strategy or _build_reading_order_strategy(self._config)
        )

    def execute(self, input_path: str) -> ParsedDocument:
        ingestor = self._find_ingestor(input_path)
        parsed = ingestor.ingest(input_path)
        for page in parsed.pages:
            resolve_containment(page, self._config)
            absorb_overlapping_elements(page, self._config)
            if self._config.absorb_image_annotations:
                absorb_image_annotations(page, self._config)
            page.elements = [
                e for e in page.elements
                if not _is_absorbed(e)
            ]
            if self._config.filter_noise_elements:
                page.elements = [
                    e for e in page.elements
                    if not _is_noise(e, self._config)
                ]
            page.elements = order_page_elements(
                page,
                row_tolerance=self._config.row_tolerance,
                strategy=self._reading_order_strategy,
            )
        parsed.relations = detect_relations(parsed.pages, self._config, caption_verifier=self._caption_verifier)
        return parsed

    @staticmethod
    def to_dict(parsed_document: ParsedDocument) -> dict:
        return asdict(parsed_document)

    def to_markdown(self, parsed_document: ParsedDocument) -> str:
        return render_markdown(parsed_document, config=self._config)

    def to_rag_chunks(self, parsed_document: ParsedDocument) -> list[dict]:
        chunks: list[RagChunk] = build_rag_chunks(parsed_document, self._config)
        return [asdict(c) for c in chunks]

    @staticmethod
    def to_debug_report(parsed_document: ParsedDocument) -> dict:
        return build_debug_report(parsed_document)

    def _find_ingestor(self, input_path: str) -> DocumentIngestor:
        for ingestor in self._ingestors:
            if ingestor.supports(input_path):
                return ingestor
        raise ValueError(f"No ingestor found for: {input_path}")


def _is_absorbed(e: DocumentElement) -> bool:
    return bool(
        e.metadata.get("absorbed_by")
        or e.metadata.get("absorbed_by_table")
        or e.metadata.get("absorbed_by_image")
    )


def _is_noise(e: DocumentElement, config: ParserConfig) -> bool:
    text = (e.text or "").strip()
    if e.element_type == ElementType.UNKNOWN and not text:
        return True
    if e.element_type == ElementType.TEXT and not text:
        return True
    area = e.bbox.width * e.bbox.height
    if area < config.min_element_area and not text:
        return True
    return False


from __future__ import annotations

from abc import ABC, abstractmethod

from .entities import DocumentBlock, DocumentElement, DocumentPage, ElementRelation, ParsedDocument


class DocumentIngestor(ABC):
    """Domain port for document ingestion."""

    @abstractmethod
    def supports(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def ingest(self, path: str) -> ParsedDocument:
        raise NotImplementedError


class CaptionVerifier(ABC):
    """Optional verifier port (e.g., VLM) for ambiguous caption candidates."""

    @abstractmethod
    def verify(
        self,
        *,
        page_number: int,
        image_element_id: str,
        caption_element_id: str,
        caption_text: str,
    ) -> tuple[bool, float]:
        """
        Returns:
            (is_caption, confidence)
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Reading Order
# ---------------------------------------------------------------------------

class ReadingOrderStrategy(ABC):
    """Domain port for element reading-order algorithms.

    Implementations can be rule-based (row clustering, XY-Cut) or
    model-based (future VLM / layout model).
    """

    @abstractmethod
    def order(
        self, elements: list[DocumentElement], page: DocumentPage
    ) -> list[DocumentElement]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Relation Inference
# ---------------------------------------------------------------------------

class RelationScorer(ABC):
    """Domain port for scoring candidate relations between elements."""

    @abstractmethod
    def score(
        self,
        source: DocumentElement,
        target: DocumentElement,
        page: DocumentPage,
    ) -> list[dict]:
        """Return a list of ``{type, score, metadata}`` dicts."""
        raise NotImplementedError


class StructureBuilder(ABC):
    """Build logical document blocks (L3) from ordered page elements."""

    @abstractmethod
    def build(
        self,
        page: DocumentPage,
        *,
        relations: list[ElementRelation],
    ) -> list[DocumentBlock]:
        raise NotImplementedError


class RelationReranker(ABC):
    """Domain port for reranking / filtering scored relation candidates.

    A no-op implementation passes candidates through unchanged; a
    VLM-based implementation can reject or boost low-confidence links.
    """

    @abstractmethod
    def rerank(
        self,
        candidates: list[dict],
        page: DocumentPage,
    ) -> list[dict]:
        raise NotImplementedError


"""No-op relation reranker.

Passes all candidates through unchanged.  Serves as the default
implementation and as a baseline for VLM-based rerankers.
"""
from __future__ import annotations

from document_inteligence.domain.entities import DocumentPage
from document_inteligence.domain.repositories import RelationReranker


class NoopRelationReranker(RelationReranker):

    def rerank(
        self,
        candidates: list[dict],
        page: DocumentPage,
    ) -> list[dict]:
        return candidates

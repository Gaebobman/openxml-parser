"""No-op relation reranker.

Passes all candidates through unchanged.  Serves as the default
implementation and as a baseline for VLM-based rerankers.
"""
from __future__ import annotations

from openxml_parser.domain.entities import DocumentPage
from openxml_parser.domain.repositories import RelationReranker


class NoopRelationReranker(RelationReranker):

    def rerank(
        self,
        candidates: list[dict],
        page: DocumentPage,
    ) -> list[dict]:
        return candidates

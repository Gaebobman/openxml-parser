from __future__ import annotations

from dataclasses import dataclass

from document_inteligence.application.use_cases import ParseDocumentUseCase
from document_inteligence.domain.entities import ParsedDocument
from document_inteligence.domain.repositories import DocumentIngestor


@dataclass
class _FakeIngestor(DocumentIngestor):
    supported_ext: str

    def supports(self, path: str) -> bool:
        return path.endswith(self.supported_ext)

    def ingest(self, path: str) -> ParsedDocument:
        return ParsedDocument(source_path=path, pages=[])


def test_use_case_selects_matching_ingestor() -> None:
    use_case = ParseDocumentUseCase(
        ingestors=[
            _FakeIngestor(".pdf"),
            _FakeIngestor(".pptx"),
        ]
    )

    result = use_case.execute("sample.pptx")
    assert result.source_path == "sample.pptx"


def test_use_case_raises_when_no_ingestor_matches() -> None:
    use_case = ParseDocumentUseCase(ingestors=[_FakeIngestor(".pdf")])

    try:
        use_case.execute("sample.pptx")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "No ingestor found" in str(exc)


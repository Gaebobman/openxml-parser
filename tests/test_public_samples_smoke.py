from __future__ import annotations

from pathlib import Path

import pytest

from document_inteligence.application.use_cases import ParseDocumentUseCase
from document_inteligence.infrastructure.ingestors.registry import build_ingestors

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public_samples"


@pytest.mark.parametrize(
    "filename",
    [
        "openxml_parser_public_sample.pptx",
        "openxml_parser_public_sample.docx",
        "openxml_parser_public_sample.xlsx",
        "openxml_parser_public_sample.hwpx",
    ],
)
def test_public_sample_parses(filename: str) -> None:
    path = PUBLIC / filename
    if not path.exists():
        pytest.skip(f"Missing public sample: {path}")

    use_case = ParseDocumentUseCase(ingestors=build_ingestors())
    parsed = use_case.execute(str(path))
    assert parsed.pages, f"No pages parsed for {filename}"
    assert any(page.elements for page in parsed.pages)

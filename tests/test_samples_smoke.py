from __future__ import annotations

from pathlib import Path

import pytest

from openxml_parser.application.use_cases import ParseDocumentUseCase
from openxml_parser.infrastructure.ingestors.registry import build_ingestors

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"


@pytest.mark.parametrize(
    "filename",
    [
        "openxml_parser_public_sample.pptx",
        "openxml_parser_public_sample.docx",
        "openxml_parser_public_sample.xlsx",
        "openxml_parser_public_sample.hwpx",
        "openxml_parser_public_sample_resume.docx",
    ],
)
def test_sample_parses(filename: str) -> None:
    path = SAMPLES / filename
    if not path.exists():
        pytest.skip(f"Missing sample: {path}")

    use_case = ParseDocumentUseCase(ingestors=build_ingestors())
    parsed = use_case.execute(str(path))
    assert parsed.pages, f"No pages parsed for {filename}"
    assert any(page.elements for page in parsed.pages)


def test_resume_sample_has_headings_and_substantial_text() -> None:
    path = SAMPLES / "openxml_parser_public_sample_resume.docx"
    if not path.exists():
        pytest.skip(f"Missing sample: {path}")

    use_case = ParseDocumentUseCase(ingestors=build_ingestors())
    parsed = use_case.execute(str(path))
    elements = [el for page in parsed.pages for el in page.elements]
    styled_count = sum(
        1
        for el in elements
        if el.metadata.get("formatted_text") or el.metadata.get("is_heading")
    )
    text_chars = sum(len((el.text or "")) for el in elements)
    assert styled_count >= 3
    assert text_chars >= 2000

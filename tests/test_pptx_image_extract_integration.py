from __future__ import annotations

import os
from pathlib import Path

import pytest

from document_inteligence.application.use_cases import ParseDocumentUseCase
from document_inteligence.domain.entities import ElementType
from document_inteligence.infrastructure.ingestors.pptx_ingestor import PptxIngestor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE = PROJECT_ROOT / "testdata/pptx_samples/sample.pptx"


@pytest.mark.skipif(os.getenv("RUN_REAL_PPTX_TESTS") != "1", reason="Set RUN_REAL_PPTX_TESTS=1 to run")
def test_image_metadata_and_asset_extraction(tmp_path: Path) -> None:
    # Enable manually with: uv run pytest -q -k image_metadata_and_asset_extraction
    # Override path: REAL_PPTX_SAMPLE=/path/to/file.pptx
    source = Path(os.getenv("REAL_PPTX_SAMPLE", str(DEFAULT_SAMPLE)))
    if not source.exists():
        pytest.skip("Source PPTX not found")

    assets_dir = tmp_path / "assets"
    use_case = ParseDocumentUseCase(ingestors=[PptxIngestor(asset_output_dir=str(assets_dir))])
    parsed = use_case.execute(str(source))

    image_elements = [
        e
        for page in parsed.pages
        for e in page.elements
        if e.element_type == ElementType.IMAGE and "image" in e.metadata
    ]
    if not image_elements:
        pytest.skip("No image elements with metadata in selected PPTX")

    rel = image_elements[0].metadata["image"]["relative_path"]
    assert isinstance(rel, str)
    assert Path(rel).exists()


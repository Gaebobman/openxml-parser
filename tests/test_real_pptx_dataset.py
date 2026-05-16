from __future__ import annotations

import os
from pathlib import Path

import pytest

from openxml_parser.application.use_cases import ParseDocumentUseCase
from openxml_parser.infrastructure.ingestors.pptx_ingestor import PptxIngestor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_ROOT = Path(os.getenv("REAL_PPTX_DATASET_ROOT", str(PROJECT_ROOT / "private_testdata/pptx_samples")))


def _is_valid_pptx(path: Path) -> bool:
    name = path.name
    if name.startswith("~$"):
        return False
    if name.startswith("._"):
        return False
    return path.suffix.lower() == ".pptx"


@pytest.mark.skipif(os.getenv("RUN_REAL_PPTX_TESTS") != "1", reason="Set RUN_REAL_PPTX_TESTS=1 to run")
def test_parse_real_pptx_files_from_dataset() -> None:
    assert DATASET_ROOT.exists(), f"Dataset root not found: {DATASET_ROOT}"

    files = sorted([p for p in DATASET_ROOT.rglob("*.pptx") if _is_valid_pptx(p)])
    assert files, "No valid .pptx files found in dataset root"

    max_files = int(os.getenv("MAX_REAL_PPTX_TESTS", "3"))
    targets = files[:max_files]

    use_case = ParseDocumentUseCase(ingestors=[PptxIngestor()])
    for path in targets:
        parsed = use_case.execute(str(path))
        assert parsed.pages, f"No pages parsed for {path}"
        assert parsed.pages[0].elements is not None


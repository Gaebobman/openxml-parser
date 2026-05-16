from __future__ import annotations

from document_inteligence.domain.repositories import DocumentIngestor
from document_inteligence.infrastructure.ingestors.docx_ingestor import DocxIngestor
from document_inteligence.infrastructure.ingestors.hwpx_ingestor import HwpxIngestor
from document_inteligence.infrastructure.ingestors.pptx_ingestor import PptxIngestor
from document_inteligence.infrastructure.ingestors.xlsx_ingestor import XlsxIngestor


def build_ingestors(
    *,
    asset_output_dir: str | None = None,
    include_master_shapes: bool = True,
    deduplicate_master_shapes: bool = True,
) -> list[DocumentIngestor]:
    """Register all format ingestors (first match wins in use case)."""
    return [
        PptxIngestor(
            asset_output_dir=asset_output_dir,
            include_master_shapes=include_master_shapes,
            deduplicate_master_shapes=deduplicate_master_shapes,
        ),
        DocxIngestor(asset_output_dir=asset_output_dir),
        XlsxIngestor(asset_output_dir=asset_output_dir),
        HwpxIngestor(asset_output_dir=asset_output_dir),
    ]

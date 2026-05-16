from __future__ import annotations

from openxml_parser.domain.repositories import DocumentIngestor
from openxml_parser.infrastructure.ingestors.docx_ingestor import DocxIngestor
from openxml_parser.infrastructure.ingestors.hwpx_ingestor import HwpxIngestor
from openxml_parser.infrastructure.ingestors.pptx_ingestor import PptxIngestor
from openxml_parser.infrastructure.ingestors.xlsx_ingestor import XlsxIngestor


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

from __future__ import annotations

import argparse
import json
from pathlib import Path

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.use_cases import ParseDocumentUseCase
from document_inteligence.infrastructure.ingestors.pptx_ingestor import PptxIngestor
from document_inteligence.infrastructure.verifiers.noop_caption_verifier import NoopCaptionVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MVP0.3 document parser")
    parser.add_argument("input_path", help="Input document path (.pptx)")
    parser.add_argument(
        "--output-json",
        dest="output_json",
        default=None,
        help="Output path for parsed JSON result",
    )
    parser.add_argument(
        "--output-md",
        dest="output_md",
        default=None,
        help="Output path for markdown result",
    )
    parser.add_argument(
        "--output-rag-json",
        dest="output_rag_json",
        default=None,
        help="Output path for RAG chunk JSON",
    )
    parser.add_argument(
        "--output-debug-json",
        dest="output_debug_json",
        default=None,
        help="Output path for debug report JSON",
    )
    parser.add_argument(
        "--assets-dir",
        dest="assets_dir",
        default=None,
        help="Optional directory path to extract image assets",
    )
    parser.add_argument(
        "--config-json",
        dest="config_json",
        default=None,
        help="Optional parser config JSON path",
    )
    parser.add_argument(
        "--reading-order",
        dest="reading_order",
        choices=["composite", "row_clustering", "xy_cut"],
        default=None,
        help="Reading order strategy override (default: from config)",
    )
    return parser


def _load_config(path: str | None) -> ParserConfig:
    if not path:
        return ParserConfig()
    cfg_path = Path(path)
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return ParserConfig(**data)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = _load_config(args.config_json)
    if args.reading_order:
        config.reading_order_strategy = args.reading_order
    use_case = ParseDocumentUseCase(
        ingestors=[PptxIngestor(
            asset_output_dir=args.assets_dir,
            include_master_shapes=config.include_master_shapes,
            deduplicate_master_shapes=config.deduplicate_master_shapes,
        )],
        config=config,
        caption_verifier=NoopCaptionVerifier(),
    )
    parsed_document = use_case.execute(args.input_path)
    payload = use_case.to_dict(parsed_document)
    markdown = use_case.to_markdown(parsed_document)
    rag_chunks = use_case.to_rag_chunks(parsed_document)
    debug_report = use_case.to_debug_report(parsed_document)

    output_json = args.output_json
    if output_json:
        out = Path(output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {out}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.output_md:
        md = Path(args.output_md)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(markdown, encoding="utf-8")
        print(f"Saved: {md}")
    elif not output_json:
        print("\n--- MARKDOWN ---\n")
        print(markdown)

    if args.output_rag_json:
        out = Path(args.output_rag_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rag_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {out}")

    if args.output_debug_json:
        out = Path(args.output_debug_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(debug_report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {out}")


if __name__ == "__main__":
    main()


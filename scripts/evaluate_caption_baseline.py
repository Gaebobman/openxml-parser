from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from openxml_parser.application.config import ParserConfig
from openxml_parser.application.use_cases import ParseDocumentUseCase
from openxml_parser.domain.entities import ElementType
from openxml_parser.infrastructure.ingestors.pptx_ingestor import PptxIngestor
from openxml_parser.infrastructure.verifiers.noop_caption_verifier import NoopCaptionVerifier


def _default_samples() -> list[str]:
    return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect caption baseline evaluation stats")
    parser.add_argument(
        "--samples-json",
        default=None,
        help="Optional JSON file containing {\"samples\": [\"path1\", ...]}",
    )
    parser.add_argument(
        "--output-json",
        default="out/eval/caption_baseline.json",
        help="Output path for aggregated baseline report",
    )
    return parser.parse_args()


def _load_samples(samples_json: str | None) -> list[str]:
    if not samples_json:
        return _default_samples()
    data = json.loads(Path(samples_json).read_text(encoding="utf-8"))
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise ValueError("samples-json must contain {'samples': [...]} structure")
    return [str(s) for s in samples]


def main() -> None:
    args = parse_args()
    samples = _load_samples(args.samples_json)
    if not samples:
        raise SystemExit(
            "No samples configured. Pass --samples-json with {\"samples\": [\"path/to/file.pptx\", ...]}."
        )
    cfg = ParserConfig()
    use_case = ParseDocumentUseCase(
        ingestors=[PptxIngestor()],
        config=cfg,
        caption_verifier=NoopCaptionVerifier(),
    )

    docs: list[dict[str, object]] = []
    total_pages = 0
    total_images = 0
    total_caption_relations = 0
    total_candidate_decisions = 0
    total_rejected = 0

    for sample in samples:
        path = Path(sample)
        if not path.exists():
            docs.append({"source_path": sample, "status": "missing"})
            continue
        parsed = use_case.execute(sample)
        debug = use_case.to_debug_report(parsed)
        caption_relations = [r for r in parsed.relations if r.relation_type == "caption_of"]
        num_images = sum(
            1
            for page in parsed.pages
            for e in page.elements
            if e.element_type == ElementType.IMAGE
        )
        decisions = []
        for page in debug["pages"]:
            page_decisions = page.get("caption_candidate_decisions", [])
            if isinstance(page_decisions, list):
                decisions.extend(page_decisions)
        rejected = [d for d in decisions if d.get("rejected_reason")]

        total_pages += int(debug["num_pages"])
        total_images += num_images
        total_caption_relations += len(caption_relations)
        total_candidate_decisions += len(decisions)
        total_rejected += len(rejected)

        docs.append(
            {
                "source_path": sample,
                "status": "ok",
                "num_pages": int(debug["num_pages"]),
                "num_images": num_images,
                "num_caption_relations": len(caption_relations),
                "num_candidate_decisions": len(decisions),
                "num_rejected_decisions": len(rejected),
                "caption_density_per_image": round(len(caption_relations) / max(num_images, 1), 4),
            }
        )

    report = {
        "config": asdict(cfg),
        "totals": {
            "num_documents": len([d for d in docs if d.get("status") == "ok"]),
            "num_pages": total_pages,
            "num_images": total_images,
            "num_caption_relations": total_caption_relations,
            "num_candidate_decisions": total_candidate_decisions,
            "num_rejected_decisions": total_rejected,
            "caption_density_per_image": round(total_caption_relations / max(total_images, 1), 4),
            "rejection_rate": round(total_rejected / max(total_candidate_decisions, 1), 4),
        },
        "documents": docs,
        "manual_sampling_guide": {
            "purpose": "Estimate caption precision/recall manually from sampled relations",
            "suggested_sample_size": 50,
            "labels": ["correct_caption_link", "wrong_link", "missing_link"],
        },
    }

    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()


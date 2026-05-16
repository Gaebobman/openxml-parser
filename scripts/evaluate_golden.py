"""Evaluate parser output against golden labels.

Metrics:
  - Reading Order: Kendall's Tau, normalised edit distance
  - Relations: Precision / Recall / F1 per relation type and overall

Usage:
  uv run python scripts/evaluate_golden.py --output-json out/eval/golden_report.json
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from openxml_parser.application.config import ParserConfig
from openxml_parser.application.evaluation import (
    kendall_tau,
    normalised_edit_distance,
    relation_prf,
)
from openxml_parser.application.use_cases import ParseDocumentUseCase
from openxml_parser.infrastructure.ingestors.pptx_ingestor import PptxIngestor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PROJECT_ROOT / "testdata" / "golden"


# ---------------------------------------------------------------------------
# Evaluation driver
# ---------------------------------------------------------------------------

def _load_golden_files() -> list[dict]:
    out = []
    for p in sorted(GOLDEN_DIR.glob("*.golden.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        data["_golden_path"] = str(p)
        out.append(data)
    return out


def _evaluate_one(golden: dict, use_case: ParseDocumentUseCase) -> dict:
    source = PROJECT_ROOT / golden["source"]
    if not source.exists():
        return {"source": golden["source"], "status": "missing"}

    parsed = use_case.execute(str(source))
    pages_by_num = {p.page_number: p for p in parsed.pages}
    rels_flat = [
        {"type": r.relation_type, "source": r.source_element_id, "target": r.target_element_id}
        for r in parsed.relations
    ]

    page_results = []
    all_tau = []
    all_ned = []
    all_pred_rels: list[dict] = []
    all_exp_rels: list[dict] = []

    for gp in golden.get("pages", []):
        pn = gp["page_number"]
        page = pages_by_num.get(pn)
        if page is None:
            page_results.append({"page_number": pn, "status": "page_not_found"})
            continue

        pred_order = [e.element_id for e in page.elements]
        exp_order = gp.get("expected_reading_order", [])
        tau = kendall_tau(pred_order, exp_order)
        ned = normalised_edit_distance(pred_order, exp_order)
        all_tau.append(tau)
        all_ned.append(ned)

        exp_rels = gp.get("expected_relations", [])
        page_pred_rels = [r for r in rels_flat if _rel_in_page(r, page)]
        all_pred_rels.extend(page_pred_rels)
        all_exp_rels.extend(exp_rels)

        prf = relation_prf(page_pred_rels, exp_rels)

        page_results.append({
            "page_number": pn,
            "reading_order": {
                "kendall_tau": round(tau, 4),
                "normalised_edit_distance": round(ned, 4),
                "predicted": pred_order,
                "expected": exp_order,
            },
            "relations": prf,
        })

    agg_prf = relation_prf(all_pred_rels, all_exp_rels)
    return {
        "source": golden["source"],
        "status": "ok",
        "avg_kendall_tau": round(sum(all_tau) / max(len(all_tau), 1), 4),
        "avg_normalised_edit_distance": round(sum(all_ned) / max(len(all_ned), 1), 4),
        "aggregate_relations": agg_prf,
        "pages": page_results,
    }


def _rel_in_page(rel: dict, page) -> bool:
    eids = {e.element_id for e in page.elements}
    return rel["source"] in eids or rel["target"] in eids


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate against golden labels")
    parser.add_argument(
        "--output-json",
        default="out/eval/golden_report.json",
        help="Output path for evaluation report",
    )
    parser.add_argument(
        "--golden-dir",
        default=None,
        help="Override golden labels directory",
    )
    return parser.parse_args()


def main() -> None:
    global GOLDEN_DIR
    args = parse_args()
    if args.golden_dir:
        GOLDEN_DIR = Path(args.golden_dir)

    goldens = _load_golden_files()
    if not goldens:
        print(f"No golden files found in {GOLDEN_DIR}")
        return

    cfg = ParserConfig()
    use_case = ParseDocumentUseCase(ingestors=[PptxIngestor()], config=cfg)

    results = []
    for g in goldens:
        print(f"Evaluating: {g['source']} ...")
        results.append(_evaluate_one(g, use_case))

    ok_results = [r for r in results if r.get("status") == "ok"]
    summary = {
        "num_golden_files": len(goldens),
        "num_evaluated": len(ok_results),
        "avg_kendall_tau": round(
            sum(r["avg_kendall_tau"] for r in ok_results) / max(len(ok_results), 1), 4
        ),
        "avg_normalised_edit_distance": round(
            sum(r["avg_normalised_edit_distance"] for r in ok_results) / max(len(ok_results), 1), 4
        ),
    }

    report = {"summary": summary, "config": asdict(cfg), "results": results}
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out}")
    print(f"  Kendall Tau (avg): {summary['avg_kendall_tau']}")
    print(f"  Norm Edit Dist (avg): {summary['avg_normalised_edit_distance']}")


if __name__ == "__main__":
    main()

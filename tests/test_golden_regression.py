"""Regression tests against golden labels.

Skipped automatically when golden label files or source PPTX are missing.
Thresholds should be tightened as the parser improves.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_inteligence.application.config import ParserConfig
from document_inteligence.application.use_cases import ParseDocumentUseCase
from document_inteligence.infrastructure.ingestors.pptx_ingestor import PptxIngestor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PROJECT_ROOT / "testdata" / "golden"

# Thresholds - raise these as the parser improves
MIN_KENDALL_TAU = 0.6
MIN_RELATION_F1 = 0.3
MIN_NORMALISED_EDIT_DISTANCE = 0.4

# Re-use metric functions from the evaluate script
from document_inteligence.application.evaluation import (
    kendall_tau,
    normalised_edit_distance,
    relation_prf,
)


def _golden_files() -> list[Path]:
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.golden.json"))


def _load_golden(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def use_case() -> ParseDocumentUseCase:
    return ParseDocumentUseCase(ingestors=[PptxIngestor()], config=ParserConfig())


golden_files = _golden_files()


@pytest.mark.skipif(not golden_files, reason="No golden label files found")
@pytest.mark.parametrize("golden_path", golden_files, ids=[p.stem for p in golden_files])
def test_reading_order_regression(golden_path: Path, use_case: ParseDocumentUseCase) -> None:
    golden = _load_golden(golden_path)
    source = PROJECT_ROOT / golden["source"]
    if not source.exists():
        pytest.skip(f"Source PPTX not found: {source}")

    parsed = use_case.execute(str(source))
    pages_by_num = {p.page_number: p for p in parsed.pages}

    taus: list[float] = []
    neds: list[float] = []
    for gp in golden.get("pages", []):
        pn = gp["page_number"]
        page = pages_by_num.get(pn)
        if page is None:
            continue
        pred_order = [e.element_id for e in page.elements]
        exp_order = gp.get("expected_reading_order", [])
        if not exp_order:
            continue
        taus.append(kendall_tau(pred_order, exp_order))
        neds.append(normalised_edit_distance(pred_order, exp_order))

    if taus:
        avg_tau = sum(taus) / len(taus)
        avg_ned = sum(neds) / len(neds)
        assert avg_tau >= MIN_KENDALL_TAU, (
            f"Kendall Tau {avg_tau:.4f} < {MIN_KENDALL_TAU} for {golden_path.name}"
        )
        assert avg_ned >= MIN_NORMALISED_EDIT_DISTANCE, (
            f"NED {avg_ned:.4f} < {MIN_NORMALISED_EDIT_DISTANCE} for {golden_path.name}"
        )


@pytest.mark.skipif(not golden_files, reason="No golden label files found")
@pytest.mark.parametrize("golden_path", golden_files, ids=[p.stem for p in golden_files])
def test_relation_regression(golden_path: Path, use_case: ParseDocumentUseCase) -> None:
    golden = _load_golden(golden_path)
    source = PROJECT_ROOT / golden["source"]
    if not source.exists():
        pytest.skip(f"Source PPTX not found: {source}")

    parsed = use_case.execute(str(source))
    pages_by_num = {p.page_number: p for p in parsed.pages}
    rels_flat = [
        {"type": r.relation_type, "source": r.source_element_id, "target": r.target_element_id}
        for r in parsed.relations
    ]

    all_pred: list[dict] = []
    all_exp: list[dict] = []
    for gp in golden.get("pages", []):
        pn = gp["page_number"]
        page = pages_by_num.get(pn)
        if page is None:
            continue
        eids = {e.element_id for e in page.elements}
        page_pred = [r for r in rels_flat if r["source"] in eids or r["target"] in eids]
        all_pred.extend(page_pred)
        all_exp.extend(gp.get("expected_relations", []))

    if not all_exp:
        return

    prf = relation_prf(all_pred, all_exp)
    overall = prf.get("_overall", {})
    f1 = overall.get("f1", 0.0)
    assert f1 >= MIN_RELATION_F1, (
        f"Relation F1 {f1:.4f} < {MIN_RELATION_F1} for {golden_path.name}"
    )

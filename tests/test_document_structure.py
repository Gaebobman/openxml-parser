from __future__ import annotations

from pathlib import Path

import pytest

from openxml_parser.application.use_cases import ParseDocumentUseCase
from openxml_parser.domain.entities import BlockKind
from openxml_parser.infrastructure.ingestors.registry import build_ingestors

ROOT = Path(__file__).resolve().parent.parent
RESUME = ROOT / "samples" / "openxml_parser_public_sample_resume.docx"


@pytest.mark.skipif(not RESUME.exists(), reason="resume sample missing")
def test_resume_blocks_are_paragraphs_without_inferred_headings() -> None:
    parsed = ParseDocumentUseCase(ingestors=build_ingestors()).execute(str(RESUME))
    assert parsed.blocks
    heading_blocks = [b for b in parsed.blocks if b.kind == BlockKind.HEADING]
    assert heading_blocks == []
    assert BlockKind.PARAGRAPH in {b.kind for b in parsed.blocks}


@pytest.mark.skipif(not RESUME.exists(), reason="resume sample missing")
def test_resume_markdown_uses_bold_not_hash_for_achievement() -> None:
    parsed = ParseDocumentUseCase(ingestors=build_ingestors()).execute(str(RESUME))
    md = ParseDocumentUseCase(ingestors=build_ingestors()).to_markdown(parsed)

    assert "**성과**" in md
    assert not any(
        line.lstrip().startswith("#") and line.rstrip().endswith("성과")
        for line in md.splitlines()
    )


@pytest.mark.skipif(not RESUME.exists(), reason="resume sample missing")
def test_resume_elements_keep_style_metadata() -> None:
    parsed = ParseDocumentUseCase(ingestors=build_ingestors()).execute(str(RESUME))
    elements = [el for page in parsed.pages for el in page.elements]
    proj = next(el for el in elements if (el.text or "").strip() == "프로젝트")
    assert proj.metadata.get("is_heading") is not True
    assert proj.metadata.get("outline_inferred") is None

    achievement = next(el for el in elements if (el.text or "").strip() == "성과")
    assert achievement.metadata.get("is_mostly_bold") is True
    assert achievement.metadata.get("formatted_text") == "**성과**"


@pytest.mark.skipif(not RESUME.exists(), reason="resume sample missing")
def test_resume_academic_papers_content_order() -> None:
    parsed = ParseDocumentUseCase(ingestors=build_ingestors()).execute(str(RESUME))
    md = ParseDocumentUseCase(ingestors=build_ingestors()).to_markdown(parsed)

    assert "Anomaly Detection Using Generative Language Models" in md
    assert "제1저자, IEEE Access, 2025" in md

    idx = md.find("Anomaly Detection")
    pub = md.find("제1저자, IEEE Access", idx)
    t2 = md.find("A Study on Detecting", pub)
    assert idx < pub < t2

    paper_headings = [
        b for b in parsed.blocks
        if b.kind == BlockKind.HEADING
        and "Anomaly Detection" in b.title_text
    ]
    assert paper_headings == []


@pytest.mark.skipif(not RESUME.exists(), reason="resume sample missing")
def test_resume_rag_chunks_include_style_metadata() -> None:
    parsed = ParseDocumentUseCase(ingestors=build_ingestors()).execute(str(RESUME))
    use_case = ParseDocumentUseCase(ingestors=build_ingestors())
    chunks = use_case.to_rag_chunks(parsed)
    assert chunks
    assert all("metadata" in c and c["metadata"].get("block_kind") for c in chunks)
    assert any(c["metadata"].get("is_mostly_bold") for c in chunks)
    assert all("section_path" not in c["metadata"] or not c["metadata"]["section_path"] for c in chunks)

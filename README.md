# openxml-parser

Open XML 문서(PPTX, DOCX, XLSX, HWPX)를 **구조화 JSON · Markdown · RAG chunk**로 변환하는 layout-first 문서 파서입니다.

레이아웃·읽기 순서·표 병합·관계 추론(`title_of`, `caption_of`)을 우선하고, VLM/시맨틱 모델은 확장 포트로만 연결합니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Multi-format ingestion** — `.pptx`, `.docx`, `.xlsx`, `.hwpx` (플러그형 `DocumentIngestor`)
- **PPTX layout pipeline** — XY-Cut / row clustering reading order, 병합셀 복원, nested table, crop 이미지 추출
- **Relation inference** — rule-based `caption_of` / `title_of` (+ optional `CaptionVerifier` hook)
- **LLM-friendly output** — JSON, Markdown(HTML table), RAG chunks, debug report
- **DDD structure** — domain ports + infrastructure adapters

## Supported formats

| Format | Status | Notes |
|--------|--------|--------|
| `.pptx` | Full | Slide coordinates, master shapes, OMML math (linear) |
| `.docx` | Beta | Page metrics, flow spacing, floating anchors/text boxes, tables |
| `.xlsx` | Beta | Sheet table + merged cells; embedded images/charts |
| `.hwpx` | Beta | Section XML; tables with colspan |
| `.hwp` (binary) | Not supported | Use HWPX export |

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (or pip).

```bash
git clone https://github.com/Gaebobman/openxml-parser.git
cd openxml-parser
uv sync
```

Parse the included samples (`samples/`):

```bash
# PPTX (full layout pipeline)
uv run openxml-parser samples/openxml_parser_public_sample.pptx \
  --output-md out/sample.md --output-json out/sample.json --assets-dir out/sample_assets

# DOCX / XLSX / HWPX
uv run openxml-parser samples/openxml_parser_public_sample.docx --output-md out/doc.md
uv run openxml-parser samples/openxml_parser_public_sample.xlsx --output-json out/sheet.json
uv run openxml-parser samples/openxml_parser_public_sample.hwpx --output-md out/hwp.md
```

## CLI

```text
openxml-parser INPUT [--output-json PATH] [--output-md PATH]
               [--output-rag-json PATH] [--output-debug-json PATH]
               [--assets-dir DIR] [--config-json PATH]
               [--reading-order composite|row_clustering|xy_cut]
```

Example with all outputs:

```bash
uv run openxml-parser samples/openxml_parser_public_sample.pptx \
  --output-json out/result.json \
  --output-md out/result.md \
  --output-rag-json out/rag.json \
  --output-debug-json out/debug.json \
  --assets-dir out/assets \
  --reading-order composite
```

Optional config JSON — see [ParserConfig](src/openxml_parser/application/config.py) fields.

## Architecture

```mermaid
flowchart LR
  Input[OpenXML file] --> Ingest[Format ingestor]
  Ingest --> Elements[L1 elements]
  Elements --> Layout[L2 layout pipeline]
  Layout --> Blocks[L3 blocks optional]
  Blocks --> Out[JSON / MD / RAG / Debug]
  Elements --> Out
```

- **L1 `pages[].elements`** — visible text, document order, native style metadata (no semantic guessing)
- **L2 layout** — reading order, bbox, containment, absorption, relations
- **L3 `blocks`** — optional grouping from **file-declared** outline only (Word `Heading`, PPTX placeholder)
- **Domain ports**: `DocumentIngestor`, `ReadingOrderStrategy`, `RelationScorer`, `CaptionVerifier`, `StructureBuilder`
- **Post-ingestion pipeline** (shared): containment → absorption → noise filter → reading order → relations → structure build → render

Details: [`docs/README.md`](docs/README.md), [`docs/architecture_diagrams.md`](docs/architecture_diagrams.md)

## Project layout

```text
src/openxml_parser/
  domain/           entities, repositories, value_objects
  application/      use_cases, config, reading_order, relationships, renderers
  infrastructure/
    ingestors/      pptx, docx, xlsx, hwpx, registry
    structure/      OutlineStructureBuilder (native outline only)
    strategies/     reading order implementations
    scorers/        rule_based_scorer
  interfaces/       cli.py
samples/            shareable demo files (committed)
private_example/    local-only fixtures (gitignored)
private_testdata/   local golden / samples (gitignored)
tests/
docs/
scripts/            evaluate_golden.py, evaluate_caption_baseline.py
```

## Development

```bash
uv sync --group dev
uv run pytest -q
```

Optional integration tests (local PPTX tree required):

```bash
RUN_REAL_PPTX_TESTS=1 uv run pytest -q tests/test_real_pptx_dataset.py
```

Golden-label regression (local `private_testdata/golden/*.golden.json` only):

```bash
uv run python scripts/evaluate_golden.py --output-json out/eval/golden_report.json
uv run pytest tests/test_golden_regression.py -v
```

## Local data policy

Do **not** commit proprietary documents. Use:

- `samples/` — safe demos for docs and CI smoke tests
- `private_example/`, `private_testdata/` — gitignored; for internal fixtures and golden labels

Never put internal file names or customer content in README, docs, or commit messages.

## Agent integration

For LLM / Agent consumption, prefer **structured JSON** over flat Markdown.

| Layer | Field | Use for |
|-------|--------|---------|
| L1 | `pages[].elements[]` | Primary: text, `z_order`, bbox, style metadata |
| L2 | `relations[]` | `title_of`, `caption_of` links |
| L3 | `blocks[]` | Optional tree when the file declares headings (Word `Heading`, PPTX placeholder) |

**Element metadata (DOCX example):** `paragraph_style`, `is_heading`, `heading_level`, `is_mostly_bold`, `formatted_text`, `is_list_item`, `list_level`, passive `line_pattern` (e.g. `bracket_leading`) — recorded for the model, not turned into a forced outline.

**Markdown export:** `#` lines map to **native Heading styles only**. Other emphasis uses `formatted_text` (e.g. `**bold**`). Resume-style docs without Word Heading styles render mostly flat; hierarchy is for the Agent to infer from JSON, not from `#` depth in `.md`.

Example:

```bash
uv run openxml-parser samples/openxml_parser_public_sample_resume.docx \
  --output-json out/resume.json \
  --output-rag-json out/resume.rag.json \
  --output-md out/resume.md
```

**RAG chunks:** one chunk per element (or per native-heading block when outline exists). Metadata includes `paragraph_style`, `is_mostly_bold`, `block_kind`, `element_ids`. `section_path` is omitted unless the source file defines native outline headings.

## Roadmap

- DOCX `outlineLvl` / styles.xml beyond built-in `Heading` styles
- VLM/CLIP `CaptionVerifier` and relation reranker adapters
- DOCX numbering.xml integration and floating text boxes
- XLSX cell-level elements (optional) and formula preservation
- HWPX binary `.hwp` conversion path
- OMML → LaTeX, equation OCR fallback

See [`docs/README.md`](docs/README.md) for implementation notes and pseudocode.

## License

[MIT](LICENSE) — Copyright (c) 2026 Gaebobman

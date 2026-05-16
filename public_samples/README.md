# Public samples

Safe-to-share fixtures for demos, CI smoke tests, and documentation.

| File | Format | Description |
|------|--------|-------------|
| `openxml_parser_public_sample.pptx` | PPTX | Multi-slide layout demo (tables, images, relations) |
| `openxml_parser_public_sample.docx` | DOCX | Heading, list, table |
| `openxml_parser_public_sample_layout.docx` | DOCX | Page margins, spacing, floating text box |
| `openxml_parser_public_sample.xlsx` | XLSX | Merged cells, metrics table |
| `openxml_parser_public_sample.hwpx` | HWPX | Paragraph + table with colspan |

Regenerate minimal DOCX/XLSX/HWPX fixtures:

```bash
uv run python scripts/build_public_samples.py
```

## Quick start

```bash
uv run openxml-parser public_samples/openxml_parser_public_sample.pptx \
  --output-md out/public_sample.md \
  --output-json out/public_sample.json \
  --assets-dir out/public_sample_assets
```

Other formats:

```bash
uv run openxml-parser public_samples/openxml_parser_public_sample.docx --output-md out/doc.md
uv run openxml-parser public_samples/openxml_parser_public_sample.xlsx --output-json out/sheet.json
uv run openxml-parser public_samples/openxml_parser_public_sample.hwpx --output-md out/hwp.md
```

Proprietary documents belong in `example/` (gitignored), not here.

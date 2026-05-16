# Public samples

Safe-to-share PPTX fixtures for demos, CI smoke tests, and documentation.

| File | Description |
|------|-------------|
| `openxml_parser_public_sample.pptx` | Multi-slide demo covering common parser cases (layout, tables, images, relations). |

## Quick start

```bash
uv run doc-parser public_samples/openxml_parser_public_sample.pptx \
  --output-md out/public_sample.md \
  --output-json out/public_sample.json \
  --assets-dir out/public_sample_assets
```

Proprietary or customer documents belong in `example/` (gitignored), not here.

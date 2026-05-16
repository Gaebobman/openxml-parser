# openxml-parser — 수도코드 문서

핵심 알고리즘을 구현 코드와 대응해 이해하기 쉽게 정리한 문서 모음입니다.

---

## 전체 파이프라인

```text
PPTX 입력
    │
    ▼
[Ingest] shape/좌표/텍스트/이미지/테이블 추출 (+ master/layout shapes)
    │
    ▼
[Containment Graph] 엘레멘트 공간 포함 관계 감지 → 병합/그룹화
    │
    ▼
[Table Absorption] Containment Ratio 기반 셀 흡수
    │
    ▼
[Reading Order] 페이지 내 원소 정렬
    │
    ▼
[Relation Inference] title_of, caption_of 추론
    │
    ▼
[Rendering]
  ├─ Markdown
  ├─ RAG Chunks
  └─ Debug Report
```

---

## 디렉터리 구조

```text
docs/pseudocode/
├── README.md
├── 00_notation.md
├── 01_ingestion/
│   ├── 01_overview.md
│   └── 02_table_xml_parsing.md
├── 02_reading_order/
│   └── 01_row_clustering.md
├── 03_relation_inference/
│   ├── 01_overview.md
│   └── 02_caption_scoring_and_resolution.md
└── 04_rendering/
    ├── 01_markdown_rendering.md
    └── 02_rag_chunk_building.md
```

---

## 코드 매핑

- Ingestion: `src/openxml_parser/infrastructure/ingestors/pptx_ingestor.py`
- Table XML: `src/openxml_parser/infrastructure/ingestors/pptx_table_xml.py`
- Containment Graph: `src/openxml_parser/application/containment_graph.py`
- Table Absorber: `src/openxml_parser/application/table_absorber.py`
- Reading Order: `src/openxml_parser/application/reading_order.py`
- Relation Inference: `src/openxml_parser/application/relationships.py`
- Markdown: `src/openxml_parser/application/markdown_renderer.py`
- RAG: `src/openxml_parser/application/rag_pack.py`


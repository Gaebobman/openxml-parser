# RAG Chunk Building

> 코드: `src/openxml_parser/application/rag_pack.py`

## 목적

검색·Agent 친화적인 chunk로 분리하고, **L1 스타일 메타**를 메타데이터에 부착한다.

## 규칙

### `ParsedDocument.blocks`가 있을 때

- `CONTAINER` block은 청크에서 제외
- `HEADING` block: 제목 + 하위 `element_ids` 텍스트를 하나의 청크 후보로 묶음 (native outline 문서)
- 그 외 block: `element_ids`당 텍스트 수집
- `chunk_max_chars`로 분할
- 메타: `block_id`, `block_kind`, `element_ids`, `paragraph_style`, `is_mostly_bold`, …
- `section_path` / `outline_level`: **native heading이 있을 때만** 포함

### blocks가 없을 때 (legacy)

- **element 단위**로 청크 생성 (페이지 aggregate 아님)
- 이미지 등 텍스트 없는 element도 `[CAPTION]`만 있으면 청크 생성

### 공통

- `preserve_text_formatting`이면 `formatted_text` 우선
- `chunk_include_captions=true` → 대상 element에 `[CAPTION] ...` 추가

## Agent 권장

- 계층/섹션 의미는 `metadata.section_path`가 비어 있으면 `elements[].metadata` + 본문으로 추론
- Markdown `#` depth를 ground truth로 사용하지 않음

## 수도코드

```pseudocode
caption_map = build_caption_map(relations)

IF parsed.blocks not empty:
    FOR block IN parsed.blocks:
        IF block.kind == CONTAINER: continue
        parts = []
        IF block.kind == HEADING:
            parts.append(block.title_text)
        FOR element_id IN block.element_ids:
            parts.append(display_text(element_id))  // formatted_text preferred
            IF chunk_include_captions:
                parts.append(caption_for(element_id))
        emit chunks with block metadata + style metadata from first element
ELSE:
    FOR page IN pages:
        FOR element IN page.elements:
            parts = [display_text(element)]
            IF caption on element: parts.append("[CAPTION] ...")
            IF parts empty: continue
            emit chunk per element with element_id + style metadata
```

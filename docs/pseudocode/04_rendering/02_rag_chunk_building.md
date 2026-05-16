# RAG Chunk Building

> 코드: `src/openxml_parser/application/rag_pack.py`

## 목적

페이지 내용을 검색 친화적인 chunk로 분리하고 메타데이터를 부착한다.

## 규칙

- 기본 단위: 페이지
- 텍스트 블록을 수집해 `chunk_max_chars` 기준으로 분할
- 옵션 `chunk_include_captions=true`이면 `[CAPTION] ...` 라인을 함께 포함
- 메타: `source_path`, `page_number`

## 실무 팁

- QA 정확도를 높이고 싶으면 `chunk_include_captions=true`를 권장합니다.
- 캡션 잡음이 많은 문서군에서는 false로 내려 노이즈를 줄일 수 있습니다.

## 수도코드

```pseudocode
caption_map = build_caption_map(relations)

FOR page IN pages:
    blocks = []
    FOR element IN page.elements:
        IF element.text:
            blocks.append(element.text)
        IF chunk_include_captions AND caption_map[element.id]:
            blocks.append("[CAPTION] " + caption_map[element.id])

    page_text = join_with_blank_lines(blocks)
    parts = split_by_max_chars(page_text, chunk_max_chars)
    FOR part IN parts:
        emit RagChunk(chunk_id, page_number, text=part, metadata)
```


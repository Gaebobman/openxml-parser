# Markdown Rendering

> 코드: `src/document_inteligence/application/markdown_renderer.py`

## 목적

정렬된 원소 + 관계 정보를 LLM 친화 Markdown으로 직렬화한다.

## 규칙 요약

- 페이지 시작: `<!-- Page N -->`
- 첫 제목 후보 텍스트: `# ...`
- 이미지: `<img src="..." alt="..." width="N"/>` HTML 태그 출력. `width`는 PPTX shape의 EMU 치수를 96 DPI 기준 픽셀로 변환한 값.
- 이미지 주석: annotation이 있으면 이미지 아래에 `*레이블1 | 레이블2*` 이탤릭으로 출력
- 테이블: 기본 HTML `<table>` 렌더링 (병합 셀 `colspan`/`rowspan` 지원, `<colgroup>`으로 원본 컬럼 너비 비율 보존)
- 테이블-in-테이블: 큰 테이블 셀 안에 포함된 작은 테이블은 nested `<table>` HTML로 렌더링
- 흡수된 이미지: HTML 블록 내에서 `<img>` 태그로 변환 (`![]()`은 HTML 블록에서 렌더링 불가)
- 흡수된 원소 순서: 셀 내 `absorbed_elements`를 `(y, x)` 좌표 기준으로 정렬하고, 셀 중앙선(`cell_bbox` 세로 중간) 위쪽은 셀 텍스트 앞에, 아래쪽은 뒤에 배치
- 흡수된 원소: 테이블 셀 `absorbed_elements`에 포함되어 렌더링되며, 페이지 일반 순회에서는 중복 출력하지 않음
- 줄바꿈: 본문 텍스트는 `\n` → `  \n` (Markdown trailing spaces), `<td>` 내부는 `\n` → `<br/>`
- 글머리 기호/번호: ingestion 단계에서 paragraph XML의 `<a:buAutoNum>`, `<a:buChar>` 속성을 읽어 텍스트에 prefix로 반영. 렌더러에서는 이미 포함된 prefix를 그대로 출력.
- 텍스트 서식: `preserve_text_formatting` 활성화 시 본문은 Markdown(`**`, `*`, `<u>`), 테이블 셀은 HTML(`<b>`, `<i>`, `<u>`). 지배적 서식(80%↑)은 억제, 인접 동일 서식 런은 병합.
- 캡션: `caption_of`가 있으면 `> caption_text`
- 중복 캡션은 한 번만 출력 (`seen_captions` 집합으로 제어)
- **칼럼 구분**: 연속 요소의 `spatial_group`이 수직 분할(`v`) 경계를 넘으면 `<!-- column-break -->` 삽입

## 주의사항

- 이미지 링크는 출력 파일 기준 상대경로를 사용해야 합니다.
- 절대경로/실행경로 의존 경로를 쓰면 Markdown 뷰어에서 이미지가 깨질 수 있습니다.
- `table_render_html=False` 설정 시에만 Markdown pipe table 폴백을 사용합니다.
- 헤더 행이 명확하지 않은 테이블은 `<thead>` 없이 `<tbody>`만 출력합니다.
- 헤더 첫 행에 `rowspan > 1` 셀이 있으면 해당 범위의 행을 모두 `<thead>`에 포함시켜 `<thead>`/`<tbody>` 경계에서 rowspan이 끊기는 문제를 방지합니다.

## 수도코드

```pseudocode
FOR page IN pages:
    write page comment
    seen_captions = set()
    prev_group = None
    FOR element IN page.elements:
        IF element.metadata.absorbed_by_table OR absorbed_by OR absorbed_by_image:
            continue
        block = render_element(element)
        IF block empty: continue
        cur_group = element.metadata.spatial_group
        IF prev_group != None AND cur_group != prev_group:
            IF group_transition_is_vertical_cut(prev_group, cur_group):
                write "<!-- column-break -->"
        prev_group = cur_group
        write block
        caption = caption_map[target=element.id]
        IF caption and caption not in seen_captions:
            write "> " + caption
            seen_captions.add(caption)
```

```pseudocode
FUNCTION render_table(table_element, config):
    cells = table_element.metadata.table_cells
    usable_cells = [cell for cell in cells if cell.is_spanned != True]
    IF config.table_render_html == False:
        RETURN render_pipe_table(usable_cells)

    col_widths = table_element.metadata.table_col_widths
    header_rows = infer_header_rows(usable_cells)
    // header_rows includes rows covered by header rowspan
    html = "<table>"
    IF col_widths valid:
        html += "<colgroup>" + col_width_pct_tags + "</colgroup>"
    IF header_rows not empty:
        html += "<thead>...</thead>"
    html += "<tbody>...</tbody>"
    html += "</table>"
    RETURN html
```


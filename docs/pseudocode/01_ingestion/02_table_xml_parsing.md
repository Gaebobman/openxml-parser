# 테이블 XML 파싱

> 코드: `src/openxml_parser/infrastructure/ingestors/pptx_table_xml.py`

## 목적

`python-pptx`만으로 복원하기 어려운 병합 정보를 XML에서 복원한다.

## 핵심 포인트

- `gridSpan`, `rowSpan`, `hMerge`, `vMerge` 처리
- 원본 셀(`is_merge_origin`)과 스팬 셀(`is_spanned`) 구분

## 수도코드

```pseudocode
FUNCTION parse_table(tbl_xml):
    col_widths = read_tblGrid
    row_heights = read_tr_heights
    grid_slots = init(row_count, col_count)

    # 1) horizontal placement
    FOR each row:
        FOR each tc:
            IF tc is hMerge-continue: skip
            col_span = resolve_grid_span_and_hmerge_followers(tc)
            place slot across columns

    # 2) vertical merge restore
    FOR each origin slot:
        IF row_span not explicit:
            extend while next rows are vMerge-continue

    # 3) emit cells
    FOR each grid position:
        emit ParsedTableCell(row, col, text, span flags)
```


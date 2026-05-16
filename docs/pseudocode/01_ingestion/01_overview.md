# Ingestion 개요

> 코드: `src/openxml_parser/infrastructure/ingestors/pptx_ingestor.py`

## 목적

PPTX를 순회해 페이지별 `DocumentElement`를 구성한다.

## 핵심 구현 포인트 (중요)

- **GROUP 재귀 처리**:
  - `GROUP` shape를 원소로만 남기지 않고, 내부 child shape를 재귀 순회해 개별 원소로 승격합니다.
  - 이 로직이 없으면 슬라이드 내 실제 이미지가 `GROUP` 내부에 있을 때 Markdown에서 누락될 수 있습니다.
- **절대 좌표 보정**:
  - 그룹 내부 child의 `left/top`은 부모 기준 상대 좌표이므로, 부모 오프셋을 누적해 슬라이드 절대 좌표로 변환합니다.
- **테이블 XML 병합 복원 + shape 매핑**:
  - 슬라이드 내 table shape 순서와 XML 테이블 파싱 결과를 대응시켜 `table_cells` 메타데이터를 구성합니다.
- **셀 단위 좌표(cell_bbox) 계산**:
  - `table_col_widths`, `table_row_heights` 비율과 테이블 shape 절대좌표를 이용해 각 셀의 normalized bbox를 계산합니다.
  - 이후 Containment Ratio 기반 테이블-원소 흡수 단계의 입력 신호로 사용됩니다.
- **이미지 경로 포터블 처리**:
  - Markdown에서 이미지가 깨지지 않도록 full path가 아닌 상대경로(`assets_dir_name/filename`)를 사용합니다.
- **PPTX crop 반영 이미지 추출**:
  - `PICTURE` shape의 `crop_left/right/top/bottom` 속성을 읽어 실제 보이는 영역을 잘라 저장합니다.
  - 이 로직이 없으면 슬라이드에서 크롭된 이미지가 Markdown에서 원본 전체로 보이는 문제가 발생합니다.
- **글머리 기호/번호(bullet) 보존**:
  - PPTX의 `<a:buAutoNum>`, `<a:buChar>` paragraph 속성에서 bullet prefix를 추출합니다.
  - `shape.text`는 bullet/numbering 정보를 포함하지 않으므로, paragraph XML을 직접 순회합니다.
  - 테이블 셀 텍스트(`pptx_table_xml`)와 일반 shape 텍스트(`pptx_ingestor`) 모두에 적용됩니다.
  - 지원 타입: `arabicPeriod(1. 2.)`, `circleNumDbPlain(① ②)`, `alpha/roman` 변형, 문자 bullet(`• v` 등).
- **슬라이드 마스터/레이아웃 shape 추출**:
  - `slide.slide_layout.shapes`와 `slide_layout.slide_master.shapes`를 추가 순회합니다.
  - placeholder idx 기반 중복 방지: 슬라이드에 이미 같은 placeholder가 있으면 skip.
  - 템플릿 텍스트(`Click to edit Master...`, `‹#›`)는 자동 필터링합니다.
  - content hash 기반으로 동일 마스터 shape의 반복 등장을 제거합니다.

## 수도코드

```pseudocode
FUNCTION ingest(pptx_path):
    prs = Presentation(pptx_path)
    xml_tables_by_slide = extract_tables_from_pptx(pptx_path)

    pages = []
    FOR each slide_index, slide IN prs.slides:
        elements = []
        slide_tables = xml_tables_by_slide.get(slide_index)
        slide_table_idx = 0

        FUNCTION process_shape(shape, abs_left=None, abs_top=None):
            shape_type = classify_shape(shape)
            text = extract_text_or_math(shape)
            bbox = normalize_bbox_with_abs(shape, abs_left, abs_top, slide_width, slide_height)
            metadata = collect_basic_metadata(shape)

            IF shape_type == TABLE:
                parsed_table = slide_tables[slide_table_idx] if exists
                cell_bboxes = build_cell_bboxes(parsed_table, shape_abs_bbox)
                metadata += table_cells_from_xml(parsed_table, cell_bboxes)
                slide_table_idx += 1

            IF shape_type == IMAGE:
                metadata += extract_image_metadata_or_file(shape)
                blob = apply_crop_if_needed(shape, blob)

            elements.append(DocumentElement(...))

            IF shape_type == GROUP:
                FOR each child IN shape.shapes:
                    child_abs_left = bbox_abs_left + child.left
                    child_abs_top  = bbox_abs_top + child.top
                    process_shape(child, child_abs_left, child_abs_top)

        FOR each root_shape IN slide.shapes:
            process_shape(root_shape)

        pages.append(DocumentPage(slide_index, elements))

    RETURN ParsedDocument(source_path, pages)
```


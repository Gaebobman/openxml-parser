# Documentation Index

이 디렉토리는 `openxml-parser`의 운영/설계 문서를 관리합니다.

## 문서 목록

- `architecture_diagrams.md`: 시스템/레이어/주요 로직 다이어그램
- `operations.md`: 실행/평가/운영 절차
- `evaluation.md`: 품질 평가 기준과 베이스라인 해석 가이드
- `pseudocode/`: 핵심 알고리즘 수도코드 설명

## 문서 원칙

- 구현된 기능과 계획 기능을 명확히 분리합니다.
- Mermaid 다이어그램은 구조/데이터 흐름 설명에 사용합니다.
- 코드 변경 시 README와 docs 문서의 불일치가 없도록 함께 업데이트합니다.

## 최신 반영 사항 (현재 구현)

### 다포맷 인제스트 (Ingestion)

| 포맷 | Ingestor | 레이아웃 |
|------|----------|----------|
| PPTX | `pptx_ingestor.py` | 슬라이드 좌표 (EMU → normalized bbox) |
| DOCX | `docx_ingestor.py` + `docx_layout.py` | `w:sectPr` 페이지 크기/여백, 단락 spacing 흐름, `wp:anchor` 플로팅 박스/이미지 |
| XLSX | `xlsx_ingestor.py` | 시트 = 페이지, 표 + 이미지/차트 앵커 |
| HWPX | `hwpx_ingestor.py` | section XML, 구조 흐름 |

- 등록: `infrastructure/ingestors/registry.py` → `build_ingestors()`
- 공개 샘플: `public_samples/openxml_parser_public_sample.{pptx,docx,xlsx,hwpx}`
- 이후 파이프라인(containment, reading order, relations, render)은 포맷 공통

### 추출/렌더링
- 테이블 렌더링은 기본적으로 HTML `<table>`을 사용하며 병합 셀 span(`colspan`, `rowspan`)을 보존합니다. `<colgroup>`으로 PPTX 원본의 컬럼 너비 비율도 보존합니다.
- **테이블 헤더 rowspan 안전성**: `<thead>` 첫 행에 `rowspan > 1`인 셀이 있으면 해당 범위의 행을 모두 `<thead>`에 포함시켜 `<thead>`/`<tbody>` 경계에서 rowspan이 끊기는 문제를 방지합니다.
- 테이블 셀 흡수 지표를 IoU에서 **Containment Ratio**(포함 비율)로 교체하여, 큰 셀 안의 작은 원소도 정확히 흡수합니다.
- **테이블-in-테이블**: 큰 테이블 셀 내부에 포함된 작은 테이블을 nested HTML `<table>`로 렌더링합니다.
- HTML 테이블 내 흡수된 이미지는 `<img>` 태그로 출력합니다.
- **Containment Graph**를 통해 엘레멘트 간 공간 포함 관계를 감지합니다.
- 슬라이드 마스터/레이아웃 shape을 추출하되, 템플릿 텍스트와 중복은 자동 필터링합니다.
- 셀 내 흡수된 요소들은 `(y, x)` 좌표 기준으로 정렬되며, 셀 중앙선 위쪽 요소는 셀 텍스트 앞에, 아래쪽 요소는 뒤에 배치됩니다.
- 텍스트 줄바꿈 보존: 본문은 Markdown trailing spaces(`  \n`), 테이블 셀은 `<br/>` 변환.
- 이미지 크기 보존: PPTX shape의 EMU 치수를 96 DPI 기준 픽셀로 변환하여 `<img width="..."/>` 출력.
- 글머리 기호/번호 보존: `<a:buAutoNum>`, `<a:buChar>` paragraph 속성에서 bullet prefix를 추출하여 텍스트에 반영.

### Reading Order (Phase 2 신규)
- **`ReadingOrderStrategy` domain port**: 확장 가능한 전략 패턴.
- **`RowClusteringStrategy`**: 기존 Y-tolerance 기반 행 클러스터링.
- **`XYCutStrategy`**: 재귀적 XY-Cut으로 다단 레이아웃 대응.
- **`CompositeStrategy`** (기본): placeholder 인덱스 우선 + XY-Cut fallback.
- CLI `--reading-order` 옵션으로 전략 선택 가능.

### Relation Inference (Phase 3 신규)
- **`RelationScorer` / `RelationReranker` domain ports**: VLM 확장 가능한 전략 패턴.
- **`RuleBasedScorer`**: proximity, alignment, size_ratio, position, text_hint 5신호 가중합.
- **`NoopRelationReranker`**: pass-through (향후 VLM reranker 대체 가능).
- 관계 타입 확장: `caption_of`, `related_to` 추가 (기존 `title_of` 유지).
- 충돌 해소 고도화: confidence 내림차순 greedy global assignment.

### 정량 평가 (Phase 1 신규)
- **Golden label 스키마**: 로컬 `testdata/golden/*.golden.json` (git 미포함).
- **`evaluate_golden.py`**: Kendall's Tau, NED, P/R/F1 자동 평가.
- **`test_golden_regression.py`**: 회귀 방지 자동 테스트.

### 출력 품질 개선 (Phase 4 신규)
- **노이즈 요소 필터링**: 빈 텍스트, UNKNOWN 타입, 극소 면적 요소를 파이프라인에서 자동 제거 (`filter_noise_elements`, `min_element_area`).
- **이미지 주석 흡수**: 이미지 영역 내부의 짧은 텍스트를 annotation으로 묶어 이미지 하단에 *이탤릭* 레이블로 렌더링 (`absorb_image_annotations`, `image_annotation_containment_threshold`, `image_annotation_max_text_len`).
- **`title_of` 공간 범위 제한**: 타이틀 아래 방향 + 최대 Y 거리(`title_max_y_distance`) 이내 요소에만 연결하여 과연결 방지.
- **텍스트 서식 보존**: `<a:rPr>` 런 속성에서 bold/italic/underline을 추출하여 Markdown(`**`, `*`, `<u>`) 및 HTML 테이블(`<b>`, `<i>`, `<u>`)에 반영 (`preserve_text_formatting`).
  - **지배적 서식 억제**: 전체 런의 80% 이상이 같은 서식이면 기본 스타일로 판단하여 태그 제거.
  - **인접 런 병합**: 동일 서식의 연속 런을 합쳐서 `****` 같은 깨진 마크다운 방지.

### 공간 그룹 / 칼럼 구조 감지 (Phase 5 신규)
- **`spatial_group` 메타데이터**: XY-Cut 재귀 분할 시 각 요소에 계층적 그룹 경로 부여 (예: `0.h0.v1` = 첫 수평 행의 두 번째 칼럼).
  - `h` = 수평 분할(행), `v` = 수직 분할(칼럼).
- **`<!-- column-break -->` 렌더링**: Markdown에서 수직 분할(칼럼 전환) 경계를 HTML 코멘트로 표시.
- **`xy_cut_gap_ratio` 기본값 0.006**: PPTX의 촘촘한 칼럼 간격(0.8%)도 감지할 수 있도록 임계치를 낮춤.

### 기타
- 공개 데모: `public_samples/`. 로컬 전용 자료: `example/`, `testdata/` (gitignore).


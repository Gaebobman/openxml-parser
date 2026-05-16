# Operations Guide

## 1. 환경 준비

```bash
uv sync
uv sync --group dev
```

## 2. 기본 파싱 실행

```bash
uv run openxml-parser ./sample.pptx \
  --output-json ./out/result.json \
  --output-md ./out/result.md \
  --output-rag-json ./out/rag.json \
  --output-debug-json ./out/debug.json \
  --assets-dir ./out/assets
```

## 3. 테스트 실행

```bash
uv run pytest -q
```

실데이터 테스트(옵션):

```bash
RUN_REAL_PPTX_TESTS=1 MAX_REAL_PPTX_TESTS=3 uv run pytest -q tests/test_real_pptx_dataset.py
RUN_REAL_PPTX_TESTS=1 uv run pytest -q tests/test_pptx_image_extract_integration.py
```

## 4. Golden Label 평가

```bash
uv run python scripts/evaluate_golden.py --output-json out/eval/golden_report.json
```

회귀 테스트:

```bash
uv run pytest tests/test_golden_regression.py -v
```

## 5. 관계 품질 베이스라인 수집

```bash
uv run python scripts/evaluate_caption_baseline.py \
  --output-json out/eval/caption_baseline.json
```

## 6. Reading Order 전략 변경

```bash
uv run openxml-parser ./sample.pptx --reading-order xy_cut --output-md ./out/result.md
uv run openxml-parser ./sample.pptx --reading-order row_clustering --output-md ./out/result.md
uv run openxml-parser ./sample.pptx --reading-order composite --output-md ./out/result.md
```

## 7. 운영 체크포인트

- Markdown 이미지 경로가 상대경로인지 확인
- GROUP 내부 이미지가 누락되지 않았는지 확인 (그룹 shape 포함 슬라이드)
- 크롭된 이미지가 원본 전체로 보이지 않는지 확인 (PPTX crop 반영 여부)
- 테이블이 HTML `<table>`로 출력되는지 확인 (`colspan`/`rowspan` 반영 여부)
- 테이블 위 텍스트박스/이미지가 셀 내용으로 흡수되어 중복 출력되지 않는지 확인 (Containment Ratio 기반)
- 셀 내 이미지가 `<img>` 태그로 렌더링되는지 확인 (Markdown `![]()` 아님)
- 큰 테이블 셀 안의 작은 테이블이 nested `<table>`로 렌더링되는지 확인
- 큰 텍스트박스 안 작은 텍스트박스가 하나로 병합되는지 확인 (Containment Graph)
- 마스터/레이아웃 텍스트가 반영되되, 템플릿 텍스트(`Click to edit Master...`)가 필터링되는지 확인
- 글머리 기호/번호(`1. 2.`, `① ②`, `• `, `v `)가 텍스트에 보존되는지 확인
- `debug.json`의 `caption_candidate_decisions`로 오탐 원인 확인
- `caption_density_per_image`, `rejection_rate` 추세 모니터링
- 회귀 발생 시 config 임계치(`caption_rule_threshold`, `caption_vlm_threshold`) 점검

## 8. 회귀 점검 시나리오 (권장)

1. `public_samples/openxml_parser_public_sample.pptx` 재파싱
2. 출력 Markdown에서 이미지 링크(상대경로) 존재 확인
3. `--assets-dir` 추출 이미지가 슬라이드 표시와 일치하는지 확인 (crop 포함)
4. `--output-debug-json`에서 `caption_candidate_decisions` 필드 존재 확인
5. 테이블 `<table>` 출력 및 `colspan`/`rowspan` 확인
6. 테이블 내부 시각 원소(텍스트박스/이미지) 셀 흡수 확인
7. 셀 내 이미지 `<img>` 렌더링 확인
8. nested `<table>` 포함 여부 확인
9. 셀 내 흡수 요소 공간 순서(위→아래, 왼쪽→오른쪽) 확인
10. 글머리 기호/번호 보존 확인
11. `out/eval/caption_baseline.json` 재생성 후 지표 변화 확인
12. 로컬 golden이 있으면 `evaluate_golden.py` / `test_golden_regression.py` 실행


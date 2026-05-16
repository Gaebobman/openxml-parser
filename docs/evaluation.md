# Evaluation Guide

## 목표

`caption_of` 관계 품질을 반복적으로 개선하기 위해 동일 데이터셋에서 지표를 비교합니다.

## 산출물

- `out/eval/caption_baseline.json`

## 핵심 지표

- `caption_density_per_image`
  - 이미지 1개당 연결된 캡션 수
  - 과도하게 높으면 오탐 가능성, 너무 낮으면 미탐 가능성
- `rejection_rate`
  - 후보 중 탈락 비율
  - 너무 높으면 보수적 과적용, 너무 낮으면 후보 생성/임계치 검토 필요
- `num_caption_relations`
  - 최종 관계 수
- `num_candidate_decisions`
  - 후보 검토 건수

## 필수 회귀 체크 항목

- **Group Image Recall**
  - 그룹 내부 이미지가 Markdown에 누락되지 않는지 확인
  - 예시: `samples/openxml_parser_public_sample.pptx` 또는 로컬 golden 데이터
- **Caption Decision Trace Coverage**
  - `debug.json`의 `caption_candidate_decisions`가 페이지별로 채워지는지 확인
- **Path Portability**
  - Markdown 이미지 링크가 상대경로로 출력되는지 확인
- **Crop Fidelity**
  - 크롭된 picture shape가 출력 자산에서도 동일하게 크롭되어 있는지 확인

## 수동 검증 권장 절차

1. `caption_of` 관계 50건 샘플링
2. `correct_caption_link / wrong_link / missing_link` 라벨링
3. 문서군별(보고서형/슬라이드형) 오차 패턴 분리
4. 임계치 조정 후 동일 절차 반복

## 해석 가이드

- `caption_density_per_image`는 문서 타입에 따라 달라집니다.
- 단일 지표보다 문서별 상세 지표를 함께 확인해야 합니다.
- `debug.json`의 `score_breakdown`, `rejected_reason`를 함께 보면 조정 포인트를 빠르게 찾을 수 있습니다.
- 지표 개선과 함께 실제 Markdown 렌더링(누락/깨짐/중복)도 반드시 병행 확인합니다.
- 특히 이미지 품질 평가는 링크 정상 여부뿐 아니라 crop fidelity(보이는 영역 일치)까지 포함해야 합니다.


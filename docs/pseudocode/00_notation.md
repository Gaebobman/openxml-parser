# 표기 규칙 (Notation)

## 주요 엔티티

- `DocumentElement`: 페이지 내 단일 원소(텍스트/이미지/표 등)
- `DocumentPage`: 페이지 단위 원소 목록
- `ElementRelation`: 원소 간 관계(`title_of`, `caption_of`)

## 핵심 변수

- `bbox`: `(x, y, width, height)` 정규화 좌표(0..1)
- `row_tolerance`: 같은 행으로 묶는 Y축 허용 오차
- `caption_max_gap`: 이미지-캡션 최대 수직 거리
- `alignment_tolerance`: X축 정렬 허용 오차
- `caption_rule_threshold`: 규칙 기반 캡션 확정 임계값
- `caption_vlm_threshold`: verifier 위임 최소 임계값

## 점수 관련

- `rule_score`: 규칙 기반 캡션 점수
- `score_breakdown`: 점수 구성요소 세부값
  - `proximity`
  - `alignment`
  - `length_score`
  - `keyword_score`
  - `bullet_penalty`


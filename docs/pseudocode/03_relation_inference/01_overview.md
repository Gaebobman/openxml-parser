# Relation Inference 개요

> 코드:
> - Domain ports: `src/document_inteligence/domain/repositories.py` → `RelationScorer`, `RelationReranker`, `CaptionVerifier`
> - Application: `src/document_inteligence/application/relationships.py`
> - Scorer: `src/document_inteligence/infrastructure/scorers/rule_based_scorer.py`
> - Reranker: `src/document_inteligence/infrastructure/rerankers/noop_reranker.py`

## 아키텍처

```
RelationScorer (ABC)
├── RuleBasedScorer     # proximity + alignment + size_ratio + position + text_hint 가중합
└── (VlmScorer)         # 향후 VLM 기반

RelationReranker (ABC)
├── NoopRelationReranker  # pass-through (기본)
└── (VlmReranker)         # 향후 VLM 기반 rerank/reject
```

## 관계 타입

- `title_of`: 제목 텍스트 → 다른 모든 원소
- `caption_of`: 텍스트가 이미지/표를 설명 (높은 confidence)
- `related_to`: 약한 연관 (중간 confidence, VLM fallback 대상)
- `illustrates`: (향후) 이미지가 텍스트를 예시로 설명

## 처리 흐름

1. Title 후보 탐색 → `title_of` 생성
2. 텍스트-비주얼 쌍마다 `RelationScorer.score()` 호출
3. `RelationReranker.rerank()`로 후보 필터/재정렬
4. VLM fallback: `related_to` 후보 중 `CaptionVerifier`로 promotion 시도
5. Greedy global assignment: confidence 내림차순, 중복 방지
6. 흡수된 텍스트는 후보에서 제외
7. 후보 의사결정 정보를 page metadata에 기록

## 출력 관측성

`DocumentPage.metadata["caption_candidate_decisions"]`에 후보 판정 로그가 기록됩니다.

주요 필드:

- `target_element_id`
- `candidate_element_id`
- `rule_score`
- `score_breakdown`
- `rejected_reason`
- `method` (`rule` / `vlm_fallback` / `vlm_rejected`)

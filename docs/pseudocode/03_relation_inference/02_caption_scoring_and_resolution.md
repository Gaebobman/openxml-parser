# Relation 점수화 + 충돌 해소

> 코드:
> - `src/openxml_parser/infrastructure/scorers/rule_based_scorer.py`
> - `src/openxml_parser/application/relationships.py`

## 후보 생성 (RuleBasedScorer)

각 visual(image/table)에 대해 텍스트 후보를 만들고 점수를 산출합니다.

후보 필터:
- X축 겹침 비율 ≥ `1 - alignment_tolerance`
- 수직 gap ≤ `caption_max_gap`
- 흡수된 텍스트는 제외

## 점수식 (5신호 가중합)

```text
score =
  rel_proximity_weight   * proximity        (gap 기반: 1 - gap/max_gap)
  + rel_alignment_weight * alignment        (X축 overlap ratio)
  + rel_size_ratio_weight * size_ratio_score (텍스트/비주얼 면적 비율)
  + rel_position_weight  * position_score   (below: 0.8, above: 0.6, else: 0.3)
  + rel_text_hint_weight * text_hint        (max(length_score, keyword_score))
  - bullet_penalty
```

기본 가중치 (ParserConfig):
- proximity: 0.35
- alignment: 0.25
- size_ratio: 0.15
- position: 0.15
- text_hint: 0.10

## 관계 타입 판정

- `score >= caption_rule_threshold` → `caption_of`
- `caption_vlm_threshold <= score < caption_rule_threshold` → `related_to`
  - VLM verifier가 있으면 `caption_of`로 promotion 시도
- `score < caption_vlm_threshold` → 후보 탈락

## 충돌 해소 (Greedy Global Assignment)

```pseudocode
sort all_candidates by score DESC
used_text_ids = {}
used_visual_rels = {}

FOR cand IN all_candidates:
    IF cand.text.id IN used_text_ids:
        reject("caption_already_assigned")
        CONTINUE
    IF cand.type == "title_of" AND visual already has "caption_of":
        reject("caption_takes_priority")
        CONTINUE
    accept(cand)
    used_text_ids.add(cand.text.id)
```

탈락 사유(`rejected_reason`) 예시:

- `no_candidate`
- `caption_already_assigned`
- `caption_takes_priority`

## Reranker 확장점

`NoopRelationReranker`는 후보를 그대로 통과시킵니다.

향후 VLM reranker 구현 시:
- 낮은 confidence 후보만 VLM에 전달
- accept/reject 판단으로 정밀도 향상
- `RelationReranker` domain port를 구현하여 주입

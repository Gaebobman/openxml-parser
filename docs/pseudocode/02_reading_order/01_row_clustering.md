# Reading Order 전략

> 코드:
> - Domain port: `src/document_inteligence/domain/repositories.py` → `ReadingOrderStrategy`
> - Application: `src/document_inteligence/application/reading_order.py`
> - Strategies: `src/document_inteligence/infrastructure/strategies/`

## 아키텍처

`ReadingOrderStrategy` domain port를 통해 전략을 교체할 수 있습니다.

```
ReadingOrderStrategy (ABC)
├── RowClusteringStrategy   # Y-tolerance 행 클러스터링
├── XYCutStrategy           # 재귀 XY-Cut
├── CompositeStrategy       # placeholder 우선 + fallback
└── (ModelBasedStrategy)    # 향후 VLM/모델 기반
```

설정: `ParserConfig.reading_order_strategy = "composite" | "row_clustering" | "xy_cut"`

## 1. Row Clustering

```pseudocode
FUNCTION order(elements, page):
    sorted_by_y = sort(elements, key=(y, x, z_order))
    rows = []
    FOR element IN sorted_by_y:
        placed = False
        FOR row IN rows:
            IF abs(element.y - row.first.y) <= row_tolerance:
                row.append(element)
                placed = True
                BREAK
        IF not placed:
            rows.append([element])
    ordered = []
    FOR row IN rows:
        ordered += sort(row, key=(x, z_order))
    RETURN ordered
```

## 2. XY-Cut

재귀적으로 페이지를 수평/수직 공백으로 분할하여 블록을 정렬합니다.

```pseudocode
FUNCTION xy_cut(elements):
    IF len(elements) <= 1: RETURN elements

    h_groups = try_horizontal_cut(elements)
    IF h_groups:
        RETURN concat(xy_cut(g) for g in h_groups)

    v_groups = try_vertical_cut(elements)
    IF v_groups:
        RETURN concat(xy_cut(g) for g in v_groups)

    RETURN sort(elements, key=(y, x, z_order))

FUNCTION try_horizontal_cut(elements):
    project intervals onto Y-axis
    find largest gap in sorted intervals
    IF gap >= gap_ratio: split and return two groups
    ELSE: RETURN None
```

## 3. Composite

```pseudocode
FUNCTION order(elements, page):
    with_idx = [e for e in elements if e.metadata.placeholder_idx exists]
    without_idx = [e for e in elements if not]

    indexed_ordered = sort(with_idx, key=placeholder_idx)
    rest_ordered = fallback_strategy.order(without_idx, page)

    RETURN indexed_ordered + rest_ordered
```


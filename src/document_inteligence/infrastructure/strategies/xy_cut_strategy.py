"""XY-Cut reading-order strategy.

Recursively partitions the page into blocks by finding large whitespace
gaps, then orders the leaf blocks top-to-bottom, left-to-right.

Better than row-clustering for multi-column layouts where elements
in different columns share similar Y coordinates.
"""
from __future__ import annotations

from document_inteligence.domain.entities import DocumentElement, DocumentPage
from document_inteligence.domain.repositories import ReadingOrderStrategy


class XYCutStrategy(ReadingOrderStrategy):
    """Recursive XY-Cut reading-order."""

    def __init__(self, gap_ratio: float = 0.025) -> None:
        self._gap_ratio = gap_ratio

    def order(
        self, elements: list[DocumentElement], page: DocumentPage
    ) -> list[DocumentElement]:
        if not elements:
            return []
        return self._xy_cut(list(elements), group_prefix="0")

    # ------------------------------------------------------------------

    def _xy_cut(
        self, elements: list[DocumentElement], group_prefix: str = "0",
    ) -> list[DocumentElement]:
        if len(elements) <= 1:
            for e in elements:
                e.metadata["spatial_group"] = group_prefix
            return elements

        h_groups = self._try_horizontal_cut(elements)
        if h_groups is not None:
            result: list[DocumentElement] = []
            for i, group in enumerate(h_groups):
                result.extend(self._xy_cut(group, f"{group_prefix}.h{i}"))
            return result

        v_groups = self._try_vertical_cut(elements)
        if v_groups is not None:
            result = []
            for i, group in enumerate(v_groups):
                result.extend(self._xy_cut(group, f"{group_prefix}.v{i}"))
            return result

        for e in elements:
            e.metadata["spatial_group"] = group_prefix
        return sorted(elements, key=lambda e: (e.bbox.y, e.bbox.x, e.z_order))

    def _try_horizontal_cut(
        self, elements: list[DocumentElement]
    ) -> list[list[DocumentElement]] | None:
        """Try to split elements by a horizontal gap (Y axis)."""
        intervals = sorted(
            [(e.bbox.y, e.bbox.y + e.bbox.height, e) for e in elements],
            key=lambda t: t[0],
        )
        return self._find_gap_split(intervals, axis="h")

    def _try_vertical_cut(
        self, elements: list[DocumentElement]
    ) -> list[list[DocumentElement]] | None:
        """Try to split elements by a vertical gap (X axis)."""
        intervals = sorted(
            [(e.bbox.x, e.bbox.x + e.bbox.width, e) for e in elements],
            key=lambda t: t[0],
        )
        return self._find_gap_split(intervals, axis="v")

    def _find_gap_split(
        self,
        intervals: list[tuple[float, float, DocumentElement]],
        axis: str,
    ) -> list[list[DocumentElement]] | None:
        """Find the largest gap and split if it exceeds the threshold."""
        if len(intervals) < 2:
            return None

        sorted_ends: list[tuple[float, float]] = []
        for start, end, _ in intervals:
            sorted_ends.append((start, end))

        max_gap = 0.0
        split_at = -1
        current_max_end = sorted_ends[0][1]

        for i in range(1, len(sorted_ends)):
            start_i = sorted_ends[i][0]
            gap = start_i - current_max_end
            if gap > max_gap:
                max_gap = gap
                split_at = i
            current_max_end = max(current_max_end, sorted_ends[i][1])

        if max_gap < self._gap_ratio or split_at < 1:
            return None

        group_a = [intervals[j][2] for j in range(split_at)]
        group_b = [intervals[j][2] for j in range(split_at, len(intervals))]

        if not group_a or not group_b:
            return None

        if axis == "h":
            group_a.sort(key=lambda e: (e.bbox.y, e.bbox.x))
            group_b.sort(key=lambda e: (e.bbox.y, e.bbox.x))
        else:
            group_a.sort(key=lambda e: (e.bbox.x, e.bbox.y))
            group_b.sort(key=lambda e: (e.bbox.x, e.bbox.y))

        return [group_a, group_b]

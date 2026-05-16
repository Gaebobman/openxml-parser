from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParserConfig:
    row_tolerance: float = 0.02
    caption_max_gap: float = 0.06
    alignment_tolerance: float = 0.08
    title_max_len: int = 80
    chunk_max_chars: int = 1200
    chunk_include_captions: bool = True
    caption_candidate_top_k: int = 5
    caption_rule_threshold: float = 0.65
    caption_vlm_threshold: float = 0.45
    table_cell_containment_threshold: float = 0.5
    containment_threshold: float = 0.6
    include_master_shapes: bool = True
    deduplicate_master_shapes: bool = True
    table_render_html: bool = True
    reading_order_strategy: str = "composite"
    xy_cut_gap_ratio: float = 0.006
    # Relation scoring weights (Phase 3)
    rel_proximity_weight: float = 0.35
    rel_alignment_weight: float = 0.25
    rel_size_ratio_weight: float = 0.15
    rel_position_weight: float = 0.15
    rel_text_hint_weight: float = 0.10
    # Noise filtering
    filter_noise_elements: bool = True
    min_element_area: float = 0.0001
    # Image annotation absorption
    absorb_image_annotations: bool = True
    image_annotation_containment_threshold: float = 0.5
    image_annotation_max_text_len: int = 60
    # Title scope
    title_max_y_distance: float = 0.5
    # Text formatting
    preserve_text_formatting: bool = True


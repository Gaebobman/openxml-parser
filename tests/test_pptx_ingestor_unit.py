from __future__ import annotations

from io import BytesIO

from lxml import etree
from PIL import Image

from document_inteligence.infrastructure.ingestors.pptx_ingestor import (
    _apply_picture_crop_if_needed,
    _build_bbox,
    _clamp_01,
    _extract_math_expressions_from_shape,
)


class _ShapeStub:
    def __init__(self, left: int, top: int, width: int, height: int):
        self.left = left
        self.top = top
        self.width = width
        self.height = height


class _MathShapeStub:
    def __init__(self, xml: str):
        self._element = etree.fromstring(xml.encode("utf-8"))


class _CropShapeStub:
    def __init__(self, *, left: float = 0.0, right: float = 0.0, top: float = 0.0, bottom: float = 0.0):
        self.crop_left = left
        self.crop_right = right
        self.crop_top = top
        self.crop_bottom = bottom


def test_clamp_01_bounds_value() -> None:
    assert _clamp_01(-1.0) == 0.0
    assert _clamp_01(0.5) == 0.5
    assert _clamp_01(1.5) == 1.0


def test_build_bbox_normalizes_coordinates() -> None:
    shape = _ShapeStub(left=100, top=50, width=400, height=200)
    bbox = _build_bbox(shape=shape, slide_width=1000.0, slide_height=500.0)

    assert bbox.x == 0.1
    assert bbox.y == 0.1
    assert bbox.width == 0.4
    assert bbox.height == 0.4


def test_extract_math_expressions_from_shape_omml() -> None:
    xml = """
    <root xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:oMath>
        <m:r><m:t>x</m:t></m:r>
        <m:r><m:t>+</m:t></m:r>
        <m:r><m:t>y</m:t></m:r>
      </m:oMath>
      <m:oMath>
        <m:r><m:t>z</m:t></m:r>
      </m:oMath>
    </root>
    """
    shape = _MathShapeStub(xml)
    exprs = _extract_math_expressions_from_shape(shape)
    assert exprs == ["x + y", "z"]


def test_apply_picture_crop_if_needed_crops_image() -> None:
    img = Image.new("RGB", (100, 50), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    blob = buf.getvalue()

    shape = _CropShapeStub(left=0.2, right=0.3, top=0.0, bottom=0.0)
    cropped_blob = _apply_picture_crop_if_needed(shape=shape, blob=blob, ext="png")

    out_img = Image.open(BytesIO(cropped_blob))
    # original width 100, left trim 20, right trim 30 -> 50
    assert out_img.size == (50, 50)


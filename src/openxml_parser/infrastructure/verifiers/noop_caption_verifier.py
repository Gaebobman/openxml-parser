from __future__ import annotations

from openxml_parser.domain.repositories import CaptionVerifier


class NoopCaptionVerifier(CaptionVerifier):
    """Default placeholder verifier for extension hooks."""

    def verify(
        self,
        *,
        page_number: int,
        image_element_id: str,
        caption_element_id: str,
        caption_text: str,
    ) -> tuple[bool, float]:
        # Not a real VLM call. Keeps extension point open.
        return (False, 0.0)


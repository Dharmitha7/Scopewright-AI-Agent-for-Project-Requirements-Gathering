"""Image evidence -> text via Groq multimodal models (D39, D59).

Whiteboard photos, architecture diagrams, UI sketches: described into plain
text so the same chunk/extract/belief pipeline handles them. Model comes from
GROQ_VISION_MODEL (default qwen/qwen3.6-27b - the llama-4 vision models were
retired from Groq's catalog).
"""

from __future__ import annotations

import base64
import mimetypes

from app.adapters.groq_client import groq_configured, groq_pool_from_settings
from app.core.config import Settings

DESCRIBE_PROMPT = (
    "This image is project evidence (a whiteboard, diagram, sketch, or screenshot) "
    "for a software project. Transcribe ALL readable text verbatim, then describe "
    "the structures shown (boxes, arrows, flows, lists) and what they convey. "
    "Plain text only, no invention beyond what is visible."
)


def describe_image(settings: Settings, filename: str, body: bytes) -> str:
    if not groq_configured(settings):
        return (
            f"[Scripted image description for {filename} - set GROQ_API_KEY for a real "
            "vision model. No image was analyzed.]"
        )
    mime = mimetypes.guess_type(filename)[0] or "image/png"
    data_url = f"data:{mime};base64,{base64.b64encode(body).decode()}"
    pool = groq_pool_from_settings(settings)
    assert pool is not None

    def _call(client):
        completion = client.chat.completions.create(
            model=settings.groq_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DESCRIBE_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        return (completion.choices[0].message.content or "").strip()

    return pool.execute(_call)

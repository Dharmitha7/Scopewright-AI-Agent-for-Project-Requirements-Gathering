"""Unit tests for inference helpers."""

import json
from unittest.mock import patch

import groq

from app.adapters.groq_client import GroqClientPool
from app.agents.inference import GroqInference, recover_json_tool_completion


class _FakeResponse:
    status_code = 400

    def __init__(self) -> None:
        self.request = object()


def test_recover_json_tool_completion_from_phantom_json_tool() -> None:
    payload = {
        "name": "json",
        "arguments": {
            "intent": "answer",
            "reply": "Confirmed.",
            "confirmed": True,
            "area_covered": True,
        },
    }
    exc = groq.BadRequestError(
        "tool failed",
        response=_FakeResponse(),
        body={
            "error": {
                "code": "tool_use_failed",
                "failed_generation": json.dumps(payload),
            }
        },
    )
    recovered = recover_json_tool_completion(exc)
    assert recovered is not None
    assert recovered.tool_calls == []
    parsed = json.loads(recovered.content or "{}")
    assert parsed["confirmed"] is True
    assert parsed["reply"] == "Confirmed."


def test_recover_json_tool_completion_ignores_other_errors() -> None:
    exc = groq.BadRequestError(
        "bad",
        response=_FakeResponse(),
        body={"error": {"code": "other"}},
    )
    assert recover_json_tool_completion(exc) is None


def test_complete_with_tools_recovers_phantom_json_tool() -> None:
    payload = {
        "name": "json",
        "arguments": {"reply": "Confirmed.", "intent": "answer"},
    }
    err = groq.BadRequestError(
        "tool failed",
        response=_FakeResponse(),
        body={
            "error": {
                "code": "tool_use_failed",
                "failed_generation": json.dumps(payload),
            }
        },
    )
    pool = GroqClientPool(["fake-key"])
    inference = GroqInference(pool=pool)
    with patch.object(pool, "execute", side_effect=err):
        result = inference.complete_with_tools(
            model="test",
            messages=[{"role": "user", "content": "yes"}],
            tools=[{"type": "function", "function": {"name": "search", "parameters": {}}}],
        )
    parsed = json.loads(result.content or "{}")
    assert parsed["reply"] == "Confirmed."

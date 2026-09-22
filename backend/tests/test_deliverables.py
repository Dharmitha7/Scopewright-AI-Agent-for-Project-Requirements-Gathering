"""Unit tests for Requirements deliverable catalog and pack composition helpers."""

from app.agents.deliverables import (
    PACK_KEYS,
    packs_for_widget,
    validate_pack_selection,
)
from app.agents.inference import ScriptedInference, complete_json, parse_json_object
from app.services.documents import (
    PACK_FAILED_MARKER,
    _build_stories_tree,
    _combine_packs,
    _stories_failure_body,
    _stories_markdown,
    _strip_duplicate_title,
    _strip_unprioritized_tags,
    _teaser,
    pack_body_failed,
)


def test_catalog_has_ten_packs() -> None:
    assert len(PACK_KEYS) == 10
    widget = packs_for_widget()
    assert len(widget) == 10
    assert widget[0]["key"] == "requirements_summary"


def test_validate_pack_selection_orders_and_dedupes() -> None:
    ordered = validate_pack_selection(
        ["user_journey", "requirements_summary", "user_journey"]
    )
    assert ordered == ["requirements_summary", "user_journey"]


def test_validate_pack_selection_rejects_empty_and_unknown() -> None:
    try:
        validate_pack_selection([])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "at least one" in str(exc)
    try:
        validate_pack_selection(["not_a_pack"])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "unknown" in str(exc)


def test_stories_markdown_what_why_how_and_optional_and() -> None:
    md = _stories_markdown(
        {
            "epics": [
                {
                    "title": "Access",
                    "features": [
                        {
                            "title": "Password reset",
                            "stories": [
                                {
                                    "title": "Reset via email",
                                    "what": "As a user, I want to reset my password.",
                                    "why": "Reduce support load.",
                                    "how": "Email a time-limited link.",
                                    "acceptance": {
                                        "happy": [
                                            {
                                                "name": "Request link",
                                                "steps": [
                                                    {"keyword": "Given", "text": "I am on login"},
                                                    {"keyword": "When", "text": "I submit email"},
                                                    {"keyword": "Then", "text": "I get a link"},
                                                    {
                                                        "keyword": "And",
                                                        "text": "the link expires later",
                                                    },
                                                ],
                                            }
                                        ],
                                        "sad": [
                                            {
                                                "name": "Unknown email",
                                                "steps": [
                                                    {"keyword": "Given", "text": "no account"},
                                                    {"keyword": "When", "text": "I submit"},
                                                    {"keyword": "Then", "text": "generic message"},
                                                ],
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )
    assert "# User Story: Reset via email" in md
    assert "**What**" in md
    assert "**Why**" in md
    assert "**How**" in md
    assert "### Happy Path" in md
    assert "### Sad Path" in md
    assert "- **Given** I am on login" in md
    assert "- **And** the link expires later" in md


def test_stories_failure_body_is_not_silent_not_stated() -> None:
    body = _stories_failure_body("outline truncated")
    assert pack_body_failed(body)
    assert PACK_FAILED_MARKER in body
    assert "generation failed" in body.lower()


def test_strip_duplicate_title_and_unprioritized_tags() -> None:
    dup = _strip_duplicate_title(
        "# Functional Requirements Specification\n\nFR-1 …",
        "Functional Requirements Specification",
    )
    assert dup.startswith("FR-1")
    tagged = _strip_unprioritized_tags("FR-1 [Unprioritized]\nFR-2 [unprioritized]")
    assert "[Unprioritized]" not in tagged
    assert tagged.startswith("FR-1")


def test_chunked_stories_tree_scripted() -> None:
    tree = _build_stories_tree(
        ScriptedInference(),
        model="scripted",
        project_brief="Fitness tracker",
        facts_blob="[tasks_scenarios] Log a workout manually",
    )
    assert tree["epics"]
    assert tree["epics"][0]["features"][0]["stories"]
    md = _stories_markdown(tree)
    assert "# User Story:" in md
    assert "**What**" in md


def test_parse_json_object_and_complete_json_retries() -> None:
    assert parse_json_object('noise {"a": 1} trailing') == {"a": 1}
    assert parse_json_object("not json") is None

    class Flaky:
        def __init__(self) -> None:
            self.n = 0

        def complete(self, **_kwargs):
            self.n += 1
            if self.n < 2:
                return "{truncated"
            return '{"ok": true}'

    assert complete_json(
        Flaky(), model="x", system="#purpose: t", user="u", attempts=3
    ) == {"ok": True}


def test_complete_json_swallows_provider_errors() -> None:
    """Groq 400 json_validate_failed must not blow up gate Generate (500)."""

    class Boom:
        def complete(self, **_kwargs):
            raise RuntimeError("Error code: 400 - json_validate_failed")

    assert complete_json(Boom(), model="x", system="#purpose: t", user="u", attempts=2) == {}


def test_compose_pack_failure_is_marked_not_raised() -> None:
    from unittest.mock import MagicMock, patch

    from app.agents.deliverables import PACK_BY_KEY
    from app.agents.templates import REQUIREMENTS
    from app.services.documents import _compose_pack

    pack = PACK_BY_KEY["functional_requirements"]
    with patch(
        "app.services.documents._llm_pack",
        side_effect=RuntimeError("rate limit"),
    ):
        body = _compose_pack(
            MagicMock(),
            MagicMock(brief="x"),
            REQUIREMENTS,
            pack,
            audit="# facts",
            critic_issues=[],
        )
    assert PACK_FAILED_MARKER in body
    assert pack_body_failed(body)


def test_complete_json_retries_past_provider_json_validation_rejection() -> None:
    """Groq's own json_mode validation can reject a completion outright
    (code json_validate_failed) instead of just returning bad text - a real,
    observed failure on the stories pack's large nested schema that used to
    skip complete_json's retry loop entirely and surface as an unhandled
    500. Confirms the retry now catches it and recovers."""
    import httpx
    from groq import BadRequestError

    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://api.groq.com/x"),
        json={"error": {"code": "json_validate_failed", "failed_generation": '{"broke'}},
    )
    rejection = BadRequestError(
        "json_validate_failed", response=response, body=response.json()
    )

    class RejectsOnce:
        def __init__(self) -> None:
            self.n = 0

        def complete(self, **_kwargs):
            self.n += 1
            if self.n < 2:
                raise rejection
            return '{"ok": true}'

    assert complete_json(
        RejectsOnce(), model="x", system="#purpose: t", user="u", attempts=3, json_mode=True
    ) == {"ok": True}


def test_combine_and_teaser() -> None:
    packs = {
        "requirements_summary": "# Requirements Summary\nHello",
        "user_journey": "# User Journey Document\nWorld",
    }
    combined = _combine_packs(packs)
    assert "Requirements Summary" in combined
    assert "User Journey Document" in combined
    assert "---" in combined
    short = _teaser("abc", limit=10)
    assert short == "abc"
    long = _teaser("line1\n" + ("x" * 2000), limit=20)
    assert "full deliverable" in long

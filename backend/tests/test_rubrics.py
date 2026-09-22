from app.agents.rubrics import area_rubric


def test_area_rubric_returns_planning_scope() -> None:
    text = area_rubric("planning", "scope")
    assert "Scope" in text
    assert "Essential" in text


def test_area_rubric_falls_back_to_guidance() -> None:
    text = area_rubric("planning", "missing", fallback_guidance="Custom guidance here.")
    assert "Custom guidance here" in text

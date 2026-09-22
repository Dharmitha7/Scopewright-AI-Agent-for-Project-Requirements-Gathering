"""Agent skill pack loader (D72) — interview skills only."""

from pathlib import Path

from app.agents.skills import interview_skill_ids, load_skill, skill_text


def test_load_core_ba_skill() -> None:
    text = load_skill("core_ba")
    assert "Never invent" in text
    assert load_skill.cache_info().hits >= 0  # lru_cache attached


def test_load_interview_skills() -> None:
    assert "Requirements interview" in load_skill("interview/requirements")
    assert "Planning interview" in load_skill("interview/planning")
    assert load_skill("docs/charter") == ""
    assert load_skill("docs/functional_requirements") == ""


def test_missing_and_unsafe_ids_return_empty() -> None:
    load_skill.cache_clear()
    assert load_skill("does/not/exist") == ""
    assert load_skill("../secrets") == ""
    assert load_skill("") == ""
    assert load_skill("  ") == ""


def test_skill_text_joins_and_skips_missing() -> None:
    load_skill.cache_clear()
    joined = skill_text("core_ba", "missing/skill", "interview/planning")
    assert "Never invent" in joined
    assert "Planning interview" in joined
    assert "missing" not in joined.lower()


def test_interview_skill_ids() -> None:
    assert interview_skill_ids("planning") == ("core_ba", "interview/planning")
    assert interview_skill_ids("requirements") == ("core_ba", "interview/requirements")


def test_skill_files_live_under_content() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "agents" / "skills" / "content"
    assert (root / "core_ba.md").is_file()
    assert (root / "interview" / "requirements.md").is_file()
    assert (root / "interview" / "planning.md").is_file()
    assert not (root / "docs" / "charter.md").is_file()

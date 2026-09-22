from app.agents.templates import PLANNING, REQUIREMENTS, get_template


def test_every_coverage_area_has_hint_and_guidance() -> None:
    for template in (PLANNING, REQUIREMENTS):
        for area in template.areas:
            assert area.hint.strip(), f"{area.key} missing hint"
            assert area.guidance.strip(), f"{area.key} missing guidance"
            assert "Explore:" in area.guidance, (
                f"{area.key} guidance should use Explore/Avoid/When thin structure"
            )


def test_requirements_labels_match_product_copy() -> None:
    req = get_template("requirements")
    labels = {a.key: a.label for a in req.areas}
    assert labels["users_goals"] == "Who it's for & why"
    assert labels["tasks_scenarios"] == "User flows"
    assert labels["failure_paths"] == "Errors & recovery"
    assert labels["rules_calculations"] == "Business rules"
    assert labels["data"] == "Data & records"
    assert labels["external_interfaces"] == "Integrations"
    assert labels["quality_targets"] == "Performance & reliability"
    assert labels["constraints_compliance"] == "Compliance & security"

from app.agents.interview import (
    answer_signals_enumeration_complete,
    describes_users_own_request,
    ensure_option_lists,
    guard_premature_enumeration_close,
    is_delegate_answer,
    is_explicit_skip,
    is_mostly_correct_add,
    is_unsure_answer,
    question_implies_more_items,
)


def test_describes_users_own_request_catches_narrated_meta_fact():
    """Regression: 'yes, show me the list' got extracted as a fabricated
    fact narrating the request itself instead of process_meta with no facts."""
    assert describes_users_own_request("User requested to see the MVP scope and exclusions list.")
    assert describes_users_own_request("The user asked to see what was recorded so far.")
    assert describes_users_own_request("User wants to know the current scope.")


def test_describes_users_own_request_leaves_real_product_facts_alone():
    assert not describes_users_own_request(
        "The app should show me a daily progress list after each session."
    )
    assert not describes_users_own_request("Users can request a report from the dashboard.")
    assert not describes_users_own_request("The system shall provide a pomodoro timer.")


def test_explicit_skip_phrases():
    assert is_explicit_skip("skip")
    assert is_explicit_skip("skip for now")
    assert is_explicit_skip("Skip this question")
    assert not is_explicit_skip("i dont know")
    assert not is_explicit_skip("Patients miss clinic slots.")


def test_unsure_not_skip():
    assert is_unsure_answer("i dont know")
    assert is_unsure_answer("I don't know")
    assert is_unsure_answer("idk")
    assert not is_unsure_answer("skip for now")
    assert not is_unsure_answer("Patients miss clinic slots.")


def test_delegate_beats_unsure():
    assert is_delegate_answer("i dont know, whichever you think are best")
    assert not is_unsure_answer("i dont know, whichever you think are best")


def test_mostly_correct_and_clarify():
    assert is_mostly_correct_add("Mostly correct, but I'd add...")
    assert is_mostly_correct_add("correct but i want to add something")
    assert not is_mostly_correct_add("Yes, that's correct")


def test_ensure_options_never_empty():
    lists = ensure_option_lists(["What is v1?"], None, area_key="scope")
    assert len(lists) == 1
    assert len(lists[0]) >= 3
    assert any("decide" in o.lower() for o in lists[0])


def test_question_implies_more_items_detects_first():
    assert question_implies_more_items(
        ["Which primary user's happy-path would you like to describe first?"]
    )
    assert not question_implies_more_items(["Walk through the onboarding flow step by step."])


def test_enumeration_complete_phrases():
    assert answer_signals_enumeration_complete("That's the only one for v1")
    assert not answer_signals_enumeration_complete(
        "New hire logs in and completes the checklist."
    )


def test_guard_blocks_close_without_enumeration_complete():
    covered, prompt, opts = guard_premature_enumeration_close(
        last_prompts=["Which flow would you like to describe first?"],
        answer_text="New hire completes onboarding checklist.",
        area_label="User flows",
        area_covered=True,
    )
    assert covered is False
    assert prompt
    assert opts


def test_guard_allows_close_when_user_confirms_only_one():
    covered, prompt, opts = guard_premature_enumeration_close(
        last_prompts=["Which flow would you like to describe first?"],
        answer_text="That's the only primary flow for v1.",
        area_label="User flows",
        area_covered=True,
    )
    assert covered is True
    assert prompt is None
    assert opts is None

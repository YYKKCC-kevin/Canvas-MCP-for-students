from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp import prompts
from canvas_mcp.server import mcp

EXPECTED = {
    "my_courses_overview",
    "course_requirements",
    "deadlines_and_exams",
    "summarize_lecture_materials",
    "study_for_exam",
    "start_assignment",
    "complete_assignment",
    "review_before_submit",
    "submit_assignment",
}


def _render_all() -> dict[str, str]:
    return {fn.__name__: fn() for fn in prompts.PROMPTS}


def test_all_prompts_are_registered_with_descriptions():
    listed = asyncio.run(mcp.list_prompts())
    assert {p.name for p in listed} == EXPECTED
    for p in listed:
        assert p.description, p.name


def test_every_prompt_works_with_no_arguments():
    for name, text in _render_all().items():
        assert text.strip(), name
        assert "{" not in text and "}" not in text, f"unformatted placeholder in {name}"


def test_prompts_only_reference_real_tools():
    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    for name, text in _render_all().items():
        for ref in set(re.findall(r"\btool_[a-z_]+\b", text)):
            assert ref in tools, f"{name} mentions unknown tool {ref}"


def test_missing_ids_make_the_assistant_find_and_confirm():
    text = prompts.start_assignment()
    assert "tool_list_courses" in text and "confirm the match" in text


def test_ids_are_interpolated():
    text = prompts.start_assignment("123", "456")
    assert "assignment 456 in course 123" in text
    assert "tool_list_courses" not in text.split("1. Call")[0]


def test_current_term_note_present_where_courses_are_listed():
    for fn in (prompts.my_courses_overview, prompts.deadlines_and_exams):
        assert "Term column" in fn()


def test_submit_requires_explicit_confirmation_and_no_default_comment():
    text = prompts.submit_assignment("1", "2", "/tmp/hw.pdf")
    assert "confirm_write=True" in text
    assert "replied yes" in text
    assert "confirm_comment" in text
    assert "/tmp/hw.pdf" in text
    # The confirmation summary must come before any submit call.
    assert text.index("ask for a clear yes") < text.index("Only after my yes")


def test_complete_assignment_gates_on_ai_permission():
    ungated = prompts.complete_assignment("1", "2")
    assert "AI-permission gate" in ungated
    gated = prompts.complete_assignment("1", "2", "syllabus allows AI with citation")
    assert "syllabus allows AI with citation" in gated
    assert "AI-permission gate" not in gated
    assert "follow the condition" in gated


def test_no_exam_refusal_in_prompts():
    for fn in (prompts.start_assignment, prompts.complete_assignment, prompts.submit_assignment):
        assert "proctored" not in fn(), fn.__name__
        assert "Exam guard" not in fn(), fn.__name__


def test_complete_assignment_does_not_submit():
    text = prompts.complete_assignment("1", "2", "allowed")
    assert "do not submit" in text
    assert "confirm_write" not in text


def test_lecture_summary_forbids_inventing_slide_content():
    text = prompts.summarize_lecture_materials("1", "Bayes")
    assert "Never invent slide content" in text
    assert "'Bayes'" in text
    assert "tool_read_course_file" in text
    assert "start_char" in text


def test_study_prompt_summarises_materials_and_predicts_with_evidence():
    text = prompts.study_for_exam("1", "Midterm")
    assert "Do not try to obtain" not in text
    assert "tool_read_course_file" in text and "past exams" in text
    assert "Predict the most likely questions" in text
    assert "confidence level" in text and "informed guesses" in text


def test_submit_prompt_covers_gradescope_without_taking_passwords():
    text = prompts.submit_assignment("1", "2")
    assert "tool_gradescope_submit_assignment" in text
    assert "install.py --gradescope-only" in text
    assert "not to paste the password into this chat" in text
    assert "if you can open a terminal" in text
    assert "Gradescope IDs differ from Canvas IDs" in text
    # preview first, real upload only after the student's yes
    assert text.index("without confirm_write") < text.index("Only after my yes, call it again")


def test_submit_prompt_uses_direct_gradescope_link_before_searching():
    text = prompts.submit_assignment("1", "2")
    assert "use those IDs directly" in text
    assert text.index("use those IDs directly") < text.index("Only if there is no such link")

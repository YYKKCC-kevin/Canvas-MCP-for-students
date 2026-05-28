from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp.client import _next_link
from canvas_mcp.client import CanvasClient
from canvas_mcp.formatting import clean_html, due_status
from canvas_mcp.browser_login import (
    _is_canvas_authenticated_url,
    canvas_settings_url,
    normalize_base_url,
)
from canvas_mcp.tools.assignments import (
    DEFAULT_DOWNLOAD_DIR,
    _assignment_resource_mismatch,
    _canvas_attachment_download_url,
)
from canvas_mcp.tools.course_content import (
    get_course_info,
    list_course_announcements,
    list_course_discussions,
    list_course_modules,
    list_exam_items,
)
from canvas_mcp.tools.learning import (
    check_my_draft,
    create_homework_template,
    extract_due_and_submission_target,
    generate_hint_pack,
    make_practice_version,
    prepare_multi_agent_review_packet,
    prepare_solution_review_artifact,
    prepare_homework_help_pack,
    review_submission_file,
    review_solution_for_chat,
    review_solution_correctness,
)
from canvas_mcp.tools.sources import resolve_assignment_source_from_canvas
from canvas_mcp.tools.submissions import submit_text_assignment, submit_url_assignment
from canvas_mcp.tools.submissions import submit_file_assignment


class FakeCanvasClient:
    def __init__(self, paginated: dict[str, list[dict]] | None = None, single: dict | None = None):
        self.paginated = paginated or {}
        self.single = single or {}
        self.calls: list[tuple[str, object]] = []

    def get_paginated(self, path: str, params=None) -> list[dict]:
        self.calls.append((path, params))
        return self.paginated.get(path, [])

    def get(self, path: str, params=None) -> dict:
        self.calls.append((path, params))
        return self.single


def test_next_link_extracts_canvas_pagination_url() -> None:
    header = (
        '<https://canvas.example.edu/api/v1/courses?page=1>; rel="current", '
        '<https://canvas.example.edu/api/v1/courses?page=2>; rel="next"'
    )

    assert _next_link(header) == "https://canvas.example.edu/api/v1/courses?page=2"


def test_clean_html_returns_plain_text() -> None:
    html = "<p>Hello <strong>Canvas</strong></p><script>bad()</script>"

    assert clean_html(html) == "Hello Canvas"


def test_due_status_marks_overdue_without_submission() -> None:
    assert due_status("2020-01-01T00:00:00Z", None) == "overdue"


def test_submit_text_requires_explicit_confirmation() -> None:
    result = submit_text_assignment("101", "202", "<p>answer</p>")

    assert "Write confirmation required" in result
    assert "No changes were made." in result
    assert "confirm_write=True" in result


def test_submit_url_requires_explicit_confirmation() -> None:
    result = submit_url_assignment("101", "202", "https://example.com/homework")

    assert "Write confirmation required" in result
    assert "No changes were made." in result
    assert "confirm_write=True" in result


def test_submit_file_requires_explicit_confirmation(tmp_path: Path) -> None:
    finished = tmp_path / "finished.pdf"
    finished.write_bytes(b"%PDF-1.4\n")

    result = submit_file_assignment("101", "202", str(finished))

    assert "Write confirmation required" in result
    assert "online_upload" in result
    assert "No changes were made." in result


def test_browser_login_helper_builds_settings_url() -> None:
    assert (
        canvas_settings_url("canvas.eee.uci.edu")
        == "https://canvas.eee.uci.edu/profile/settings"
    )


def test_browser_login_helper_normalizes_default_url() -> None:
    assert normalize_base_url(None) == "https://canvas.eee.uci.edu"


def test_browser_login_helper_detects_authenticated_canvas_url() -> None:
    assert _is_canvas_authenticated_url(
        "https://canvas.eee.uci.edu/profile/settings",
        "http://canvas.eee.uci.edu/",
    )
    assert not _is_canvas_authenticated_url(
        "https://idp.uci.edu/idp/profile/SAML2/Redirect/SSO",
        "https://canvas.eee.uci.edu",
    )
    assert not _is_canvas_authenticated_url(
        "https://canvas.eee.uci.edu/login/canvas",
        "https://canvas.eee.uci.edu",
    )


def test_canvas_client_loads_browser_storage_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "_canvas_session",
                        "value": "abc123",
                        "domain": "canvas.example.edu",
                        "path": "/",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    client = CanvasClient(
        base_url="https://canvas.example.edu",
        storage_state_path=str(state_path),
    )

    assert client.session.cookies.get("_canvas_session") == "abc123"
    assert "Authorization" not in client.session.headers


def test_canvas_attachment_metadata_can_resolve_download_url() -> None:
    class Response:
        headers = {"Content-Type": "application/json"}

        def json(self) -> dict:
            return {"attachment": {"url": "https://canvas.example.edu/files/1/download"}}

    assert (
        _canvas_attachment_download_url(Response())
        == "https://canvas.example.edu/files/1/download"
    )


def test_list_course_announcements_formats_recent_notices(monkeypatch) -> None:
    fake_client = FakeCanvasClient(
        paginated={
            "/announcements": [
                {
                    "title": "Final Exam Room",
                    "posted_at": "2026-05-20T20:00:00Z",
                    "message": "<p>Bring your student ID.</p>",
                    "html_url": "https://canvas.example.edu/announcements/1",
                    "author": {"display_name": "Prof. Example"},
                }
            ]
        }
    )
    monkeypatch.setattr("canvas_mcp.tools.course_content.get_client", lambda: fake_client)
    monkeypatch.setattr(
        "canvas_mcp.tools.course_content.fetch_courses",
        lambda *_args, **_kwargs: [{"id": 101, "name": "ECON 120B"}],
    )

    result = list_course_announcements(days_back=14)

    assert "Canvas Course Announcements" in result
    assert "ECON 120B" in result
    assert "Final Exam Room" in result
    assert "Bring your student ID." in result
    assert "Prof. Example" in result
    assert fake_client.calls[0][0] == "/announcements"


def test_list_exam_items_filters_exam_like_assignments(monkeypatch) -> None:
    monkeypatch.setattr(
        "canvas_mcp.tools.course_content.fetch_courses",
        lambda *_args, **_kwargs: [{"id": 101, "name": "ECON 120B"}],
    )
    monkeypatch.setattr(
        "canvas_mcp.tools.course_content.fetch_course_assignments",
        lambda *_args, **_kwargs: [
            {
                "id": 1,
                "name": "Final Exam",
                "due_at": "2026-06-10T23:59:00Z",
                "points_possible": 100,
                "submission_types": ["online_upload"],
                "html_url": "https://canvas.example.edu/final",
                "submission": {},
            },
            {
                "id": 2,
                "name": "Homework Assignment #5",
                "due_at": "2026-06-01T23:59:00Z",
                "points_possible": 100,
                "submission_types": ["online_quiz"],
                "html_url": "https://canvas.example.edu/homework",
                "submission": {},
            },
        ],
    )

    result = list_exam_items()

    assert "Canvas Exam / Quiz / Test Items" in result
    assert "Final Exam" in result
    assert "Homework Assignment #5" not in result


def test_list_course_discussions_excludes_announcements_by_default(monkeypatch) -> None:
    fake_client = FakeCanvasClient(
        paginated={
            "/courses/101/discussion_topics": [
                {
                    "id": 1,
                    "title": "Problem Set Thread",
                    "posted_at": "2026-05-22T12:00:00Z",
                    "message": "<p>Ask questions here.</p>",
                    "html_url": "https://canvas.example.edu/discussions/1",
                    "author": {"display_name": "TA"},
                },
                {
                    "id": 2,
                    "title": "Announcement Thread",
                    "is_announcement": True,
                    "posted_at": "2026-05-23T12:00:00Z",
                },
            ]
        }
    )
    monkeypatch.setattr("canvas_mcp.tools.course_content.get_client", lambda: fake_client)

    result = list_course_discussions("101")

    assert "Canvas Course Discussions" in result
    assert "Problem Set Thread" in result
    assert "Ask questions here." in result
    assert "Announcement Thread" not in result


def test_get_course_info_includes_syllabus_preview(monkeypatch) -> None:
    fake_client = FakeCanvasClient(
        single={
            "id": 101,
            "name": "ECON 120B",
            "course_code": "ECON120B",
            "workflow_state": "available",
            "time_zone": "America/Los_Angeles",
            "term": {"name": "Spring 2026"},
            "teachers": [{"display_name": "Prof. Example"}],
            "syllabus_body": "<p>Lecture meets Tuesday and Thursday.</p>",
        }
    )
    monkeypatch.setattr("canvas_mcp.tools.course_content.get_client", lambda: fake_client)

    result = get_course_info("101")

    assert "# ECON 120B" in result
    assert "Spring 2026" in result
    assert "Prof. Example" in result
    assert "Lecture meets Tuesday and Thursday." in result


def test_list_course_modules_includes_class_material_items(monkeypatch) -> None:
    fake_client = FakeCanvasClient(
        paginated={
            "/courses/101/modules": [
                {
                    "name": "Week 9 Lectures",
                    "published": True,
                    "items": [
                        {
                            "title": "Lecture 17 Slides",
                            "type": "File",
                            "published": True,
                            "html_url": "https://canvas.example.edu/files/1",
                            "completion_requirement": {"type": "must_view"},
                        }
                    ],
                }
            ]
        }
    )
    monkeypatch.setattr("canvas_mcp.tools.course_content.get_client", lambda: fake_client)

    result = list_course_modules("101")

    assert "Canvas Course Modules" in result
    assert "Week 9 Lectures" in result
    assert "Lecture 17 Slides" in result
    assert "must_view" in result


def test_default_download_dir_is_project_relative() -> None:
    assert DEFAULT_DOWNLOAD_DIR == "canvas-mcp-downloads"


def test_assignment_resource_mismatch_detects_wrong_homework_file() -> None:
    result = _assignment_resource_mismatch("Assignment 4", "HW2.pdf")

    assert result is not None
    assert "number 4" in result
    assert "number 2" in result


def test_assignment_resource_mismatch_allows_matching_homework_file() -> None:
    assert (
        _assignment_resource_mismatch(
            "Homework 6",
            "Stats120C_281C_homework6_S26.pdf",
        )
        is None
    )


def test_assignment_resource_mismatch_ignores_unnumbered_resources() -> None:
    assert _assignment_resource_mismatch("Assignment 4", "rubric.pdf") is None


def test_learning_template_keeps_student_work_blank() -> None:
    assignment_text = "1. Fit a regression model.\n\na. Estimate beta.\n\n2. Prove the result."

    result = create_homework_template("Homework 6", assignment_text)

    assert "# Homework 6 Template" in result
    assert "## Problem 1" in result
    assert "## Problem 2" in result
    assert "[Write your work here.]" in result
    assert "Fit a regression model." not in result


def test_learning_template_deduplicates_and_handles_pdf_question_noise() -> None:
    noisy_text = """
    1. First regression question.
    no 2.parameters     is known
           In lecture, we showed the following result:
    3. Intercept only question.
    1. First regression question.
    """

    result = create_homework_template("Homework 6", noisy_text)

    assert result.count("## Problem 1") == 1
    assert "## Problem 2" in result
    assert "## Problem 3" in result


def test_learning_hint_pack_includes_method_support() -> None:
    assignment_text = "1. Use summary statistics to calculate least squares estimates."

    result = generate_hint_pack("Homework 6", assignment_text)

    assert "Homework Support Pack" in result
    assert "plan, draft, verify, and improve" in result
    assert "least squares" in result.lower()


def test_learning_draft_checker_reports_missing_sections() -> None:
    assignment_text = "1. First question.\n\n2. Second question."
    draft_text = "Problem 1\nI did this one."

    result = check_my_draft("Homework 6", assignment_text, draft_text)

    assert "Problem 2" in result
    assert "not found" in result


def test_review_submission_file_reports_ready_when_sections_are_present(tmp_path: Path) -> None:
    prompt = tmp_path / "hw4_prompt.txt"
    prompt.write_text(
        "Problem 1: Compute the risk.\nProblem 2: Derive the SURE formula.\n",
        encoding="utf-8",
    )
    solution = tmp_path / "HW4_solutions.txt"
    solution.write_text(
        "HW4 Solutions\n\nProblem 1\nTherefore the risk is derived.\n\n"
        "Problem 2\nHence the SURE formula follows.\n",
        encoding="utf-8",
    )

    result = review_submission_file(
        "Homework 4",
        str(solution),
        assignment_path=str(prompt),
    )

    assert "Looks ready for submission" in result
    assert "Expected problems: 1, 2" in result


def test_review_submission_file_flags_prompt_only_submission(tmp_path: Path) -> None:
    prompt = tmp_path / "HW4.txt"
    prompt.write_text(
        "Due: Sunday\nPoints 100\nProblem 1: Show that the estimator works.\n"
        "Problem 2: Compute the risk and derive the formula.\n",
        encoding="utf-8",
    )

    result = review_submission_file("Homework 4", str(prompt), assignment_path=str(prompt))

    assert "Needs attention before submission" in result
    assert "prompt/assignment" in result


def test_review_solution_correctness_warns_without_reference(tmp_path: Path) -> None:
    solution = tmp_path / "solution.txt"
    solution.write_text("Problem 1\nTherefore the estimator is unbiased.\n", encoding="utf-8")

    result = review_solution_correctness(
        "Homework 4",
        solution_path=str(solution),
        assignment_text="Problem 1: Show that the estimator is unbiased.",
    )

    assert "Confidence: low" in result
    assert "No reference answer or rubric was provided" in result


def test_review_solution_correctness_flags_reference_mismatch(tmp_path: Path) -> None:
    solution = tmp_path / "solution.txt"
    reference = tmp_path / "reference.txt"
    solution.write_text("Problem 1\nFinal answer: R(theta, delta_P)=1/(12n).\n", encoding="utf-8")
    reference.write_text(
        "Problem 1\nFinal answer: R(theta, delta_P)=1/(2(n+1)(n+2)).\n",
        encoding="utf-8",
    )

    result = review_solution_correctness(
        "Homework 4",
        solution_path=str(solution),
        assignment_text="Problem 1: Compute the risk.",
        reference_path=str(reference),
    )

    assert "Needs correctness review" in result
    assert "Missing or mismatched reference answer" in result


def test_review_solution_correctness_passes_matching_reference(tmp_path: Path) -> None:
    solution = tmp_path / "solution.txt"
    reference = tmp_path / "reference.txt"
    text = "Problem 1\nFinal answer: R(theta, delta_P)=1/(2(n+1)(n+2)).\n"
    solution.write_text(text, encoding="utf-8")
    reference.write_text(text, encoding="utf-8")

    result = review_solution_correctness(
        "Homework 4",
        solution_path=str(solution),
        assignment_text="Problem 1: Compute the risk.",
        reference_path=str(reference),
    )

    assert "No obvious correctness issues found" in result
    assert "Confidence: medium" in result


def test_prepare_solution_review_artifact_without_reference(tmp_path: Path) -> None:
    result = prepare_solution_review_artifact(
        "Homework 4",
        solution_text="Problem 1\nThe risk is 1/(2(n+1)(n+2)).",
        assignment_text="Problem 1: Compute the risk.",
        output_dir=str(tmp_path),
    )

    artifact = tmp_path / "Homework-4-review.md"
    text = artifact.read_text(encoding="utf-8")

    assert "Solution Review Artifact Prepared" in result
    assert "Reference status: missing" in result
    assert "derive a provisional expected solution" in text
    assert "Student Solution" in text
    assert "do not stop after reporting this artifact path" in text
    assert "In-Chat Review Prompt" in result


def test_prepare_solution_review_artifact_with_reference_and_rubric(tmp_path: Path) -> None:
    result = prepare_solution_review_artifact(
        "Homework 4",
        solution_text="Problem 1\nThe risk is 1/(2(n+1)(n+2)).",
        assignment_text="Problem 1: Compute the risk.",
        reference_text="Problem 1\nThe risk is 1/(2(n+1)(n+2)).",
        rubric_text="Full credit requires the correct risk formula.",
        output_dir=str(tmp_path),
    )

    artifact = tmp_path / "Homework-4-review.md"
    text = artifact.read_text(encoding="utf-8")

    assert "Reference status: user-provided reference answer plus rubric" in result
    assert "Reference Answer" in text
    assert "Full credit requires" in text


def test_review_solution_for_chat_returns_artifact_and_detected_signals(tmp_path: Path) -> None:
    result = review_solution_for_chat(
        "Homework 4",
        solution_text="Problem 1\nFinal answer: 1/(12n).",
        assignment_text="Problem 1: Compute the risk.",
        reference_text="Problem 1\nFinal answer: 1/(2(n+1)(n+2)).",
        output_dir=str(tmp_path),
    )

    assert "Chat-Ready Solution Review" in result
    assert "User-Facing Chat Summary" in result
    assert "Parts That May Be Inaccurate Or Need Revision" in result
    assert "Solution Review Artifact Prepared" in result
    assert "Missing or mismatched reference answer" in result
    assert "Required Follow-Up In The Conversation" in result
    assert "do not only return the artifact path" in result


def test_prepare_multi_agent_review_packet_guides_consensus_workflow(tmp_path: Path) -> None:
    result = prepare_multi_agent_review_packet(
        "Homework 5",
        solution_text="Problem 1\nFinal answer: 1.52 to 6.48.",
        assignment_text="Problem 1: Compute a 99% confidence interval.",
        output_dir=str(tmp_path),
    )

    artifact = tmp_path / "Homework-5-multi-agent-review.md"
    text = artifact.read_text(encoding="utf-8")

    assert "Multi-Agent Review Packet Prepared" in result
    assert "Host-agent workflow required" in result
    assert "MCP cannot directly spawn Codex/Claude subagents" in result
    assert "Solver Agent Packet" in text
    assert "Reviewer Agent Packet" in text
    assert "Disagreement Resolution Packet" in text
    assert "send the disputed items back to the solver" in text


def test_learning_practice_version_changes_context() -> None:
    assignment_text = "1. Use summary statistics to calculate least squares estimates."

    result = make_practice_version("Homework 6", assignment_text)

    assert "Practice Version" in result
    assert "similar but not identical" in result
    assert "least squares" in result.lower()


def test_homework_help_pack_requests_confirmation_on_mismatch(monkeypatch) -> None:
    def fake_prepare_assignment_workspace(*args, **kwargs) -> str:
        return "\n".join(
            [
                "## Assignment Workspace Prepared",
                "",
                "- Folder: `/tmp/course_1/assignment_2_Assignment-4`",
                "",
                "### User Confirmation Required",
                "- Assignment name `Assignment 4` appears to be number 4, "
                "but linked file/resource `HW2.pdf` appears to be number 2.",
            ]
        )

    monkeypatch.setattr(
        "canvas_mcp.tools.learning.prepare_assignment_workspace",
        fake_prepare_assignment_workspace,
    )

    result = prepare_homework_help_pack("1", "2")

    assert "Homework Help Pack Awaiting Confirmation" in result
    assert "allow_mismatched_files=True" in result
    assert "Not Prepared" not in result


def test_homework_help_pack_waits_when_source_is_external(monkeypatch) -> None:
    def fake_prepare_assignment_workspace(*args, **kwargs) -> str:
        return "\n".join(
            [
                "## Assignment Workspace Prepared",
                "",
                "- Folder: `/tmp/course_1/assignment_2_Assignment-4`",
                "- Downloaded files: 0",
            ]
        )

    monkeypatch.setattr(
        "canvas_mcp.tools.learning.prepare_assignment_workspace",
        fake_prepare_assignment_workspace,
    )
    monkeypatch.setattr(
        "canvas_mcp.tools.learning.resolve_assignment_source",
        lambda *args, **kwargs: "## Assignment Source Likely GitHub\n\n- repo",
    )

    result = prepare_homework_help_pack("1", "2")

    assert "Homework Help Pack Awaiting Assignment Source" in result
    assert "Assignment Source Likely GitHub" in result


def test_assignment_source_resolver_detects_gradescope_link() -> None:
    html = """
    <p>Submit this homework on Gradescope.</p>
    <p><a href="https://www.gradescope.com/courses/123/assignments/456">Gradescope HW</a></p>
    """

    result = resolve_assignment_source_from_canvas(
        "Homework 4",
        html,
        "https://canvas.example.edu",
    )

    assert "Assignment Source Likely Gradescope" in result
    assert "tool_gradescope_bridge_status" in result
    assert "https://www.gradescope.com/courses/123/assignments/456" in result


def test_assignment_source_resolver_detects_github_source() -> None:
    html = """
    <p>The homework is maintained in the course repo.</p>
    <a href="https://github.com/example/stat220b-homework/blob/main/hw4.pdf">HW4</a>
    """

    result = resolve_assignment_source_from_canvas(
        "Assignment 4",
        html,
        "https://canvas.example.edu",
    )

    assert "Assignment Source Likely GitHub" in result
    assert "https://github.com/example/stat220b-homework/blob/main/hw4.pdf" in result


def test_assignment_source_resolver_asks_user_when_canvas_source_is_missing() -> None:
    result = resolve_assignment_source_from_canvas(
        "Assignment 4",
        "<p>See syllabus for details.</p>",
        "https://canvas.example.edu",
    )

    assert "Assignment Source Needed From User" in result
    assert "GitHub" in result
    assert "Gradescope" in result
    assert "local file" in result


def test_extract_due_and_submission_target_detects_gradescope() -> None:
    details = """
    - Due: 2026-05-31 23:59 PDT
    Submissions are to be done on Gradescope.
    """

    result = extract_due_and_submission_target(details)

    assert "2026-05-31 23:59 PDT" in result
    assert "Gradescope" in result

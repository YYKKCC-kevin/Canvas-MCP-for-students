from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp.client import _next_link
from canvas_mcp.client import CanvasClient
from canvas_mcp.formatting import clean_html, due_status
from canvas_mcp.browser_login import canvas_settings_url, normalize_base_url
from canvas_mcp.tools.assignments import (
    DEFAULT_DOWNLOAD_DIR,
    _assignment_resource_mismatch,
    _canvas_attachment_download_url,
)
from canvas_mcp.tools.learning import (
    check_my_draft,
    create_homework_template,
    extract_due_and_submission_target,
    generate_hint_pack,
    make_practice_version,
    prepare_homework_help_pack,
)
from canvas_mcp.tools.sources import resolve_assignment_source_from_canvas
from canvas_mcp.tools.submissions import submit_text_assignment, submit_url_assignment
from canvas_mcp.tools.submissions import submit_file_assignment


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


def test_learning_hint_pack_is_not_answer_pack() -> None:
    assignment_text = "1. Use summary statistics to calculate least squares estimates."

    result = generate_hint_pack("Homework 6", assignment_text)

    assert "Hint Pack" in result
    assert "not final answers" in result
    assert "least squares" in result.lower()


def test_learning_draft_checker_reports_missing_sections() -> None:
    assignment_text = "1. First question.\n\n2. Second question."
    draft_text = "Problem 1\nI did this one."

    result = check_my_draft("Homework 6", assignment_text, draft_text)

    assert "Problem 2" in result
    assert "not found" in result


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

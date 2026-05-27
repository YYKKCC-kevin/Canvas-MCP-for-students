from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp.client import _next_link
from canvas_mcp.client import CanvasClient
from canvas_mcp.formatting import clean_html, due_status
from canvas_mcp.browser_login import canvas_settings_url, normalize_base_url
from canvas_mcp.tools.assignments import DEFAULT_DOWNLOAD_DIR, _canvas_attachment_download_url
from canvas_mcp.tools.learning import (
    check_my_draft,
    create_homework_template,
    extract_due_and_submission_target,
    generate_hint_pack,
    make_practice_version,
)
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


def test_extract_due_and_submission_target_detects_gradescope() -> None:
    details = """
    - Due: 2026-05-31 23:59 PDT
    Submissions are to be done on Gradescope.
    """

    result = extract_due_and_submission_target(details)

    assert "2026-05-31 23:59 PDT" in result
    assert "Gradescope" in result

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp.client import _next_link
from canvas_mcp.formatting import clean_html, due_status
from canvas_mcp.tools.submissions import submit_text_assignment, submit_url_assignment


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

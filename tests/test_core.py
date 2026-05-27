from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp.client import _next_link
from canvas_mcp.client import CanvasClient
from canvas_mcp.formatting import clean_html, due_status
from canvas_mcp.browser_login import canvas_settings_url, normalize_base_url
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

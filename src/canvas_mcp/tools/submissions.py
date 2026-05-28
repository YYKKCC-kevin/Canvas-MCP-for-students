"""Submission-related Canvas tools."""

from __future__ import annotations

import os
from pathlib import Path

from canvas_mcp.auth import AuthError, get_client
from canvas_mcp.client import CanvasApiError
from canvas_mcp.formatting import clean_html, human_datetime


def _write_confirmation(action: str, details: list[str]) -> str:
    lines = [
        f"Write confirmation required for `{action}`.",
        "No changes were made.",
    ]
    lines.extend(f"- {detail}" for detail in details)
    lines.append("- Re-run with `confirm_write=True` to execute this change.")
    return "\n".join(lines)


def _comment_confirmation(action: str, details: list[str]) -> str:
    lines = [
        f"Comment confirmation required for `{action}`.",
        "No changes were made.",
        "A submission comment was provided. Comments are only sent when the user explicitly requests the exact comment.",
    ]
    lines.extend(f"- {detail}" for detail in details)
    lines.append(
        "- Re-run with `confirm_write=True` and `confirm_comment=True` to submit with this comment."
    )
    return "\n".join(lines)


def _clean_comment(comment: str | None) -> str | None:
    value = (comment or "").strip()
    return value or None


def get_my_submission(course_id: str, assignment_id: str) -> str:
    """Get the current user's submission state for an assignment."""
    try:
        client = get_client()
        submission = client.get(
            f"/courses/{course_id}/assignments/{assignment_id}/submissions/self",
            params=[
                ("include[]", "submission_comments"),
                ("include[]", "rubric_assessment"),
                ("include[]", "assignment"),
            ],
        )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error fetching submission: {e}"

    assignment = submission.get("assignment") or {}
    lines = [
        "## My Canvas Submission",
        "",
        f"- Course ID: `{course_id}`",
        f"- Assignment ID: `{assignment_id}`",
        f"- Assignment: {assignment.get('name') or ''}",
        f"- Workflow state: {submission.get('workflow_state')}",
        f"- Submitted at: {human_datetime(submission.get('submitted_at')) or '(not submitted)'}",
        f"- Grade: {submission.get('grade') or '(none)'}",
        f"- Score: {submission.get('score')}",
        f"- Late: {submission.get('late')}",
        f"- Missing: {submission.get('missing')}",
        f"- URL submission: {submission.get('url') or ''}",
    ]
    if submission.get("body"):
        lines.extend(["", "## Body", "", clean_html(submission.get("body"), 4000)])
    comments = submission.get("submission_comments") or []
    if comments:
        lines.extend(["", "## Comments"])
        for comment in comments:
            lines.append(
                f"- {human_datetime(comment.get('created_at'))}: "
                f"{comment.get('author_name') or 'Unknown'}: "
                f"{clean_html(comment.get('comment'), 500)}"
            )
    return "\n".join(lines)


def submit_text_assignment(
    course_id: str,
    assignment_id: str,
    html_body: str,
    comment: str | None = None,
    confirm_write: bool = False,
    confirm_comment: bool = False,
) -> str:
    """Submit an online text entry assignment. Requires confirm_write=True."""
    if not html_body.strip():
        return "Error: html_body is empty."
    comment = _clean_comment(comment)
    details = [
        f"course_id=`{course_id}`",
        f"assignment_id=`{assignment_id}`",
        "submission_type=`online_text_entry`",
        f"body_length={len(html_body)}",
        f"body_preview={html_body[:240]!r}",
    ]
    if comment:
        details.append(f"comment={comment[:240]!r}")
    if not confirm_write:
        return _write_confirmation("submit_text_assignment", details)
    if comment and not confirm_comment:
        return _comment_confirmation("submit_text_assignment", details)

    try:
        client = get_client()
        data = {
            "submission[submission_type]": "online_text_entry",
            "submission[body]": html_body,
        }
        if comment:
            data["comment[text_comment]"] = comment
        result = client.post_form(
            f"/courses/{course_id}/assignments/{assignment_id}/submissions",
            data=data,
        )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error submitting assignment: {e}"

    return (
        "## Submission Saved\n\n"
        f"- Workflow state: {result.get('workflow_state')}\n"
        f"- Submitted at: {human_datetime(result.get('submitted_at'))}\n"
        f"- Attempt: {result.get('attempt')}\n"
        f"- Preview URL: {result.get('preview_url') or result.get('html_url') or ''}"
    )


def submit_url_assignment(
    course_id: str,
    assignment_id: str,
    url: str,
    comment: str | None = None,
    confirm_write: bool = False,
    confirm_comment: bool = False,
) -> str:
    """Submit an online URL assignment. Requires confirm_write=True."""
    if not url.strip():
        return "Error: url is empty."
    comment = _clean_comment(comment)
    details = [
        f"course_id=`{course_id}`",
        f"assignment_id=`{assignment_id}`",
        "submission_type=`online_url`",
        f"url={url}",
    ]
    if comment:
        details.append(f"comment={comment[:240]!r}")
    if not confirm_write:
        return _write_confirmation("submit_url_assignment", details)
    if comment and not confirm_comment:
        return _comment_confirmation("submit_url_assignment", details)

    try:
        client = get_client()
        data = {
            "submission[submission_type]": "online_url",
            "submission[url]": url,
        }
        if comment:
            data["comment[text_comment]"] = comment
        result = client.post_form(
            f"/courses/{course_id}/assignments/{assignment_id}/submissions",
            data=data,
        )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error submitting assignment: {e}"

    return (
        "## URL Submission Saved\n\n"
        f"- Workflow state: {result.get('workflow_state')}\n"
        f"- Submitted at: {human_datetime(result.get('submitted_at'))}\n"
        f"- Attempt: {result.get('attempt')}\n"
        f"- Submitted URL: {result.get('url') or url}"
    )


def submit_file_assignment(
    course_id: str,
    assignment_id: str,
    file_path: str,
    comment: str | None = None,
    confirm_write: bool = False,
    confirm_comment: bool = False,
) -> str:
    """Submit a completed local file to a Canvas online-upload assignment."""
    path = Path(file_path).expanduser()
    if not path.exists() or not path.is_file():
        return f"Error: file_path does not exist or is not a file: {path}"
    comment = _clean_comment(comment)

    details = [
        f"course_id=`{course_id}`",
        f"assignment_id=`{assignment_id}`",
        "submission_type=`online_upload`",
        f"file=`{path}`",
        f"size_bytes={path.stat().st_size}",
    ]
    if comment:
        details.append(f"comment={comment[:240]!r}")
    if not confirm_write:
        return _write_confirmation("submit_file_assignment", details)
    if comment and not confirm_comment:
        return _comment_confirmation("submit_file_assignment", details)

    try:
        client = get_client()
        file_id = client.upload_submission_file(course_id, assignment_id, path)
        data = {
            "submission[submission_type]": "online_upload",
            "submission[file_ids][]": str(file_id),
        }
        if comment:
            data["comment[text_comment]"] = comment
        result = client.post_form(
            f"/courses/{course_id}/assignments/{assignment_id}/submissions",
            data=data,
        )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        fallback = _submit_file_assignment_via_browser(
            course_id,
            assignment_id,
            path,
            comment,
            e,
        )
        if fallback is not None:
            return fallback
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error submitting file assignment: {e}"

    return (
        "## File Submission Saved\n\n"
        f"- Workflow state: {result.get('workflow_state')}\n"
        f"- Submitted at: {human_datetime(result.get('submitted_at'))}\n"
        f"- Attempt: {result.get('attempt')}\n"
        f"- File ID: {file_id}\n"
        f"- File: `{path}`"
    )


def _submit_file_assignment_via_browser(
    course_id: str,
    assignment_id: str,
    path: Path,
    comment: str | None,
    api_error: CanvasApiError,
) -> str | None:
    """Fallback for Canvas instances that reject browser-session API upload init."""
    storage_state = Path(
        os.environ.get("CANVAS_STORAGE_STATE", ".canvas-storage-state.json")
    ).expanduser()
    if not storage_state.exists():
        return None

    try:
        from playwright.sync_api import sync_playwright

        from canvas_mcp.browser_login import _launch_browser, normalize_base_url
    except ImportError:
        return None

    base_url = normalize_base_url(os.environ.get("CANVAS_BASE_URL"))
    assignment_url = f"{base_url}/courses/{course_id}/assignments/{assignment_id}"
    headless = os.environ.get("CANVAS_SUBMIT_HEADLESS", "true").lower() not in {
        "0",
        "false",
        "no",
    }

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, headless=headless)
            context = browser.new_context(storage_state=str(storage_state))
            page = context.new_page()
            page.goto(assignment_url, wait_until="networkidle", timeout=60000)

            if page.get_by_role("button", name="Start Assignment").count():
                page.get_by_role("button", name="Start Assignment").click(timeout=10000)
            elif page.get_by_role("button", name="New Attempt").count():
                page.get_by_role("button", name="New Attempt").click(timeout=10000)

            page.locator("input[type=file]").first.set_input_files(str(path), timeout=10000)
            page.wait_for_timeout(1000)

            if comment:
                _fill_first_visible_textarea(page, comment)

            page.get_by_role("button", name="Submit Assignment").click(timeout=10000)
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            body = page.locator("body").inner_text(timeout=10000)
            context.storage_state(path=str(storage_state))
            browser.close()
    except Exception as e:
        return (
            f"Canvas API error: {api_error}\n\n"
            f"Browser fallback also failed: {e}"
        )

    if "Submitted!" not in body or path.name not in body:
        return (
            f"Canvas API error: {api_error}\n\n"
            "Browser fallback ran, but the page did not show a clear submitted state. "
            "Check Canvas manually before retrying."
        )

    note = ""
    if comment:
        note = (
            "\n- Comment: browser fallback attempted to include the comment "
            "if Canvas exposed a comment box."
        )
    return (
        "## File Submission Saved\n\n"
        "- Workflow state: submitted\n"
        "- Submitted via: Canvas browser fallback\n"
        f"- File: `{path}`"
        f"{note}"
    )


def _fill_first_visible_textarea(page, value: str) -> bool:
    for textarea in page.locator("textarea").all():
        try:
            if textarea.is_visible(timeout=500):
                textarea.fill(value)
                return True
        except Exception:
            continue
    return False

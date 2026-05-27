"""Submission-related Canvas tools."""

from __future__ import annotations

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
) -> str:
    """Submit an online text entry assignment. Requires confirm_write=True."""
    if not html_body.strip():
        return "Error: html_body is empty."
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
) -> str:
    """Submit an online URL assignment. Requires confirm_write=True."""
    if not url.strip():
        return "Error: url is empty."
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
) -> str:
    """Submit a completed local file to a Canvas online-upload assignment."""
    path = Path(file_path).expanduser()
    if not path.exists() or not path.is_file():
        return f"Error: file_path does not exist or is not a file: {path}"

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

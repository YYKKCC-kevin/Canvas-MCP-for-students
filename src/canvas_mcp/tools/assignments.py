"""Assignment, deadline, and workspace tools."""

from __future__ import annotations

import os
import re
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from canvas_mcp.auth import AuthError, get_client
from canvas_mcp.client import CanvasApiError
from canvas_mcp.formatting import (
    clean_html,
    due_status,
    human_datetime,
    markdown_table,
    parse_canvas_datetime,
)
from canvas_mcp.tools.courses import fetch_courses


ASSIGNMENT_BUCKETS = {
    "all",
    "past",
    "overdue",
    "undated",
    "ungraded",
    "unsubmitted",
    "upcoming",
    "future",
}


DOWNLOAD_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".r",
    ".rmd",
    ".py",
    ".ipynb",
    ".zip",
}

DEFAULT_DOWNLOAD_DIR = "canvas-mcp-downloads"


def _assignment_params(bucket: str = "all") -> list[tuple[str, str]]:
    params = [
        ("include[]", "submission"),
        ("include[]", "all_dates"),
        ("order_by", "due_at"),
        ("per_page", "100"),
    ]
    if bucket != "all":
        params.append(("bucket", bucket))
    return params


def fetch_course_assignments(
    course_id: str,
    bucket: str = "all",
    search_term: str | None = None,
) -> list[dict]:
    client = get_client()
    params = _assignment_params(bucket)
    if search_term:
        params.append(("search_term", search_term))
    return client.get_paginated(f"/courses/{course_id}/assignments", params=params)


def _submitted(submission: dict | None) -> bool:
    if not submission:
        return False
    return bool(submission.get("submitted_at")) or submission.get("workflow_state") in {
        "submitted",
        "graded",
        "pending_review",
    }


def _assignment_status(assignment: dict) -> str:
    submission = assignment.get("submission") or {}
    if submission.get("excused"):
        return "excused"
    if submission.get("missing") or submission.get("late_policy_status") == "missing":
        return "missing"
    if _submitted(submission):
        return submission.get("workflow_state") or "submitted"
    return due_status(assignment.get("due_at"), submission.get("submitted_at"))


def _assignment_row(course_id: str, assignment: dict) -> list[Any]:
    submission = assignment.get("submission") or {}
    submission_types = ", ".join(assignment.get("submission_types") or [])
    return [
        course_id,
        assignment.get("id"),
        assignment.get("name") or "(unnamed)",
        human_datetime(assignment.get("due_at")),
        _assignment_status(assignment),
        submission.get("submitted_at") and human_datetime(submission.get("submitted_at")),
        assignment.get("points_possible"),
        submission_types,
        assignment.get("html_url") or "",
    ]


def list_course_assignments(
    course_id: str,
    bucket: str = "upcoming",
    search_term: str | None = None,
) -> str:
    """List assignments in one Canvas course."""
    if bucket not in ASSIGNMENT_BUCKETS:
        return f"Error: bucket must be one of {', '.join(sorted(ASSIGNMENT_BUCKETS))}."
    try:
        assignments = fetch_course_assignments(course_id, bucket, search_term)
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error listing assignments: {e}"

    rows = [_assignment_row(course_id, assignment) for assignment in assignments]
    headers = [
        "Course",
        "Assignment",
        "Name",
        "Due",
        "Status",
        "Submitted",
        "Pts",
        "Submission Types",
        "URL",
    ]
    return f"## Assignments for Course `{course_id}`\n\n{markdown_table(headers, rows)}"


def get_missing_work(
    days_ahead: int = 14,
    include_overdue: bool = True,
    include_undated: bool = False,
    course_ids: list[str] | None = None,
) -> str:
    """Find unsubmitted Canvas assignments across active courses."""
    if days_ahead < 0:
        return "Error: days_ahead must be non-negative."

    try:
        courses = fetch_courses("active")
        if course_ids:
            wanted = {str(course_id) for course_id in course_ids}
            courses = [course for course in courses if str(course.get("id")) in wanted]

        now = datetime.now(timezone.utc)
        horizon = now + timedelta(days=days_ahead)
        rows = []
        for course in courses:
            course_id = str(course.get("id"))
            course_name = course.get("name") or course.get("course_code") or course_id
            assignments = fetch_course_assignments(course_id, "all")
            for assignment in assignments:
                submission = assignment.get("submission") or {}
                if _submitted(submission) or submission.get("excused"):
                    continue
                if not assignment.get("published", True):
                    continue
                due = parse_canvas_datetime(assignment.get("due_at"))
                if due is None:
                    if not include_undated:
                        continue
                else:
                    due_utc = due.astimezone(timezone.utc)
                    if due_utc < now and not include_overdue:
                        continue
                    if due_utc > horizon:
                        continue

                rows.append(
                    [
                        course_id,
                        course_name,
                        assignment.get("id"),
                        assignment.get("name") or "(unnamed)",
                        human_datetime(assignment.get("due_at")),
                        _assignment_status(assignment),
                        assignment.get("points_possible"),
                        assignment.get("html_url") or "",
                    ]
                )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error finding missing work: {e}"

    def sort_key(row: list[Any]) -> tuple[int, str]:
        return (1 if not row[4] else 0, row[4] or "9999")

    rows.sort(key=sort_key)
    headers = ["Course", "Course Name", "Assignment", "Name", "Due", "Status", "Pts", "URL"]
    return (
        f"## Canvas Work Not Yet Submitted\n\n"
        f"Window: now through {days_ahead} day(s) ahead"
        f"{' plus overdue' if include_overdue else ''}.\n\n"
        f"{markdown_table(headers, rows)}"
    )


def get_todo_items(
    start_date: str | None = None,
    end_date: str | None = None,
    incomplete_only: bool = True,
    course_ids: list[str] | None = None,
) -> str:
    """List Canvas planner/todo items."""
    try:
        client = get_client()
        params: list[tuple[str, str]] = []
        if start_date:
            params.append(("start_date", start_date))
        if end_date:
            params.append(("end_date", end_date))
        if incomplete_only:
            params.append(("filter", "incomplete_items"))
        if course_ids:
            for course_id in course_ids:
                params.append(("context_codes[]", f"course_{course_id}"))
        items = client.get_paginated("/planner/items", params=params)
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error listing todo items: {e}"

    rows = []
    for item in items:
        plannable = item.get("plannable") or {}
        override = item.get("planner_override") or {}
        submission = item.get("submissions")
        title = (
            plannable.get("title")
            or plannable.get("name")
            or item.get("plannable_type")
            or "(untitled)"
        )
        rows.append(
            [
                item.get("course_id") or item.get("context_code") or "",
                item.get("plannable_type"),
                item.get("plannable_id"),
                title,
                human_datetime(
                    item.get("plannable_date")
                    or item.get("todo_date")
                    or plannable.get("due_at")
                ),
                "complete" if override.get("marked_complete") else "incomplete",
                "submitted" if submission else "",
                item.get("html_url") or plannable.get("html_url") or "",
            ]
        )
    headers = ["Course", "Type", "ID", "Title", "Date", "Planner", "Submission", "URL"]
    return f"## Canvas Planner Items\n\n{markdown_table(headers, rows)}"


def _extract_links(html: str | None, base_url: str) -> list[dict[str, str]]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()
    for tag in soup.find_all("a", href=True):
        href = urljoin(base_url + "/", tag["href"])
        if href in seen:
            continue
        seen.add(href)
        links.append({"text": clean_html(tag.get_text(" "), 200) or href, "url": href})
    return links


def get_assignment_details(
    course_id: str,
    assignment_id: str,
    max_description_chars: int = 8000,
) -> str:
    """Fetch a single assignment, including instructions and submission status."""
    try:
        client = get_client()
        params = [("include[]", "submission"), ("include[]", "all_dates")]
        assignment = client.get(
            f"/courses/{course_id}/assignments/{assignment_id}", params=params
        )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error fetching assignment details: {e}"

    submission = assignment.get("submission") or {}
    links = _extract_links(assignment.get("description"), client.base_url)
    lines = [
        f"# {assignment.get('name') or 'Canvas Assignment'}",
        "",
        f"- Course ID: `{course_id}`",
        f"- Assignment ID: `{assignment_id}`",
        f"- Due: {human_datetime(assignment.get('due_at')) or '(none)'}",
        f"- Unlock: {human_datetime(assignment.get('unlock_at')) or '(none)'}",
        f"- Lock: {human_datetime(assignment.get('lock_at')) or '(none)'}",
        f"- Points: {assignment.get('points_possible')}",
        f"- Submission types: {', '.join(assignment.get('submission_types') or [])}",
        f"- Status: {_assignment_status(assignment)}",
        f"- Submitted at: {human_datetime(submission.get('submitted_at')) or '(not submitted)'}",
        f"- URL: {assignment.get('html_url') or ''}",
        "",
        "## Instructions",
        "",
        clean_html(assignment.get("description"), max_description_chars) or "(No description.)",
    ]
    if links:
        lines.extend(["", "## Links"])
        for link in links:
            lines.append(f"- [{link['text']}]({link['url']})")
    return "\n".join(lines)


def _slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    return text.strip("-")[:80] or "assignment"


def _filename_from_response(url: str, response_headers: dict[str, str]) -> str:
    disposition = response_headers.get("Content-Disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
    if match:
        return _slug(unquote(match.group(1)))
    path_name = os.path.basename(urlparse(url).path)
    return _slug(unquote(path_name or "download"))


def _canvas_attachment_download_url(response) -> str | None:
    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        return None
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return None
    attachment = payload.get("attachment") if isinstance(payload, dict) else None
    if not isinstance(attachment, dict):
        return None
    url = attachment.get("url")
    return url if isinstance(url, str) and url else None


def _assignment_resource_mismatch(
    assignment_name: str | None,
    resource_name: str | None,
) -> str | None:
    assignment_number = _named_number(assignment_name)
    resource_number = _named_number(resource_name)
    if assignment_number is None or resource_number is None:
        return None
    if assignment_number == resource_number:
        return None
    return (
        f"Assignment name `{assignment_name}` appears to be number {assignment_number}, "
        f"but linked file/resource `{resource_name}` appears to be number {resource_number}."
    )


def _named_number(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(
        r"\b(?:assignment|homework|hw)\s*[-_#:]?\s*(\d+)\b",
        text,
        flags=re.I,
    )
    return match.group(1) if match else None


def _downloadable_link(url: str) -> bool:
    path = urlparse(url).path.lower()
    if "/files/" in path:
        return True
    return Path(path).suffix in DOWNLOAD_EXTENSIONS


def prepare_assignment_workspace(
    course_id: str,
    assignment_id: str,
    output_dir: str | None = None,
    download_linked_files: bool = True,
    max_files: int = 10,
    allow_mismatched_files: bool = False,
) -> str:
    """Create a local folder with assignment instructions and linked files."""
    try:
        client = get_client()
        params = [("include[]", "submission"), ("include[]", "all_dates")]
        assignment = client.get(
            f"/courses/{course_id}/assignments/{assignment_id}", params=params
        )
        base_dir = Path(
            output_dir
            or os.environ.get("CANVAS_DOWNLOAD_DIR", DEFAULT_DOWNLOAD_DIR)
        ).expanduser()
        work_dir = base_dir / f"course_{course_id}" / (
            f"assignment_{assignment_id}_{_slug(assignment.get('name') or 'assignment')}"
        )
        work_dir.mkdir(parents=True, exist_ok=True)

        details = get_assignment_details(course_id, assignment_id, max_description_chars=50000)
        (work_dir / "assignment.md").write_text(details + "\n", encoding="utf-8")

        links = _extract_links(assignment.get("description"), client.base_url)
        downloaded: list[str] = []
        skipped: list[str] = []
        mismatches: list[str] = []
        existing_untrusted: list[str] = []
        if download_linked_files:
            files_dir = work_dir / "files"
            files_dir.mkdir(exist_ok=True)
            for link in links:
                if len(downloaded) >= max_files:
                    break
                url = link["url"]
                mismatch = _assignment_resource_mismatch(
                    assignment.get("name"),
                    link.get("text"),
                )
                if mismatch and not allow_mismatched_files:
                    mismatches.append(mismatch)
                    skipped.append(url)
                    continue
                if not _downloadable_link(url):
                    skipped.append(url)
                    continue
                try:
                    response = client.download(url)
                    attachment_url = _canvas_attachment_download_url(response)
                    if attachment_url:
                        url = attachment_url
                        response = client.download(attachment_url)
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" in content_type and "/files/" not in urlparse(url).path:
                        skipped.append(url)
                        continue
                    filename = _filename_from_response(url, response.headers)
                    mismatch = _assignment_resource_mismatch(
                        assignment.get("name"),
                        filename,
                    )
                    if mismatch and not allow_mismatched_files:
                        mismatches.append(mismatch)
                        skipped.append(url)
                        continue
                    out_path = files_dir / filename
                    with out_path.open("wb") as fh:
                        for chunk in response.iter_content(chunk_size=1024 * 256):
                            if chunk:
                                fh.write(chunk)
                    downloaded.append(str(out_path))
                except Exception as e:
                    skipped.append(f"{url} ({e})")
            if mismatches:
                downloaded_set = {str(Path(path)) for path in downloaded}
                existing_untrusted = [
                    str(path)
                    for path in sorted(files_dir.iterdir())
                    if path.is_file() and str(path) not in downloaded_set
                ]
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error preparing assignment workspace: {e}"

    lines = [
        "## Assignment Workspace Prepared",
        "",
        f"- Folder: `{work_dir}`",
        f"- Instructions: `{work_dir / 'assignment.md'}`",
        f"- Downloaded files: {len(downloaded)}",
    ]
    for path in downloaded:
        lines.append(f"- `{path}`")
    if mismatches:
        warning_path = work_dir / "MISMATCH_WARNING.md"
        warning_path.write_text(
            "# Potential Assignment/File Mismatch\n\n"
            "The Canvas assignment title and linked file names appear to refer to "
            "different assignment numbers. Downloads were skipped by default to avoid "
            "working on or submitting the wrong assignment.\n\n"
            + "\n".join(f"- {item}" for item in mismatches)
            + "\n",
            encoding="utf-8",
        )
        lines.append("")
        lines.append("### Potential Assignment/File Mismatches")
        lines.append(
            "Downloads were skipped because the assignment number and file number disagree. "
            "Verify the Canvas page or set `allow_mismatched_files=True` only if this is intentional."
        )
        lines.append(f"- Warning file: `{warning_path}`")
        for item in mismatches[:20]:
            lines.append(f"- {item}")
    if existing_untrusted:
        lines.append("")
        lines.append("### Existing Files Not Trusted")
        lines.append(
            "This workspace already contains files from an earlier run. They were not "
            "downloaded in this run and should not be used for this assignment unless "
            "you manually verify them."
        )
        for path in existing_untrusted[:20]:
            lines.append(f"- `{path}`")
    if skipped:
        lines.append("")
        lines.append("### Links Not Downloaded")
        for item in skipped[:20]:
            lines.append(f"- {item}")
    return "\n".join(lines)

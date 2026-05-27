"""Course content, announcement, discussion, and exam-info tools."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from canvas_mcp.auth import AuthError, get_client
from canvas_mcp.client import CanvasApiError
from canvas_mcp.formatting import (
    clean_html,
    human_datetime,
    markdown_table,
    parse_canvas_datetime,
)
from canvas_mcp.tools.assignments import _assignment_status, fetch_course_assignments
from canvas_mcp.tools.courses import fetch_courses


EXAM_KEYWORDS_RE = re.compile(r"\b(exam|midterm|final|quiz|test)\b", re.I)


def _active_course_scope(course_id: str | None = None) -> list[tuple[str, str]]:
    if course_id:
        cid = str(course_id)
        try:
            for course in fetch_courses("active"):
                if str(course.get("id")) == cid:
                    return [(cid, course.get("name") or course.get("course_code") or cid)]
        except Exception:
            pass
        return [(cid, cid)]
    courses = fetch_courses("active")
    scoped = []
    for course in courses:
        if course.get("access_restricted_by_date"):
            continue
        cid = str(course.get("id"))
        name = course.get("name") or course.get("course_code") or cid
        scoped.append((cid, name))
    return scoped


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def list_course_announcements(
    course_id: str | None = None,
    days_back: int = 30,
    max_items: int = 25,
) -> str:
    """List recent Canvas announcements for one course or all active courses."""
    if days_back < 0:
        return "Error: days_back must be non-negative."
    if max_items <= 0:
        return "Error: max_items must be positive."

    try:
        client = get_client()
        courses = _active_course_scope(course_id)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days_back)
        rows: list[list[Any]] = []
        for cid, course_name in courses:
            announcements = client.get_paginated(
                "/announcements",
                params=[
                    ("context_codes[]", f"course_{cid}"),
                    ("start_date", _iso_utc(start)),
                    ("end_date", _iso_utc(end)),
                    ("active_only", "true"),
                    ("per_page", "50"),
                ],
            )
            for announcement in announcements:
                author = announcement.get("author") or {}
                rows.append(
                    [
                        cid,
                        course_name,
                        announcement.get("title") or "(untitled)",
                        human_datetime(
                            announcement.get("posted_at") or announcement.get("created_at")
                        ),
                        author.get("display_name") or "",
                        clean_html(announcement.get("message"), 280),
                        announcement.get("html_url") or "",
                    ]
                )
                if len(rows) >= max_items:
                    break
            if len(rows) >= max_items:
                break
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error listing announcements: {e}"

    headers = ["Course", "Course Name", "Title", "Posted", "Author", "Preview", "URL"]
    scope = f"course `{course_id}`" if course_id else "active courses"
    return (
        "## Canvas Course Announcements\n\n"
        f"Scope: {scope}. Window: last {days_back} day(s).\n\n"
        f"{markdown_table(headers, rows)}"
    )


def list_exam_items(
    course_id: str | None = None,
    include_past: bool = True,
    days_ahead: int = 120,
    max_items: int = 100,
) -> str:
    """List exam-, quiz-, test-, midterm-, and final-like Canvas assignments."""
    if days_ahead < 0:
        return "Error: days_ahead must be non-negative."
    if max_items <= 0:
        return "Error: max_items must be positive."

    try:
        courses = _active_course_scope(course_id)
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(days=days_ahead)
        rows: list[list[Any]] = []
        for cid, course_name in courses:
            assignments = fetch_course_assignments(cid, "all")
            for assignment in assignments:
                name = assignment.get("name") or ""
                if not EXAM_KEYWORDS_RE.search(name):
                    continue
                due = parse_canvas_datetime(assignment.get("due_at"))
                if due is not None:
                    due_utc = due.astimezone(timezone.utc)
                    if not include_past and due_utc < now:
                        continue
                    if due_utc > horizon:
                        continue
                rows.append(
                    [
                        cid,
                        course_name,
                        assignment.get("id"),
                        _exam_kind(name),
                        name,
                        human_datetime(assignment.get("due_at")) or "(none)",
                        _assignment_status(assignment),
                        assignment.get("points_possible"),
                        ", ".join(assignment.get("submission_types") or []),
                        assignment.get("html_url") or "",
                    ]
                )
                if len(rows) >= max_items:
                    break
            if len(rows) >= max_items:
                break
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error listing exam items: {e}"

    headers = [
        "Course",
        "Course Name",
        "ID",
        "Kind",
        "Name",
        "Due",
        "Status",
        "Pts",
        "Submission Types",
        "URL",
    ]
    scope = f"course `{course_id}`" if course_id else "active courses"
    return (
        "## Canvas Exam / Quiz / Test Items\n\n"
        f"Scope: {scope}. Window: {'all visible dates' if include_past else f'next {days_ahead} day(s)'}.\n\n"
        f"{markdown_table(headers, rows)}"
    )


def _exam_kind(name: str) -> str:
    lower = name.lower()
    if "midterm" in lower:
        return "midterm"
    if "final" in lower:
        return "final"
    if "exam" in lower:
        return "exam"
    if "quiz" in lower:
        return "quiz"
    if "test" in lower:
        return "test"
    return "assessment"


def list_course_discussions(
    course_id: str,
    include_announcements: bool = False,
    search_term: str | None = None,
    max_items: int = 25,
) -> str:
    """List discussion topics for a Canvas course."""
    if max_items <= 0:
        return "Error: max_items must be positive."

    try:
        client = get_client()
        params: list[tuple[str, str]] = [
            ("only_announcements", "false"),
            ("order_by", "recent_activity"),
            ("per_page", "50"),
        ]
        if search_term:
            params.append(("search_term", search_term))
        topics = client.get_paginated(
            f"/courses/{course_id}/discussion_topics",
            params=params,
        )
        rows: list[list[Any]] = []
        for topic in topics:
            if topic.get("is_announcement") and not include_announcements:
                continue
            author = topic.get("author") or {}
            rows.append(
                [
                    topic.get("id"),
                    "announcement" if topic.get("is_announcement") else "discussion",
                    topic.get("title") or "(untitled)",
                    human_datetime(topic.get("posted_at") or topic.get("created_at")),
                    human_datetime(topic.get("last_reply_at")),
                    author.get("display_name") or "",
                    "locked" if topic.get("locked") else "open",
                    clean_html(topic.get("message"), 240),
                    topic.get("html_url") or "",
                ]
            )
            if len(rows) >= max_items:
                break
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error listing discussions: {e}"

    headers = [
        "ID",
        "Type",
        "Title",
        "Posted",
        "Last Reply",
        "Author",
        "State",
        "Preview",
        "URL",
    ]
    return (
        f"## Canvas Course Discussions for `{course_id}`\n\n"
        f"{markdown_table(headers, rows)}"
    )


def get_course_info(course_id: str, max_syllabus_chars: int = 3000) -> str:
    """Fetch Canvas course metadata and syllabus/class information."""
    try:
        client = get_client()
        course = client.get(
            f"/courses/{course_id}",
            params=[
                ("include[]", "term"),
                ("include[]", "teachers"),
                ("include[]", "sections"),
                ("include[]", "syllabus_body"),
            ],
        )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error fetching course info: {e}"

    term = course.get("term") or {}
    teachers = course.get("teachers") or []
    sections = course.get("sections") or []
    syllabus = clean_html(course.get("syllabus_body"), max_syllabus_chars)
    lines = [
        f"# {course.get('name') or course.get('course_code') or f'Course {course_id}'}",
        "",
        f"- Course ID: `{course_id}`",
        f"- Code: {course.get('course_code') or ''}",
        f"- Term: {term.get('name') or ''}",
        f"- State: {course.get('workflow_state') or ''}",
        f"- Time zone: {course.get('time_zone') or ''}",
        f"- Teachers: {', '.join(t.get('display_name', '') for t in teachers) or '(none listed)'}",
        f"- Sections: {', '.join(s.get('name', '') for s in sections) or '(none listed)'}",
        f"- URL: {course.get('html_url') or ''}",
        "",
        "## Syllabus / Class Information",
        "",
        syllabus or "(No syllabus body exposed by Canvas.)",
    ]
    return "\n".join(lines).rstrip() + "\n"


def list_course_modules(
    course_id: str,
    search_term: str | None = None,
    max_items: int = 100,
) -> str:
    """List Canvas modules and module items for class/session materials."""
    if max_items <= 0:
        return "Error: max_items must be positive."

    try:
        client = get_client()
        modules = client.get_paginated(
            f"/courses/{course_id}/modules",
            params=[("include[]", "items"), ("per_page", "50")],
        )
        rows: list[list[Any]] = []
        query = search_term.lower() if search_term else None
        for module in modules:
            module_name = module.get("name") or "(untitled module)"
            items = module.get("items") or []
            if not items:
                if query and query not in module_name.lower():
                    continue
                rows.append(
                    [
                        module_name,
                        "",
                        "",
                        _published(module),
                        _completion_requirement(module),
                        module.get("html_url") or "",
                    ]
                )
                continue
            for item in items:
                title = item.get("title") or "(untitled item)"
                haystack = f"{module_name}\n{title}\n{item.get('type') or ''}".lower()
                if query and query not in haystack:
                    continue
                rows.append(
                    [
                        module_name,
                        title,
                        item.get("type") or "",
                        _published(item),
                        _completion_requirement(item),
                        item.get("html_url") or item.get("external_url") or "",
                    ]
                )
                if len(rows) >= max_items:
                    break
            if len(rows) >= max_items:
                break
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error listing course modules: {e}"

    headers = ["Module", "Item", "Type", "Published", "Requirement", "URL"]
    return (
        f"## Canvas Course Modules for `{course_id}`\n\n"
        f"{markdown_table(headers, rows)}"
    )


def _published(item: dict) -> str:
    value = item.get("published")
    if value is True:
        return "published"
    if value is False:
        return "unpublished"
    return ""


def _completion_requirement(item: dict) -> str:
    requirement = item.get("completion_requirement") or {}
    if not requirement:
        return ""
    req_type = requirement.get("type") or ""
    minimum_score = requirement.get("min_score")
    if minimum_score is not None:
        return f"{req_type} >= {minimum_score}"
    return req_type

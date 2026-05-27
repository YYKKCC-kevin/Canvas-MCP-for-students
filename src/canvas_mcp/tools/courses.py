"""Course-related Canvas tools."""

from __future__ import annotations

from canvas_mcp.auth import AuthError, get_client
from canvas_mcp.client import CanvasApiError
from canvas_mcp.formatting import markdown_table


def _role_summary(course: dict) -> str:
    enrollments = course.get("enrollments") or []
    roles = []
    for enrollment in enrollments:
        role = enrollment.get("type") or enrollment.get("role")
        if role and role not in roles:
            roles.append(role)
    return ", ".join(roles)


def _score_summary(course: dict) -> str:
    enrollments = course.get("enrollments") or []
    scores = []
    for enrollment in enrollments:
        score = enrollment.get("computed_current_score")
        grade = enrollment.get("computed_current_grade")
        if score is not None or grade:
            scores.append(f"{score if score is not None else '?'} ({grade or 'no grade'})")
    return ", ".join(scores)


def fetch_courses(
    enrollment_state: str = "active",
    include_scores: bool = False,
    include_completed: bool = False,
) -> list[dict]:
    client = get_client()
    params: list[tuple[str, str]] = [
        ("include[]", "term"),
        ("include[]", "teachers"),
        ("include[]", "favorites"),
    ]
    if include_scores:
        params.append(("include[]", "total_scores"))
    if enrollment_state != "all":
        params.append(("enrollment_state", enrollment_state))
    if include_completed:
        params.extend([("state[]", "available"), ("state[]", "completed")])
    return client.get_paginated("/courses", params=params)


def list_courses(
    enrollment_state: str = "active",
    include_scores: bool = False,
    include_completed: bool = False,
) -> str:
    """List Canvas courses visible to the authenticated user."""
    if enrollment_state not in {"active", "completed", "invited_or_pending", "all"}:
        return "Error: enrollment_state must be active, completed, invited_or_pending, or all."

    try:
        courses = fetch_courses(enrollment_state, include_scores, include_completed)
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error listing courses: {e}"

    rows = []
    for course in courses:
        if course.get("access_restricted_by_date"):
            continue
        term = course.get("term") or {}
        teachers = course.get("teachers") or []
        rows.append(
            [
                course.get("id"),
                course.get("name") or course.get("course_code") or "(unnamed)",
                course.get("course_code") or "",
                term.get("name") or "",
                _role_summary(course),
                ", ".join(t.get("display_name", "") for t in teachers[:3]),
                _score_summary(course) if include_scores else "",
            ]
        )

    headers = ["ID", "Course", "Code", "Term", "Role", "Teachers", "Score"]
    return f"## Canvas Courses\n\n{markdown_table(headers, rows)}"

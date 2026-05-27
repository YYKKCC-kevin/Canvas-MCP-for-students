"""Canvas MCP server definition."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from canvas_mcp.tools.assignments import (
    get_assignment_details,
    get_missing_work,
    get_todo_items,
    list_course_assignments,
    prepare_assignment_workspace,
)
from canvas_mcp.tools.courses import list_courses
from canvas_mcp.tools.submissions import (
    get_my_submission,
    submit_text_assignment,
    submit_url_assignment,
)


mcp = FastMCP("Canvas MCP Server")


@mcp.tool()
def tool_list_courses(
    enrollment_state: str = "active",
    include_scores: bool = False,
    include_completed: bool = False,
) -> str:
    """List Canvas courses for the authenticated user.

    Args:
        enrollment_state: active, completed, invited_or_pending, or all.
        include_scores: Include current score/grade if Canvas exposes it.
        include_completed: Include completed courses in addition to available courses.
    """
    return list_courses(enrollment_state, include_scores, include_completed)


@mcp.tool()
def tool_list_course_assignments(
    course_id: str,
    bucket: str = "upcoming",
    search_term: str | None = None,
) -> str:
    """List assignments for a course.

    Args:
        course_id: Canvas course ID.
        bucket: all, past, overdue, undated, ungraded, unsubmitted, upcoming, or future.
        search_term: Optional title search.
    """
    return list_course_assignments(course_id, bucket, search_term)


@mcp.tool()
def tool_get_missing_work(
    days_ahead: int = 14,
    include_overdue: bool = True,
    include_undated: bool = False,
    course_ids: list[str] | None = None,
) -> str:
    """Find unsubmitted Canvas assignments across active courses.

    Args:
        days_ahead: Include assignments due within this many days.
        include_overdue: Include unsubmitted assignments whose due date has passed.
        include_undated: Include unsubmitted assignments with no due date.
        course_ids: Optional course ID filter.
    """
    return get_missing_work(days_ahead, include_overdue, include_undated, course_ids)


@mcp.tool()
def tool_get_todo_items(
    start_date: str | None = None,
    end_date: str | None = None,
    incomplete_only: bool = True,
    course_ids: list[str] | None = None,
) -> str:
    """List Canvas planner/todo items.

    Dates may be YYYY-MM-DD or ISO 8601 strings.
    """
    return get_todo_items(start_date, end_date, incomplete_only, course_ids)


@mcp.tool()
def tool_get_assignment_details(
    course_id: str,
    assignment_id: str,
    max_description_chars: int = 8000,
) -> str:
    """Fetch a Canvas assignment's due date, submission state, instructions, and links."""
    return get_assignment_details(course_id, assignment_id, max_description_chars)


@mcp.tool()
def tool_prepare_assignment_workspace(
    course_id: str,
    assignment_id: str,
    output_dir: str | None = None,
    download_linked_files: bool = True,
    max_files: int = 10,
) -> str:
    """Create a local folder with assignment.md and best-effort linked file downloads."""
    return prepare_assignment_workspace(
        course_id, assignment_id, output_dir, download_linked_files, max_files
    )


@mcp.tool()
def tool_get_my_submission(course_id: str, assignment_id: str) -> str:
    """Get the authenticated user's current submission state for an assignment."""
    return get_my_submission(course_id, assignment_id)


@mcp.tool()
def tool_submit_text_assignment(
    course_id: str,
    assignment_id: str,
    html_body: str,
    comment: str | None = None,
    confirm_write: bool = False,
) -> str:
    """Submit an online text entry assignment. Requires confirm_write=True."""
    return submit_text_assignment(course_id, assignment_id, html_body, comment, confirm_write)


@mcp.tool()
def tool_submit_url_assignment(
    course_id: str,
    assignment_id: str,
    url: str,
    comment: str | None = None,
    confirm_write: bool = False,
) -> str:
    """Submit an online URL assignment. Requires confirm_write=True."""
    return submit_url_assignment(course_id, assignment_id, url, comment, confirm_write)

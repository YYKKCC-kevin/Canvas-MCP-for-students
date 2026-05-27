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
from canvas_mcp.tools.gradescope_bridge import (
    gradescope_bridge_status,
    gradescope_get_assignment_details,
    gradescope_list_assignments,
    gradescope_list_courses,
)
from canvas_mcp.tools.learning import (
    check_my_draft,
    create_homework_template,
    extract_due_and_submission_target,
    generate_hint_pack,
    make_practice_version,
    prepare_homework_help_pack,
)
from canvas_mcp.tools.sources import resolve_assignment_source
from canvas_mcp.tools.submissions import (
    get_my_submission,
    submit_file_assignment,
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
def tool_resolve_assignment_source(
    course_id: str,
    assignment_id: str,
    user_source_url: str | None = None,
    user_source_kind: str | None = None,
) -> str:
    """Decide whether the assignment source is Canvas, GitHub, Gradescope, or user-provided.

    Args:
        course_id: Canvas course ID.
        assignment_id: Canvas assignment ID.
        user_source_url: Optional URL/path supplied by the user after clarification.
        user_source_kind: Optional hint such as github, gradescope, or local_file.
    """
    return resolve_assignment_source(
        course_id,
        assignment_id,
        user_source_url,
        user_source_kind,
    )


@mcp.tool()
def tool_prepare_assignment_workspace(
    course_id: str,
    assignment_id: str,
    output_dir: str | None = None,
    download_linked_files: bool = True,
    max_files: int = 10,
    allow_mismatched_files: bool = False,
) -> str:
    """Create a local folder with assignment.md and best-effort linked file downloads."""
    return prepare_assignment_workspace(
        course_id,
        assignment_id,
        output_dir,
        download_linked_files,
        max_files,
        allow_mismatched_files,
    )


@mcp.tool()
def tool_prepare_homework_help_pack(
    course_id: str,
    assignment_id: str,
    output_dir: str | None = None,
    allow_mismatched_files: bool = False,
) -> str:
    """Create template, hints, practice prompt, and submission-target files.

    This tool intentionally does not generate submit-ready homework answers.
    """
    return prepare_homework_help_pack(
        course_id, assignment_id, output_dir, allow_mismatched_files
    )


@mcp.tool()
def tool_create_homework_template(
    assignment_title: str,
    assignment_text: str | None = None,
    output_path: str | None = None,
) -> str:
    """Create a fill-in homework template without solving the assignment."""
    return create_homework_template(assignment_title, assignment_text, output_path)


@mcp.tool()
def tool_generate_hint_pack(
    assignment_title: str,
    assignment_text: str,
    output_path: str | None = None,
) -> str:
    """Generate conceptual hints and checklists, not final answers."""
    return generate_hint_pack(assignment_title, assignment_text, output_path)


@mcp.tool()
def tool_check_my_draft(
    assignment_title: str,
    assignment_text: str,
    draft_text: str | None = None,
    draft_path: str | None = None,
    output_path: str | None = None,
) -> str:
    """Check a student-authored draft for structure and common missing pieces."""
    if draft_path:
        from pathlib import Path

        draft_text = Path(draft_path).expanduser().read_text(encoding="utf-8")
    return check_my_draft(assignment_title, assignment_text, draft_text or "", output_path)


@mcp.tool()
def tool_make_practice_version(
    assignment_title: str,
    assignment_text: str,
    output_path: str | None = None,
) -> str:
    """Create a similar-but-not-identical practice version for studying."""
    return make_practice_version(assignment_title, assignment_text, output_path)


@mcp.tool()
def tool_extract_due_and_submission_target(assignment_details: str) -> str:
    """Extract the due date and whether submission is on Canvas, Gradescope, or unknown."""
    return extract_due_and_submission_target(assignment_details)


@mcp.tool()
def tool_gradescope_bridge_status(
    gradescope_mcp_path: str | None = None,
    check_login: bool = False,
) -> str:
    """Check optional local gradescope-mcp integration and credentials."""
    return gradescope_bridge_status(gradescope_mcp_path, check_login)


@mcp.tool()
def tool_gradescope_list_courses(gradescope_mcp_path: str | None = None) -> str:
    """List Gradescope courses through a local gradescope-mcp installation."""
    return gradescope_list_courses(gradescope_mcp_path)


@mcp.tool()
def tool_gradescope_list_assignments(
    course_id: str,
    gradescope_mcp_path: str | None = None,
) -> str:
    """List Gradescope assignments through a local gradescope-mcp installation."""
    return gradescope_list_assignments(course_id, gradescope_mcp_path)


@mcp.tool()
def tool_gradescope_get_assignment_details(
    course_id: str,
    assignment_id: str,
    gradescope_mcp_path: str | None = None,
) -> str:
    """Get Gradescope assignment details through a local gradescope-mcp installation."""
    return gradescope_get_assignment_details(course_id, assignment_id, gradescope_mcp_path)


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


@mcp.tool()
def tool_submit_file_assignment(
    course_id: str,
    assignment_id: str,
    file_path: str,
    comment: str | None = None,
    confirm_write: bool = False,
) -> str:
    """Submit a completed local file to a Canvas online-upload assignment.

    This is for student-authored finished work and requires confirm_write=True.
    """
    return submit_file_assignment(course_id, assignment_id, file_path, comment, confirm_write)

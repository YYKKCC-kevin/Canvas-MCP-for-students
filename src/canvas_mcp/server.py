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
from canvas_mcp.tools.course_content import (
    get_course_info,
    list_course_announcements,
    list_course_discussions,
    list_course_modules,
    list_exam_items,
)
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
    prepare_multi_agent_review_packet,
    prepare_solution_review_artifact,
    prepare_homework_help_pack,
    review_submission_file,
    review_solution_for_chat,
    review_solution_correctness,
)
from canvas_mcp.tools.sources import resolve_assignment_source
from canvas_mcp.tools.submissions import (
    get_my_submission,
    submit_file_assignment,
    submit_text_assignment,
    submit_url_assignment,
)


MCP_INSTRUCTIONS = """
Canvas MCP helps students inspect Canvas coursework, prepare assignments,
review finished work, and submit only after explicit confirmation.

For homework or coursework completion requests, first confirm two things with
the user before doing final-answer work or submitting:
1. the course/instructor allows the student to use AI tools for this assignment;
2. the user wants AI assistance to complete, review, and/or submit the work.

If the user confirms AI assistance is allowed and asks for completion or
submission, help them complete the assignment, check the work, upload it, and
submit it when the relevant submission tool has explicit write confirmation.
Do not respond with a blanket refusal such as "I cannot help you complete this"
after the user has confirmed the work is AI-permitted. Instead, use the Canvas
tools to gather the prompt/source, create or inspect the workspace, run
correctness/format checks, and submit only after confirmation.

If AI permission is unknown, ask for confirmation and provide learning,
debugging, or review support while waiting. If the request is for an active exam,
proctored assessment, hidden-answer quiz, or misconduct, do not complete or
submit it; redirect to allowed learning or review help.
""".strip()


mcp = FastMCP("Canvas MCP Server", instructions=MCP_INSTRUCTIONS)


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
def tool_list_course_announcements(
    course_id: str | None = None,
    days_back: int = 30,
    max_items: int = 25,
) -> str:
    """List recent Canvas announcements for one course or all active courses.

    Args:
        course_id: Optional Canvas course ID. If omitted, searches active courses.
        days_back: How many days of announcements to include.
        max_items: Maximum announcements returned across the selected scope.
    """
    return list_course_announcements(course_id, days_back, max_items)


@mcp.tool()
def tool_list_exam_items(
    course_id: str | None = None,
    include_past: bool = True,
    days_ahead: int = 120,
    max_items: int = 100,
) -> str:
    """List exam-, quiz-, test-, midterm-, and final-like Canvas items.

    Args:
        course_id: Optional Canvas course ID. If omitted, searches active courses.
        include_past: Include past/graded exam-like items in addition to upcoming ones.
        days_ahead: Future date window when include_past is False.
        max_items: Maximum rows returned.
    """
    return list_exam_items(course_id, include_past, days_ahead, max_items)


@mcp.tool()
def tool_list_course_discussions(
    course_id: str,
    include_announcements: bool = False,
    search_term: str | None = None,
    max_items: int = 25,
) -> str:
    """List discussion topics for a Canvas course.

    Args:
        course_id: Canvas course ID.
        include_announcements: Include announcement-style discussion topics.
        search_term: Optional Canvas discussion search term.
        max_items: Maximum rows returned.
    """
    return list_course_discussions(
        course_id,
        include_announcements,
        search_term,
        max_items,
    )


@mcp.tool()
def tool_get_course_info(course_id: str, max_syllabus_chars: int = 3000) -> str:
    """Fetch course metadata plus syllabus/class information exposed by Canvas."""
    return get_course_info(course_id, max_syllabus_chars)


@mcp.tool()
def tool_list_course_modules(
    course_id: str,
    search_term: str | None = None,
    max_items: int = 100,
) -> str:
    """List Canvas modules and module items such as lecture/class materials."""
    return list_course_modules(course_id, search_term, max_items)


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
    """Create template, support, practice, and submission-target files."""
    return prepare_homework_help_pack(
        course_id, assignment_id, output_dir, allow_mismatched_files
    )


@mcp.tool()
def tool_create_homework_template(
    assignment_title: str,
    assignment_text: str | None = None,
    output_path: str | None = None,
) -> str:
    """Create a structured homework workspace for student drafting."""
    return create_homework_template(assignment_title, assignment_text, output_path)


@mcp.tool()
def tool_generate_hint_pack(
    assignment_title: str,
    assignment_text: str,
    output_path: str | None = None,
) -> str:
    """Generate a homework support pack with concepts, steps, and checks."""
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
def tool_review_submission_file(
    assignment_title: str,
    submission_path: str,
    assignment_text: str | None = None,
    assignment_path: str | None = None,
    output_path: str | None = None,
) -> str:
    """Review a finished file for readability and coverage before submission.

    This is a structural/readiness review, not a full correctness proof.
    """
    return review_submission_file(
        assignment_title,
        submission_path,
        assignment_text,
        assignment_path,
        output_path,
    )


@mcp.tool()
def tool_review_solution_correctness(
    assignment_title: str,
    solution_path: str | None = None,
    solution_text: str | None = None,
    assignment_text: str | None = None,
    assignment_path: str | None = None,
    reference_text: str | None = None,
    reference_path: str | None = None,
    rubric_text: str | None = None,
    output_path: str | None = None,
) -> str:
    """Review a solution for likely correctness issues.

    For stronger checks, provide a reference answer or rubric. Without one,
    the review is low-confidence and based on internal consistency signals.
    """
    return review_solution_correctness(
        assignment_title,
        solution_path,
        solution_text,
        assignment_text,
        assignment_path,
        reference_text,
        reference_path,
        rubric_text,
        output_path,
    )


@mcp.tool()
def tool_prepare_solution_review_artifact(
    assignment_title: str,
    solution_path: str | None = None,
    solution_text: str | None = None,
    assignment_text: str | None = None,
    assignment_path: str | None = None,
    reference_text: str | None = None,
    reference_path: str | None = None,
    rubric_text: str | None = None,
    output_dir: str | None = None,
) -> str:
    """Prepare a Gradescope-style artifact for agent correctness review.

    This is the preferred no-reference workflow: the MCP gathers the prompt,
    student answer, optional rubric/reference, and review instructions; then
    the agent reads the artifact and reasons through correctness.
    """
    return prepare_solution_review_artifact(
        assignment_title,
        solution_path,
        solution_text,
        assignment_text,
        assignment_path,
        reference_text,
        reference_path,
        rubric_text,
        output_dir,
    )


@mcp.tool()
def tool_review_solution_for_chat(
    assignment_title: str,
    solution_path: str | None = None,
    solution_text: str | None = None,
    assignment_text: str | None = None,
    assignment_path: str | None = None,
    reference_text: str | None = None,
    reference_path: str | None = None,
    rubric_text: str | None = None,
    output_dir: str | None = None,
) -> str:
    """Prepare an artifact and return chat-ready correctness review guidance.

    Use this when the user expects the assistant to tell them what is wrong
    or needs revision directly in the conversation.
    """
    return review_solution_for_chat(
        assignment_title,
        solution_path,
        solution_text,
        assignment_text,
        assignment_path,
        reference_text,
        reference_path,
        rubric_text,
        output_dir,
    )


@mcp.tool()
def tool_prepare_multi_agent_review_packet(
    assignment_title: str,
    solution_path: str | None = None,
    solution_text: str | None = None,
    assignment_text: str | None = None,
    assignment_path: str | None = None,
    reference_text: str | None = None,
    reference_path: str | None = None,
    rubric_text: str | None = None,
    output_dir: str | None = None,
) -> str:
    """Prepare solver/reviewer/disagreement packets for multi-agent review.

    The MCP gathers context and writes a packet. The calling Codex/Claude host
    should run the solver and reviewer agents, then report consensus in chat.
    """
    return prepare_multi_agent_review_packet(
        assignment_title,
        solution_path,
        solution_text,
        assignment_text,
        assignment_path,
        reference_text,
        reference_path,
        rubric_text,
        output_dir,
    )


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
    confirm_comment: bool = False,
) -> str:
    """Submit an online text entry assignment.

    Requires confirm_write=True. If comment is set, also requires
    confirm_comment=True so agents cannot add Canvas comments unless requested.
    """
    return submit_text_assignment(
        course_id,
        assignment_id,
        html_body,
        comment,
        confirm_write,
        confirm_comment,
    )


@mcp.tool()
def tool_submit_url_assignment(
    course_id: str,
    assignment_id: str,
    url: str,
    comment: str | None = None,
    confirm_write: bool = False,
    confirm_comment: bool = False,
) -> str:
    """Submit an online URL assignment.

    Requires confirm_write=True. If comment is set, also requires
    confirm_comment=True so agents cannot add Canvas comments unless requested.
    """
    return submit_url_assignment(
        course_id,
        assignment_id,
        url,
        comment,
        confirm_write,
        confirm_comment,
    )


@mcp.tool()
def tool_submit_file_assignment(
    course_id: str,
    assignment_id: str,
    file_path: str,
    comment: str | None = None,
    confirm_write: bool = False,
    confirm_comment: bool = False,
) -> str:
    """Submit a completed local file to a Canvas online-upload assignment.

    This is for student-authored finished work and requires confirm_write=True.
    If comment is set, also requires confirm_comment=True so agents cannot add
    Canvas comments unless requested.
    """
    return submit_file_assignment(
        course_id,
        assignment_id,
        file_path,
        comment,
        confirm_write,
        confirm_comment,
    )

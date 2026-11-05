"""Built-in Gradescope support: list courses and assignments, and submit files.

This works on its own with the `gradescopeapi` package. It only does what a
student does on their own account: look up their courses and assignments, and
upload a file.

Credentials come from GRADESCOPE_EMAIL and GRADESCOPE_PASSWORD in `.env`
(written by `python3 install.py --gradescope-only`). They are never accepted
as tool arguments, so they cannot end up in a chat transcript.

This module is self-contained and reads only this project's own settings.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
from typing import Any
from urllib.parse import urlparse

from canvas_mcp.formatting import markdown_table

SETUP_HINT = (
    "Gradescope is not set up yet. It is set up by running `python3 install.py --gradescope-only` "
    "in the Canvas MCP project folder: it asks for the Gradescope email and password (hidden while "
    "typing), saves them locally, and checks the login. If you can open a terminal tab for the "
    "student, start that command there and tell them to type the password into that terminal. "
    "Otherwise ask them to run it themselves. Never ask for the password in the chat, and restart "
    "is not needed afterwards."
)
INSTALL_HINT = (
    "The `gradescopeapi` package is missing. Run `python3 install.py --gradescope-only` in the "
    "Canvas MCP project folder; it installs the package and asks for the Gradescope login."
)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]

_connection: Any = None


class GradescopeError(Exception):
    """A problem the student can act on."""


def _env_files() -> list[pathlib.Path]:
    """This project's own .env files (never another project's)."""
    return [PROJECT_ROOT / ".env", pathlib.Path.cwd() / ".env"]


def _credentials() -> tuple[str, str]:
    """Gradescope email and password from the environment, else from this project's .env.

    Re-reading the file means a login saved by the installer works without
    restarting the server.
    """
    email = os.environ.get("GRADESCOPE_EMAIL", "").strip()
    password = os.environ.get("GRADESCOPE_PASSWORD", "").strip()
    if email and password:
        return email, password
    from dotenv import dotenv_values

    for path in _env_files():
        if not path.is_file():
            continue
        values = dotenv_values(path)
        email = email or (values.get("GRADESCOPE_EMAIL") or "").strip()
        password = password or (values.get("GRADESCOPE_PASSWORD") or "").strip()
        if email and password:
            break
    return email, password


def _get_connection():
    global _connection
    if _connection is not None and getattr(_connection, "logged_in", False):
        return _connection
    try:
        from gradescopeapi.classes.connection import GSConnection
    except ImportError as exc:
        raise GradescopeError(INSTALL_HINT) from exc

    email, password = _credentials()
    if not email or not password:
        raise GradescopeError(SETUP_HINT)

    conn = GSConnection()
    try:
        conn.login(email, password)
    except ValueError as exc:
        raise GradescopeError(
            f"Gradescope rejected the login ({exc}). Check the email and password. If you normally sign in "
            "with school single sign-on, set a Gradescope password first (use 'Forgot password' on "
            f"gradescope.com), then run `python3 install.py --gradescope-only`."
        ) from exc
    except Exception as exc:
        raise GradescopeError(f"Could not reach Gradescope: {exc}") from exc
    _connection = conn
    return conn


_URL_IDS = re.compile(r"/courses/(\d+)(?:/assignments/(\d+))?")


def parse_gradescope_url(url: str) -> tuple[str, str] | None:
    """Return (course_id, assignment_id) from a Gradescope assignment link.

    Handles .../courses/1/assignments/2, .../submissions/3 and similar. Returns
    None for other hosts or links without both IDs (e.g. a bare course page).
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host != "gradescope.com" and not host.endswith(".gradescope.com"):
        return None
    match = _URL_IDS.search(parsed.path)
    if not match or not match.group(2):
        return None
    return match.group(1), match.group(2)


def reset_connection() -> None:
    global _connection
    _connection = None


# --------------------------------------------------------------------------
# Read-only helpers
# --------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M %Z").strip()
    return "" if value is None else str(value)


def _assignments(conn, course_id: str) -> list[Any]:
    return conn.account.get_assignments(course_id)


def _find_assignment(conn, course_id: str, assignment_id: str):
    for item in _assignments(conn, course_id):
        if str(item.assignment_id) == str(assignment_id):
            return item
    return None


def status(check_login: bool = False) -> str:
    try:
        import gradescopeapi  # noqa: F401

        library = "installed"
    except ImportError:
        library = "missing"
    email, password = _credentials()
    lines = [
        "## Gradescope",
        "",
        f"- gradescopeapi package: {library}",
        f"- GRADESCOPE_EMAIL: {'set' if email else 'missing'}",
        f"- GRADESCOPE_PASSWORD: {'set' if password else 'missing'}",
    ]
    if library == "missing":
        lines.append(f"- {INSTALL_HINT}")
    if not (email and password):
        lines.append(f"- {SETUP_HINT}")
    if check_login and library == "installed" and email and password:
        try:
            courses = _get_connection().account.get_courses()
            count = sum(len(group) for group in courses.values())
            lines.append(f"- Login check: OK, {count} course(s) found")
        except GradescopeError as exc:
            lines.append(f"- Login check failed: {exc}")
        except Exception as exc:
            lines.append(f"- Login check failed: {exc}")
    return "\n".join(lines)


def list_courses() -> str:
    try:
        courses = _get_connection().account.get_courses()
    except GradescopeError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error listing Gradescope courses: {exc}"
    rows = []
    for role, group in courses.items():
        for course_id, course in group.items():
            rows.append([course_id, course.name, course.full_name, f"{course.semester} {course.year}", role])
    return "## Gradescope Courses\n\n" + markdown_table(["ID", "Course", "Title", "Term", "Role"], rows)


def list_assignments(course_id: str) -> str:
    try:
        items = _assignments(_get_connection(), course_id)
    except GradescopeError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error listing Gradescope assignments: {exc}"
    rows = [
        [a.assignment_id, a.name, _fmt(a.release_date), _fmt(a.due_date), _fmt(a.late_due_date),
         a.submissions_status, f"{a.grade}/{a.max_grade}" if a.grade else ""]
        for a in items
    ]
    return f"## Gradescope Assignments for `{course_id}`\n\n" + markdown_table(
        ["ID", "Assignment", "Released", "Due", "Late due", "Status", "Grade"], rows
    )


def assignment_details(course_id: str, assignment_id: str) -> str:
    try:
        item = _find_assignment(_get_connection(), course_id, assignment_id)
    except GradescopeError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error reading Gradescope assignment: {exc}"
    if item is None:
        return f"No assignment `{assignment_id}` found in Gradescope course `{course_id}`."
    return "\n".join(
        [
            f"## {item.name}",
            "",
            f"- Course `{course_id}`, assignment `{assignment_id}`",
            f"- Released: {_fmt(item.release_date)}",
            f"- Due: {_fmt(item.due_date)}",
            f"- Late due: {_fmt(item.late_due_date)}",
            f"- Status: {item.submissions_status}",
            f"- Grade: {item.grade}/{item.max_grade}" if item.grade else "- Grade: not shown",
        ]
    )


# --------------------------------------------------------------------------
# Submission
# --------------------------------------------------------------------------


def _timing_note(item) -> str:
    """Say whether the deadline has passed, when the dates carry a time zone."""
    now = dt.datetime.now(dt.timezone.utc)
    final = item.late_due_date or item.due_date
    for label, when in (("late deadline", item.late_due_date), ("due date", item.due_date)):
        if isinstance(when, dt.datetime) and when.tzinfo is not None and when < now:
            if when is final:
                return f"Warning: the {label} has passed. Gradescope will probably reject this upload."
            return f"Note: the {label} has passed, so this would count as late."
    return ""


def submit(
    course_id: str,
    assignment_id: str,
    file_paths: list[str],
    confirm_write: bool = False,
) -> str:
    """Upload files to a Gradescope assignment on the student's own account."""
    if not course_id or not assignment_id:
        return "Error: both course_id and assignment_id are required."
    if not file_paths:
        return "Error: at least one file path is required."

    paths: list[pathlib.Path] = []
    for raw in file_paths:
        original = pathlib.Path(raw).expanduser()
        if not original.is_absolute():
            return f"Error: file path must be absolute: {raw}"
        resolved = original.resolve()
        if not resolved.is_file():
            return f"Error: file not found: {raw}"
        paths.append(resolved)

    try:
        conn = _get_connection()
        item = _find_assignment(conn, course_id, assignment_id)
    except GradescopeError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error reading the Gradescope assignment: {exc}"
    if item is None:
        return (
            f"No assignment `{assignment_id}` found in Gradescope course `{course_id}`. "
            "Nothing was uploaded. Check the IDs with tool_gradescope_list_assignments."
        )

    summary = [
        f"- Assignment: **{item.name}** (course `{course_id}`, assignment `{assignment_id}`)",
        f"- Due: {_fmt(item.due_date)}; late due: {_fmt(item.late_due_date) or 'none'}",
        f"- Current status: {item.submissions_status}",
        f"- Files: {', '.join(p.name for p in paths)}",
    ]
    note = _timing_note(item)
    if note:
        summary.append(f"- {note}")

    if not confirm_write:
        return "\n".join(
            ["Write confirmation required to submit to Gradescope. No changes were made.", *summary,
             "- Show this to the student and re-run with `confirm_write=True` only after they say yes."]
        )

    try:
        from gradescopeapi.classes.upload import upload_assignment

        handles = [open(p, "rb") for p in paths]
        try:
            url = upload_assignment(conn.session, course_id, assignment_id, *handles)
        finally:
            for handle in handles:
                handle.close()
    except Exception as exc:
        return f"Error uploading to Gradescope: {exc}"

    if not url:
        return "\n".join(
            ["Upload failed. Nothing was submitted. Gradescope does not say why, so these are only "
             "possible reasons, not a diagnosis:",
             "- the assignment is past its due date, or not open for submissions",
             "- the file type is not accepted (many assignments take only PDF)",
             "- this assignment type does not take file uploads (online or code assignments)",
             "- you are not enrolled as a student in this course",
             "Tell the student it failed and that the reason is unknown; do not state one as fact. "
             "If the deadline is still open, check the file type, then try the upload on gradescope.com.",
             "", *summary]
        )

    after = ""
    try:
        fresh = _find_assignment(conn, course_id, assignment_id)
        if fresh is not None:
            after = f"- Status now: {fresh.submissions_status}\n"
    except Exception:
        pass
    return (
        "Submitted to Gradescope.\n"
        + "\n".join(summary)
        + f"\n- Submission page: {url}\n{after}"
        "- If this assignment asks you to mark which pages answer which questions, "
        "open the submission page and do that there. Uploading the file does not do it."
    )

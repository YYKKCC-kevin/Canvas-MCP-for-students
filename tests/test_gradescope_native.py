from __future__ import annotations

import datetime as dt
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp.tools import gradescope_bridge, gradescope_native as gs

PASSWORD = "s3cret-password-xyz"
UTC = dt.timezone.utc


class Assignment:
    def __init__(self, aid, name, due=None, late=None, status="No Submission", grade="", max_grade="10"):
        self.assignment_id, self.name = aid, name
        self.release_date = dt.datetime(2026, 10, 1, tzinfo=UTC)
        self.due_date, self.late_due_date = due, late
        self.submissions_status, self.grade, self.max_grade = status, grade, max_grade


class Course:
    def __init__(self, name, full_name, semester, year):
        self.name, self.full_name, self.semester, self.year = name, full_name, semester, year
        self.num_grades_published, self.num_assignments = "0", "3"


class FakeAccount:
    def __init__(self, assignments):
        self.assignments = assignments

    def get_courses(self):
        return {"instructor": {}, "student": {"111": Course("STATS 120A", "Intro Prob", "Fall", "2026")}}

    def get_assignments(self, course_id):
        return self.assignments


class FakeConnection:
    login_error: Exception | None = None
    assignments: list = []
    logins: list = []

    def __init__(self):
        self.logged_in = False
        self.session = object()

    def login(self, email, password):
        FakeConnection.logins.append((email, password))
        if FakeConnection.login_error:
            raise FakeConnection.login_error
        self.logged_in = True
        self.account = FakeAccount(FakeConnection.assignments)


@pytest.fixture(autouse=True)
def fake_gradescopeapi(monkeypatch):
    uploads: list = []

    def upload_assignment(session, course_id, assignment_id, *files, **kwargs):
        uploads.append((course_id, assignment_id, [f.name for f in files]))
        return upload_assignment.result

    upload_assignment.result = "https://www.gradescope.com/courses/111/assignments/222/submissions/9"

    pkg = types.ModuleType("gradescopeapi")
    classes = types.ModuleType("gradescopeapi.classes")
    conn = types.ModuleType("gradescopeapi.classes.connection")
    conn.GSConnection = FakeConnection
    up = types.ModuleType("gradescopeapi.classes.upload")
    up.upload_assignment = upload_assignment
    for name, mod in {"gradescopeapi": pkg, "gradescopeapi.classes": classes,
                      "gradescopeapi.classes.connection": conn, "gradescopeapi.classes.upload": up}.items():
        monkeypatch.setitem(sys.modules, name, mod)

    monkeypatch.setenv("GRADESCOPE_EMAIL", "student@example.edu")
    monkeypatch.setenv("GRADESCOPE_PASSWORD", PASSWORD)
    FakeConnection.login_error = None
    FakeConnection.logins = []
    FakeConnection.assignments = [
        Assignment("222", "Homework 3", due=dt.datetime(2099, 1, 1, tzinfo=UTC)),
        Assignment("333", "Homework 2", due=dt.datetime(2020, 1, 1, tzinfo=UTC), late=dt.datetime(2020, 1, 3, tzinfo=UTC)),
    ]
    gs.reset_connection()
    uploads_holder = types.SimpleNamespace(calls=uploads, fn=upload_assignment)
    yield uploads_holder
    gs.reset_connection()


@pytest.fixture
def pdf(tmp_path):
    f = tmp_path / "hw3.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    return str(f)


# ---- setup problems are actionable and never leak the password ---------------


def test_missing_credentials_point_to_the_installer_and_not_the_chat(monkeypatch):
    monkeypatch.delenv("GRADESCOPE_PASSWORD")
    out = gs.list_courses()
    assert "python3 install.py --gradescope-only" in out
    assert "Do not paste your password" in out


def test_missing_library_gives_install_command(monkeypatch):
    monkeypatch.setitem(sys.modules, "gradescopeapi.classes.connection", None)
    assert "gradescopeapi" in gs.list_courses() and "pip install" in gs.list_courses()


def test_rejected_login_mentions_sso_accounts():
    FakeConnection.login_error = ValueError("bad credentials")
    out = gs.list_courses()
    assert "single sign-on" in out
    assert PASSWORD not in out


def test_password_never_appears_in_any_output(pdf):
    outputs = [gs.status(True), gs.list_courses(), gs.list_assignments("111"),
               gs.assignment_details("111", "222"), gs.submit("111", "222", [pdf]),
               gs.submit("111", "222", [pdf], confirm_write=True)]
    assert all(PASSWORD not in o for o in outputs)
    assert "set" in gs.status() and "student@example.edu" not in gs.status()


# ---- read-only tools -------------------------------------------------------------


def test_courses_and_assignments_are_listed():
    assert "STATS 120A" in gs.list_courses() and "student" in gs.list_courses()
    out = gs.list_assignments("111")
    assert "Homework 3" in out and "Homework 2" in out and "222" in out
    assert "Homework 3" in gs.assignment_details("111", "222")
    assert "No assignment `999`" in gs.assignment_details("111", "999")


def test_login_is_reused_between_calls():
    gs.list_courses()
    gs.list_assignments("111")
    assert len(FakeConnection.logins) == 1


# ---- submission safety -----------------------------------------------------------


def test_without_confirmation_nothing_is_uploaded(pdf, fake_gradescopeapi):
    out = gs.submit("111", "222", [pdf])
    assert "No changes were made" in out and "Homework 3" in out and "hw3.pdf" in out
    assert "confirm_write=True" in out
    assert fake_gradescopeapi.calls == []


def test_confirmed_submit_uploads_and_reports(pdf, fake_gradescopeapi):
    out = gs.submit("111", "222", [pdf], confirm_write=True)
    assert out.startswith("Submitted to Gradescope")
    assert "submissions/9" in out
    assert "mark which pages answer which questions" in out
    assert fake_gradescopeapi.calls == [("111", "222", [pdf])]


def test_failed_upload_says_nothing_was_submitted(pdf, fake_gradescopeapi):
    fake_gradescopeapi.fn.result = None
    out = gs.submit("111", "222", [pdf], confirm_write=True)
    assert "Nothing was submitted" in out and "past its due date" in out


def test_unknown_assignment_blocks_the_upload(pdf, fake_gradescopeapi):
    out = gs.submit("111", "999", [pdf], confirm_write=True)
    assert "Nothing was uploaded" in out
    assert fake_gradescopeapi.calls == []


def test_bad_paths_are_rejected_before_login(tmp_path):
    assert "must be absolute" in gs.submit("111", "222", ["hw.pdf"], confirm_write=True)
    assert "not found" in gs.submit("111", "222", [str(tmp_path / "missing.pdf")], confirm_write=True)
    assert "at least one file" in gs.submit("111", "222", [])
    assert "required" in gs.submit("", "222", ["/x"])
    assert FakeConnection.logins == []


def test_past_deadline_is_warned_about_in_the_preview(pdf):
    assert "has passed" in gs.submit("111", "333", [pdf])
    assert "Warning" not in gs.submit("111", "222", [pdf])


# ---- bridge falls back to the built-in support ------------------------------------


@pytest.fixture
def no_external_gradescope_mcp(monkeypatch):
    monkeypatch.setattr(gradescope_bridge, "_resolve_gradescope_mcp_path", lambda path=None: None)


def test_bridge_tools_work_without_a_separate_gradescope_mcp(no_external_gradescope_mcp):
    assert "STATS 120A" in gradescope_bridge.gradescope_list_courses()
    assert "Homework 3" in gradescope_bridge.gradescope_list_assignments("111")
    assert "Homework 3" in gradescope_bridge.gradescope_get_assignment_details("111", "222")
    status = gradescope_bridge.gradescope_bridge_status(check_login=True)
    assert "Login check: OK" in status


# ---- direct links from Canvas skip the search -------------------------------------


def test_parse_gradescope_url_extracts_ids():
    p = gs.parse_gradescope_url
    assert p("https://www.gradescope.com/courses/111/assignments/222") == ("111", "222")
    assert p("https://www.gradescope.com/courses/111/assignments/222/submissions/9?x=1") == ("111", "222")
    assert p("https://gradescope.com/courses/111/assignments/222/") == ("111", "222")


def test_parse_gradescope_url_rejects_non_assignment_links():
    p = gs.parse_gradescope_url
    assert p("https://www.gradescope.com/courses/111") is None
    assert p("https://www.gradescope.com/") is None
    assert p("https://evilgradescope.com/courses/1/assignments/2") is None
    assert p("https://example.com/courses/1/assignments/2") is None
    assert p("not a url") is None


def test_canvas_source_with_direct_gradescope_link_gives_ids_and_skips_search():
    from canvas_mcp.tools.sources import resolve_assignment_source_from_canvas

    html = '<a href="https://www.gradescope.com/courses/111/assignments/222">Submit here</a>'
    out = resolve_assignment_source_from_canvas("HW3", html, "https://canvas.example.edu")
    assert "course_id=`111`" in out and "assignment_id=`222`" in out
    assert "tool_gradescope_list_courses" not in out


def test_canvas_source_without_link_still_asks_the_student():
    from canvas_mcp.tools.sources import resolve_assignment_source_from_canvas

    out = resolve_assignment_source_from_canvas("HW3", "<p>Submit on Gradescope.</p>", "https://canvas.example.edu")
    assert "tool_gradescope_list_courses" in out
    assert "Ask the user which Gradescope" in out

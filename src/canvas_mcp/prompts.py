"""MCP prompts: ready-made workflows that show up as slash commands.

Each prompt returns instructions for the AI host. They do not call Canvas
themselves; they tell the assistant which tools to call, in what order, and
where it must stop and ask the student. The safety rules from the server
instructions (AI-permission check, no exam completion, explicit confirmation
before any submission) are repeated inside the prompts that need them, so
they hold even when a host ignores the server-level instructions.
"""

from __future__ import annotations

from collections.abc import Callable

# --------------------------------------------------------------------------
# Shared building blocks
# --------------------------------------------------------------------------

STYLE = (
    "Reply in the language the student writes in. Be concrete: give dates with "
    "weekday and time zone, and say when a value is missing in Canvas instead "
    "of guessing."
)

CURRENT_TERM = (
    "Canvas keeps past-term courses listed as active, so use today's date and "
    "each course's Term column to pick the current term, and say which courses "
    "you treated as current. Show the Role column too: the student may be a "
    "TA in some courses."
)

AI_GATE = (
    "AI-permission gate: you may only write or finish graded work for the "
    "student after the student has said that this course or instructor allows "
    "AI assistance for this assignment. If that has not been said in this "
    "conversation, ask once, quote any AI policy you found in the syllabus or "
    "assignment text, and stop until they answer. If the answer is no or "
    "unclear, switch to learning support: explain concepts, give hints, and "
    "review the student's own draft."
)

SUBMIT_AI_GATE = (
    "AI-permission gate: if AI helped produce this work, confirm the student "
    "has said that this course or instructor allows it for this assignment. "
    "If that is not clear from this conversation, ask once and stop until "
    "they answer. If AI use is not allowed, do not submit AI-produced work; "
    "offer learning support or help with the student's own work instead."
)

WRITE_GATE = (
    "Submission gate: never call a submit tool with confirm_write=True until "
    "the student has replied yes, in this conversation, to a summary of "
    "exactly what will be submitted. Never add a comment (confirm_comment) "
    "unless the student asked for one. A submission may be final, so treat it "
    "as irreversible."
)


GRADESCOPE_STEPS = (
    "If the assignment is actually submitted on Gradescope (the "
    "tool_resolve_assignment_source or assignment text says so), submit it "
    "there instead of steps 4 and 5, and the same gates apply:\n"
    "a. Call tool_gradescope_status. If the Gradescope login is not "
    "set up, run `python3 install.py --gradescope-only` in the Canvas MCP "
    "project folder for me if you can open a terminal (otherwise tell me to "
    "run it), tell me to type my Gradescope email and password into that "
    "terminal, and tell me not to paste the password into this chat. Then "
    "wait until I say it is done; no restart is needed.\n"
    "b. If the Canvas assignment already links to the Gradescope "
    "assignment (tool_resolve_assignment_source shows a Direct Gradescope "
    "Assignment with course_id and assignment_id), use those IDs directly "
    "and do not search or ask me. Only if there is no such link, call "
    "tool_gradescope_list_courses and tool_gradescope_list_assignments, ask "
    "me which Gradescope assignment it is, and have me confirm the match "
    "(name, due date). Gradescope IDs differ from Canvas IDs.\n"
    "c. Call tool_gradescope_submit_assignment without confirm_write to get "
    "the preview. Show it to me, including any late warning, and ask for a "
    "clear yes.\n"
    "d. Only after my yes, call it again with confirm_write=True, then "
    "report the submission page and status. If the assignment asks me to "
    "mark which pages answer which questions, tell me to do that on the "
    "submission page, because uploading does not do it.\n"
)


def _course(course_id: str) -> str:
    if course_id.strip():
        return f"Canvas course {course_id.strip()}"
    return (
        "the course the student means (no course ID was given: call "
        "tool_list_courses, pick the current-term courses, and ask which one "
        "if it is not obvious)"
    )


def _assignment(course_id: str, assignment_id: str) -> str:
    if course_id.strip() and assignment_id.strip():
        return f"assignment {assignment_id.strip()} in course {course_id.strip()}"
    return (
        "the assignment the student means (course or assignment ID missing: "
        "find it with tool_list_courses and tool_list_course_assignments, "
        "then confirm the match with the student before continuing)"
    )


# --------------------------------------------------------------------------
# Know your courses
# --------------------------------------------------------------------------


def my_courses_overview() -> str:
    """List this term's courses with role, instructor, and class times. (本学期课程概览)"""
    return (
        "Give me an overview of my current Canvas courses.\n"
        "1. Call tool_list_courses. " + CURRENT_TERM + "\n"
        "2. For each current-term course, call tool_get_course_info and pull "
        "out the instructor, meeting days and times, location, and office "
        "hours if the syllabus or course page states them.\n"
        "3. Present one table: course, role, instructor, class time and "
        "place, office hours. Write 'not stated in Canvas' where the data is "
        "missing.\n"
        "4. Close with the one or two courses that look most urgent, based on "
        "tool_get_missing_work.\n" + STYLE
    )


def course_requirements(course_id: str = "") -> str:
    """Summarize a course's syllabus: grading, schedule, policies, AI rules. (课程要求与规定)"""
    return (
        f"Summarize what {_course(course_id)} requires of me.\n"
        "1. Call tool_get_course_info for the syllabus, then "
        "tool_list_course_modules and tool_list_course_announcements "
        "(last 30 days) for anything the syllabus leaves out.\n"
        "2. Report: grading breakdown and late policy; weekly schedule and "
        "key dates; exam dates and formats; attendance and participation; "
        "required materials; instructor and TA contact and office hours.\n"
        "3. Report separately, quoting the exact wording, what the course "
        "says about AI tools, collaboration, and academic integrity. If it "
        "says nothing, say so plainly. Do not infer a policy.\n"
        "4. List anything unclear that I should ask the instructor.\n" + STYLE
    )


# --------------------------------------------------------------------------
# Deadlines and exams
# --------------------------------------------------------------------------


def deadlines_and_exams(days_ahead: str = "14", course_id: str = "") -> str:
    """Show upcoming deadlines, overdue work, and exam dates in one timeline. (DDL与考试时间)"""
    scope = f"course {course_id.strip()}" if course_id.strip() else "all my current-term courses"
    return (
        f"Build my deadline and exam timeline for {scope}, covering the next "
        f"{days_ahead.strip() or '14'} days.\n"
        "1. Call tool_get_missing_work (include overdue) and "
        "tool_get_todo_items for the window.\n"
        "2. Call tool_list_exam_items for exams, quizzes, midterms, and "
        "finals. Exams outside the window still matter: list them under "
        "'later'.\n"
        "3. Merge everything into one list sorted by date. Mark each row "
        "overdue, due today, due this week, or later, and show the course "
        "and whether it is submitted on Canvas, Gradescope, or elsewhere.\n"
        "4. Flag clusters (several items due within 48 hours) and anything "
        "overdue that can still be submitted.\n"
        "5. End with a suggested order to work in. " + CURRENT_TERM + "\n" + STYLE
    )


# --------------------------------------------------------------------------
# Lectures and studying
# --------------------------------------------------------------------------


def summarize_lecture_materials(course_id: str = "", topic: str = "") -> str:
    """Summarize lecture slides and module materials for a course or topic. (讲义/PPT总结)"""
    focus = f" focused on '{topic.strip()}'" if topic.strip() else ""
    return (
        f"Help me understand the lecture materials for {_course(course_id)}{focus}.\n"
        "1. Call tool_list_course_modules (use search_term for the topic) to "
        "find lecture slides, readings, and notes.\n"
        "2. For each lecture file (a File item with an ID in the ID "
        "column), call tool_read_course_file. If a result is cut off, "
        "continue with its start_char. The text is read in memory and "
        "nothing is saved to my computer. If a result says a temporary copy "
        "was saved (scanned or image-only files), open that file and read "
        "its pages directly, then call tool_clear_temp_materials. Work only "
        "from content you actually received or saw. If a file cannot be "
        "read at all, say exactly which files and why, and ask me to export "
        "it (PDF or text) and give you the path. Never invent slide content "
        "from a title.\n"
        "3. Produce: a short overview per lecture; key definitions, "
        "formulas, and theorems; worked-example patterns; and what the "
        "materials suggest is exam-relevant, marked as your inference.\n"
        "4. End with 5 self-test questions and offer a practice version with "
        "tool_make_practice_version.\n" + STYLE
    )


def study_for_exam(course_id: str = "", exam: str = "") -> str:
    """Condense all course materials into key points and predict likely exam questions. (考试复习与押题)"""
    target = f" the exam '{exam.strip()}'" if exam.strip() else " my next exam"
    return (
        f"Help me study for{target} in {_course(course_id)}.\n"
        "1. Call tool_list_exam_items to find the exam, its date, and any "
        "stated coverage; check tool_list_course_announcements and "
        "tool_get_course_info for format and allowed materials.\n"
        "2. Gather the evidence. Call tool_list_course_modules for all "
        "lecture slides and notes, tool_list_course_assignments for all "
        "homework, and look in modules and files for past exams, practice "
        "exams, or review sheets. Read each relevant file with "
        "tool_read_course_file (read in chunks with start_char; if a file has "
        "no readable text, say so instead of guessing its content). Cover "
        "everything the exam includes, not just a sample.\n"
        "3. Organise the knowledge points by topic. For each one give a short "
        "plain-language explanation, the key formula or rule, one tiny "
        "example, and the usual pitfall. Keep it brief enough to review "
        "quickly, and mark what is must-know versus nice-to-know.\n"
        "4. Predict the most likely questions. Base each prediction on "
        "evidence and cite it: how past exams were structured and which "
        "topics repeat, topics the instructor stressed in lectures or "
        "announcements, topics that homework drilled, and the stated exam "
        "coverage. For each predicted question give the topic, the likely "
        "question type, a confidence level (high/medium/low) with the reason, "
        "and a worked example question with a hint before the solution. "
        "These are informed guesses, so say so, and do not claim to know the "
        "actual questions.\n"
        "5. Build a day-by-day plan from today to the exam date, weighting "
        "topics by predicted likelihood and by how much I have already "
        "practised them. For finished homework, offer a similar-but-different "
        "set via tool_make_practice_version.\n"
        + STYLE
    )


# --------------------------------------------------------------------------
# Assignments: understand, do, check, submit
# --------------------------------------------------------------------------


def start_assignment(course_id: str = "", assignment_id: str = "") -> str:
    """Understand an assignment: requirements, deadline, where to submit. (了解作业要求)"""
    return (
        f"Help me get started on {_assignment(course_id, assignment_id)}. "
        "Do not write any answers yet.\n"
        "1. Call tool_get_assignment_details and "
        "tool_resolve_assignment_source to learn whether the real prompt and "
        "submission live on Canvas, GitHub, Gradescope, or somewhere I must "
        "tell you. If it is not Canvas, ask me for the link or file.\n"
        "2. Call tool_prepare_assignment_workspace to save assignment.md and "
        "download linked files.\n"
        "3. Report: what is asked, in my own checklist form; due date with "
        "time zone and time left; points; submission type and what file "
        "format is expected; allowed resources; anything ambiguous.\n"
        "4. Quote any AI-use statement in the assignment text or syllabus. "
        "Then ask me whether this course or instructor allows AI "
        "assistance on this assignment, and wait for my answer.\n"
        + STYLE
    )


def complete_assignment(
    course_id: str = "",
    assignment_id: str = "",
    ai_policy_note: str = "",
) -> str:
    """Draft a full solution, only after AI use is confirmed as allowed. (在许可下完成作业)"""
    if ai_policy_note.strip():
        gate = (
            "The student states the AI policy is: "
            f"'{ai_policy_note.strip()}'. Treat that as their confirmation "
            "that AI help is allowed, but if it sounds conditional (for "
            "example 'only for brainstorming', 'must be cited'), follow the "
            "condition and tell them what it limits."
        )
    else:
        gate = AI_GATE
    return (
        f"Help me complete {_assignment(course_id, assignment_id)}.\n"
        f"{gate}\n"
        "Once the gate is passed:\n"
        "1. Call tool_get_assignment_details, tool_resolve_assignment_source, "
        "and tool_prepare_homework_help_pack to collect the prompt, files, "
        "and a template. If the real prompt is on GitHub or Gradescope, get "
        "it from there or ask me.\n"
        "2. Work through every part of the assignment. Show the method, not "
        "just the answer, and follow the required format and file type. "
        "Never fabricate data, results, citations, or quotes; mark anything "
        "you are unsure about instead of guessing.\n"
        "3. Save the finished work to a file in the workspace folder and "
        "tell me its path. Keep it separate from assignment.md and "
        "templates.\n"
        "4. Keep a short note of what you did so I can disclose AI use if "
        "the course requires it.\n"
        "5. Run the check described in the review_before_submit workflow, "
        "but do not submit. Submitting is a separate step I will ask for.\n"
        + STYLE
    )


def review_before_submit(
    course_id: str = "",
    assignment_id: str = "",
    file_path: str = "",
) -> str:
    """Check a finished file for correctness, coverage, and format before submitting. (提交前检查)"""
    where = f"the file at {file_path.strip()}" if file_path.strip() else "my finished file (ask me for the path if unclear)"
    return (
        f"Review {where} against {_assignment(course_id, assignment_id)} "
        "before I submit. Do not submit anything.\n"
        "1. Call tool_get_assignment_details for the requirements, due "
        "date, and submission type, and tool_get_my_submission for what is "
        "already on Canvas.\n"
        "2. Call tool_review_submission_file for structure, readability, "
        "and coverage of each part. This is a readiness check, not proof "
        "of correctness.\n"
        "3. For correctness call tool_review_solution_for_chat, then read "
        "the artifact it prepares and reason through each answer yourself. "
        "State your confidence, and say when there is no reference answer "
        "or rubric to check against. For a high-stakes item, "
        "tool_prepare_multi_agent_review_packet gives an independent "
        "second look.\n"
        "4. Check the practical items: right file for the right assignment "
        "(not the template or assignment.md), accepted file type, name and "
        "ID filled in, every question answered, any required AI disclosure "
        "present, and whether the due date has passed.\n"
        "5. Report as: blocking problems, should-fix, optional polish, and "
        "a clear 'ready to submit' or 'not ready'.\n" + STYLE
    )


def submit_assignment(
    course_id: str = "",
    assignment_id: str = "",
    file_path: str = "",
) -> str:
    """Submit finished work to Canvas, only after you confirm the exact summary. (确认后提交)"""
    return (
        f"Submit my finished work to {_assignment(course_id, assignment_id)}.\n"
        + SUBMIT_AI_GATE
        + "\n" + WRITE_GATE + "\n"
        "Steps:\n"
        "1. Call tool_get_assignment_details and tool_get_my_submission. "
        "Check the submission type (file upload, text entry, or URL), "
        "whether it is open, whether the due date has passed (late or "
        "locked), and whether something is already submitted.\n"
        "2. Identify what I am submitting: "
        + (f"the file {file_path.strip()}" if file_path.strip() else "ask me for the file path or text")
        + ". Confirm it is the final deliverable and has been reviewed. If it "
        "has not, run the review_before_submit workflow first.\n"
        "3. Show me a summary: assignment title and course, exact file name "
        "or text, due date and late status, whether it replaces an "
        "existing submission, and that no comment will be added. Then stop "
        "and ask for a clear yes.\n"
        "4. Only after my yes, call the matching tool: "
        "tool_submit_file_assignment, tool_submit_text_assignment, or "
        "tool_submit_url_assignment, with confirm_write=True.\n"
        "5. Call tool_get_my_submission again and report what Canvas now "
        "shows: status, time, and file name.\n"
        + GRADESCOPE_STEPS + STYLE
    )


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

PROMPTS: tuple[Callable[..., str], ...] = (
    my_courses_overview,
    course_requirements,
    deadlines_and_exams,
    summarize_lecture_materials,
    study_for_exam,
    start_assignment,
    complete_assignment,
    review_before_submit,
    submit_assignment,
)


def register_prompts(mcp) -> None:
    """Register every prompt on a FastMCP server."""
    for fn in PROMPTS:
        mcp.prompt()(fn)

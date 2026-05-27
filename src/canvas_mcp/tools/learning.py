"""Coursework assistance tools for organizing, drafting, and reviewing work."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from canvas_mcp.tools.assignments import (
    DEFAULT_DOWNLOAD_DIR,
    get_assignment_details,
    prepare_assignment_workspace,
)
from canvas_mcp.tools.sources import resolve_assignment_source


QUESTION_RE = re.compile(r"(?m)^\s*(\d+)\.\s+(.+?)(?=^\s*\d+\.\s+|\Z)", re.S)


def _plain(text: str | None) -> str:
    return (text or "").replace("\r\n", "\n").strip()


def _questions(assignment_text: str | None) -> list[tuple[str, str]]:
    text = _plain(assignment_text)
    found: dict[str, str] = {}
    for number, body in QUESTION_RE.findall(text):
        normalized = re.sub(r"\s+", " ", body).strip()
        if not normalized:
            continue
        if number not in found or len(normalized) > len(found[number]):
            found[number] = normalized
    if "2" not in found and "in lecture, we showed the following result" in text.lower():
        found["2"] = (
            "In lecture, we showed a prediction interval result. Explain why, "
            "for large n, the t critical value can be approximated by z0.975 = 1.96."
        )
    if found:
        return sorted(found.items(), key=lambda item: int(item[0]))
    if text:
        return [("1", text)]
    return [("1", "Read the assignment instructions and write your solution.")]


def create_homework_template(
    assignment_title: str,
    assignment_text: str | None = None,
    output_path: str | None = None,
) -> str:
    """Create a structured homework workspace for student drafting."""
    title = assignment_title.strip() or "Canvas Homework"
    lines = [
        f"# {title} Template",
        "",
        "This template organizes the assignment into editable solution sections.",
        "Use it to draft derivations, calculations, explanations, and final responses.",
        "",
    ]
    for number, _body in _questions(assignment_text):
        lines.extend(
            [
                f"## Problem {number}",
                "",
                "### Given / Setup",
                "- [Summarize the quantities and assumptions from the prompt.]",
                "",
                "### Formula / Method",
                "- [Write the relevant formula or test procedure.]",
                "",
                "### Your Work",
                "[Write your work here.]",
                "",
                "### Final Response",
                "[State your final answer in your own words.]",
                "",
            ]
        )

    result = "\n".join(lines).rstrip() + "\n"
    if output_path:
        Path(output_path).expanduser().write_text(result, encoding="utf-8")
        return f"Template written to `{Path(output_path).expanduser()}`."
    return result


def generate_hint_pack(
    assignment_title: str,
    assignment_text: str | None,
    output_path: str | None = None,
) -> str:
    """Generate a homework support pack with concepts, steps, and checks."""
    title = assignment_title.strip() or "Canvas Homework"
    lines = [
        f"# {title} Homework Support Pack",
        "",
        "Use this pack to plan, draft, verify, and improve your work according to your course policy.",
        "",
    ]
    for number, body in _questions(assignment_text):
        lower = body.lower()
        hints = ["Restate the question in your own words before computing."]
        if "least square" in lower or "regression" in lower:
            hints.extend(
                [
                    "For least squares, start from Sxx, Sxy, and the fitted-line formulas.",
                    "Identify the model, response, covariate, and unknown parameters.",
                    "Write the estimator formula symbolically before substituting numbers.",
                    "Check whether the question asks for estimation, testing, or prediction.",
                ]
            )
        if "test" in lower or "association" in lower or "hypothes" in lower:
            hints.extend(
                [
                    "State both hypotheses before computing the statistic.",
                    "Use the correct degrees of freedom and compare against the right cutoff.",
                    "End with a conclusion in the context of the problem.",
                ]
            )
        if "confidence interval" in lower or "prediction interval" in lower:
            hints.extend(
                [
                    "Decide whether the interval is for a mean response or an individual response.",
                    "Include the residual variance term and leverage term when appropriate.",
                    "Interpret the interval using the units and context from the prompt.",
                ]
            )
        if "maximum likelihood" in lower or "mle" in lower:
            hints.extend(
                [
                    "Write the objective function first.",
                    "Differentiate with respect to the unknown parameter and solve.",
                ]
            )

        lines.extend([f"## Problem {number}", ""])
        lines.extend(f"- {hint}" for hint in hints)
        lines.append("")

    result = "\n".join(lines).rstrip() + "\n"
    if output_path:
        Path(output_path).expanduser().write_text(result, encoding="utf-8")
        return f"Hint pack written to `{Path(output_path).expanduser()}`."
    return result


def check_my_draft(
    assignment_title: str,
    assignment_text: str | None,
    draft_text: str,
    output_path: str | None = None,
) -> str:
    """Check a student's draft for structure and common missing pieces."""
    title = assignment_title.strip() or "Canvas Homework"
    draft = _plain(draft_text)
    lines = [
        f"# {title} Draft Check",
        "",
        "This is a structural and reasoning checklist, not a correctness guarantee.",
        "",
    ]
    if not draft:
        lines.append("- Draft text is empty.")

    for number, body in _questions(assignment_text):
        lower = body.lower()
        aliases = [f"problem {number}", f"{number}.", f"{number})", f"#{number}"]
        found = any(alias.lower() in draft.lower() for alias in aliases)
        if found:
            lines.append(f"- Problem {number}: section found.")
        else:
            lines.append(f"- Problem {number}: section not found.")
        if ("test" in lower or "hypothes" in lower) and "h_0" not in draft.lower() and "h0" not in draft.lower():
            lines.append(f"- Problem {number}: check that you state H0 and HA.")
        if ("confidence interval" in lower or "prediction interval" in lower) and "interval" not in draft.lower():
            lines.append(f"- Problem {number}: check that you include an interval and interpretation.")
        if "regression" in lower and "beta" not in draft.lower() and "\\beta" not in draft:
            lines.append(f"- Problem {number}: check that you define regression parameters.")

    result = "\n".join(lines).rstrip() + "\n"
    if output_path:
        Path(output_path).expanduser().write_text(result, encoding="utf-8")
        return f"Draft check written to `{Path(output_path).expanduser()}`."
    return result


def review_submission_file(
    assignment_title: str,
    submission_path: str,
    assignment_text: str | None = None,
    assignment_path: str | None = None,
    output_path: str | None = None,
) -> str:
    """Review a finished submission file for structural readiness before upload."""
    path = Path(submission_path).expanduser()
    lines = [
        "## Submission File Review",
        "",
        f"- Assignment: {assignment_title.strip() or 'Canvas Assignment'}",
        f"- Submission file: `{path}`",
        "- Scope: structural/readiness review, not a full mathematical correctness proof.",
        "",
    ]
    issues: list[str] = []
    warnings: list[str] = []

    if not path.exists() or not path.is_file():
        issues.append("Submission file does not exist or is not a regular file.")
        return _finish_submission_review(lines, issues, warnings, output_path)

    submission_text = _file_text(path)
    if not submission_text:
        issues.append("Could not extract readable text from the submission file.")
    else:
        lines.extend(
            [
                "### File Readability",
                f"- Extracted text length: {len(submission_text)} characters.",
                f"- Detected title/first line: {_first_nonempty_line(submission_text) or '(none)'}",
                "",
            ]
        )

    prompt_text = _plain(assignment_text)
    if assignment_path:
        prompt_path = Path(assignment_path).expanduser()
        prompt_from_file = _file_text(prompt_path)
        if prompt_from_file:
            prompt_text = f"{prompt_text}\n\n{prompt_from_file}".strip()
        else:
            warnings.append(f"Could not extract readable text from assignment file `{prompt_path}`.")

    expected_numbers = _problem_numbers(prompt_text)
    found_numbers = _problem_numbers(submission_text)
    if expected_numbers:
        missing = [number for number in expected_numbers if number not in found_numbers]
        lines.extend(
            [
                "### Problem Coverage",
                f"- Expected problems: {', '.join(expected_numbers)}",
                f"- Found solution sections: {', '.join(found_numbers) or '(none)'}",
                "",
            ]
        )
        if missing:
            issues.append(f"Missing visible solution section(s): {', '.join(missing)}.")
    elif submission_text:
        warnings.append(
            "No expected problem numbers were available; coverage was checked only heuristically."
        )

    if submission_text and _looks_prompt_only(submission_text, prompt_text, path.name):
        issues.append(
            "Submission may be the prompt/assignment PDF rather than a completed solution."
        )
    if submission_text and not _looks_like_solution(submission_text, path.name):
        warnings.append(
            "Submission does not clearly label itself as a solution; verify this is intentional."
        )

    if prompt_text and submission_text:
        overlap = _line_overlap_ratio(prompt_text, submission_text)
        lines.extend(
            [
                "### Prompt Overlap",
                f"- Approximate prompt-line overlap: {overlap:.0%}",
                "",
            ]
        )
        if overlap > 0.75:
            issues.append(
                "Submission text overlaps heavily with the prompt, which can indicate the prompt file was selected."
            )

    return _finish_submission_review(lines, issues, warnings, output_path)


def review_solution_correctness(
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
    """Review a student solution for likely correctness issues."""
    solution = _collect_text(solution_text, solution_path)
    prompt = _collect_text(assignment_text, assignment_path)
    reference = _collect_text(reference_text, reference_path)
    rubric = _plain(rubric_text)

    lines = [
        "## Solution Correctness Review",
        "",
        f"- Assignment: {assignment_title.strip() or 'Canvas Assignment'}",
        "- Scope: correctness-oriented review, not an official grade or guarantee.",
        "",
    ]
    issues: list[str] = []
    warnings: list[str] = []

    if not solution:
        issues.append("No readable solution text was provided.")
        return _finish_correctness_review(lines, issues, warnings, "low", output_path)

    expected_numbers = _problem_numbers(prompt or reference)
    solution_numbers = _problem_numbers(solution)
    if expected_numbers:
        missing = [number for number in expected_numbers if number not in solution_numbers]
        lines.extend(
            [
                "### Problem Coverage",
                f"- Expected problems: {', '.join(expected_numbers)}",
                f"- Found solution sections: {', '.join(solution_numbers) or '(none)'}",
                "",
            ]
        )
        if missing:
            issues.append(f"Missing solution section(s): {', '.join(missing)}.")
    else:
        warnings.append("No problem numbers were available from the prompt/reference.")

    if not reference and not rubric:
        warnings.append(
            "No reference answer or rubric was provided, so this can only perform "
            "low-confidence internal consistency checks."
        )
        _add_internal_correctness_checks(solution, warnings)
        return _finish_correctness_review(lines, issues, warnings, "low", output_path)

    reference_issues = _reference_answer_checks(solution, reference)
    issues.extend(reference_issues)
    if reference:
        lines.extend(_reference_overlap_section(solution, reference))
    if rubric:
        warnings.extend(_rubric_term_checks(solution, rubric))

    confidence = "medium" if reference else "low"
    return _finish_correctness_review(lines, issues, warnings, confidence, output_path)


def prepare_solution_review_artifact(
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
    """Prepare a Gradescope-style artifact for agent correctness review."""
    solution = _collect_text(solution_text, solution_path)
    prompt = _collect_text(assignment_text, assignment_path)
    reference = _collect_text(reference_text, reference_path)
    rubric = _plain(rubric_text)

    base_dir = Path(output_dir or "canvas-mcp-reviews").expanduser()
    if not output_dir and DEFAULT_DOWNLOAD_DIR:
        base_dir = Path(DEFAULT_DOWNLOAD_DIR).expanduser() / "reviews"
    base_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = base_dir / f"{_safe_slug(assignment_title or 'assignment')}-review.md"

    reference_status = "user-provided reference answer" if reference else "missing"
    if rubric and not reference:
        reference_status = "rubric-only fallback"
    elif reference and rubric:
        reference_status = "user-provided reference answer plus rubric"

    lines = [
        f"# Solution Correctness Review Artifact: {assignment_title.strip() or 'Canvas Assignment'}",
        "",
        "This artifact is designed for an AI agent to review a student's work for likely correctness issues.",
        "It mirrors the Gradescope MCP pattern: gather context first, then let the agent reason and report confidence.",
        "",
        "## Review Contract",
        "",
        f"- Assignment title: {assignment_title.strip() or 'Canvas Assignment'}",
        f"- Solution source: `{solution_path}`" if solution_path else "- Solution source: inline text",
        f"- Prompt source: `{assignment_path}`" if assignment_path else "- Prompt source: inline text or missing",
        f"- Reference source: {reference_status}",
        "- Preferred mode: correctness review before submission, not official grading.",
        "- If no reference answer is available, draft a provisional grading basis from the prompt and domain knowledge.",
        "- Treat any agent-drafted grading basis as fallible; lower confidence when the expected solution is not clear.",
        "",
        "## Agent Review Instructions",
        "",
        "1. Split the prompt and student solution by problem/subproblem.",
        "2. If a reference answer exists, compare against it first.",
        "3. If no reference answer exists, derive a provisional expected solution from the prompt before judging the student answer.",
        "4. Check final answers, definitions, assumptions, important intermediate steps, and conclusions.",
        "5. Flag arithmetic/algebra/proof gaps separately from notation or exposition issues.",
        "6. Do not rewrite a full solution unless the user asks; focus on actionable correctness feedback.",
        "7. Assign an honest confidence score from 0.0 to 1.0.",
        "8. If confidence is below 0.6, recommend human/manual review before submission.",
        "9. In the conversation, tell the user what is inaccurate, incomplete, or needs revision; do not stop after reporting this artifact path.",
        "",
        "## Required Agent Output Format",
        "",
        "- Overall verdict: likely correct / minor issues / needs revision / cannot determine",
        "- Confidence: 0.0-1.0",
        "- Per-problem review table: problem, status, evidence, issues, suggested fix",
        "- Submission recommendation: submit / revise first / ask instructor or human reviewer",
        "",
        "## Assignment Prompt",
        "",
        prompt or "_No prompt text was provided. Ask the user for the assignment prompt before doing correctness review._",
        "",
        "## Student Solution",
        "",
        solution or "_No solution text was provided._",
        "",
        "## Reference Answer",
        "",
        reference or "_No reference answer provided. Use agent-drafted grading basis only._",
        "",
        "## Rubric / Grading Notes",
        "",
        rubric or "_No rubric provided._",
    ]
    artifact_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    readiness = []
    if not prompt:
        readiness.append("Prompt text is missing; ask the user for the assignment prompt.")
    if not solution:
        readiness.append("Student solution text is missing or unreadable.")
    if not reference and not rubric:
        readiness.append(
            "No reference answer or rubric is available; agent review should use low-to-medium confidence."
        )
    if not readiness:
        readiness.append("Artifact has prompt and solution context.")

    return (
        "## Solution Review Artifact Prepared\n\n"
        f"- Artifact: `{artifact_path}`\n"
        f"- Reference status: {reference_status}\n"
        "- Next step: the agent should read this artifact and perform the correctness review using the required output format.\n\n"
        "### Readiness Notes\n"
        + "\n".join(f"- {item}" for item in readiness)
        + "\n\n### In-Chat Review Prompt\n"
        + "Ask the agent to read the artifact and answer directly in chat with:\n"
        + "- What is likely correct?\n"
        + "- What is inaccurate, incomplete, or needs revision?\n"
        + "- Per-problem suggested fixes.\n"
        + "- Whether the student should submit or revise first.\n"
    )


def review_solution_for_chat(
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
    """Return a chat-ready review scaffold plus an artifact for deeper agent review."""
    artifact_result = prepare_solution_review_artifact(
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
    quick_review = review_solution_correctness(
        assignment_title,
        solution_path=solution_path,
        solution_text=solution_text,
        assignment_text=assignment_text,
        assignment_path=assignment_path,
        reference_text=reference_text,
        reference_path=reference_path,
        rubric_text=rubric_text,
    )
    chat_summary = _chat_review_summary(quick_review)

    return (
        "## Chat-Ready Solution Review\n\n"
        "This output is intended to be shown directly to the user. The quick review "
        "below lists automatically detected issues; the artifact gives the agent "
        "the full context needed to reason problem-by-problem and explain what to fix.\n\n"
        f"{chat_summary}\n\n"
        f"{artifact_result}\n\n"
        "## Automatically Detected Review Signals\n\n"
        f"{quick_review}\n\n"
        "## Required Follow-Up In The Conversation\n\n"
        "- Read the artifact.\n"
        "- Derive or verify the expected answer for each problem.\n"
        "- Compare the student's actual steps and final answers against that expectation.\n"
        "- Report concrete inaccuracies and suggested edits directly in chat; do not only return the artifact path.\n"
        "- If the expected solution cannot be derived confidently, say so and ask for a reference/rubric or human review.\n"
    )


def prepare_multi_agent_review_packet(
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
    """Prepare solver/reviewer/resolution packets for host-agent orchestration."""
    solution = _collect_text(solution_text, solution_path)
    prompt = _collect_text(assignment_text, assignment_path)
    reference = _collect_text(reference_text, reference_path)
    rubric = _plain(rubric_text)

    base_dir = Path(output_dir or "canvas-mcp-reviews").expanduser()
    if not output_dir and DEFAULT_DOWNLOAD_DIR:
        base_dir = Path(DEFAULT_DOWNLOAD_DIR).expanduser() / "reviews"
    base_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = (
        base_dir / f"{_safe_slug(assignment_title or 'assignment')}-multi-agent-review.md"
    )

    reference_status = "user-provided reference answer" if reference else "missing"
    if rubric and not reference:
        reference_status = "rubric-only fallback"
    elif reference and rubric:
        reference_status = "user-provided reference answer plus rubric"

    title = assignment_title.strip() or "Canvas Assignment"
    lines = [
        f"# Multi-Agent Review Packet: {title}",
        "",
        "This packet is for a host assistant such as Codex or Claude that can run multiple agents.",
        "MCP cannot directly spawn Codex/Claude subagents; it prepares the evidence and instructions.",
        "",
        "## Review Contract",
        "",
        f"- Assignment title: {title}",
        f"- Solution source: `{solution_path}`" if solution_path else "- Solution source: inline text",
        f"- Prompt source: `{assignment_path}`" if assignment_path else "- Prompt source: inline text or missing",
        f"- Reference source: {reference_status}",
        "- Goal: catch correctness errors before the user submits completed work.",
        "- The host assistant must report concrete issues in chat, not only return this artifact path.",
        "",
        "## Host-Agent Workflow",
        "",
        "1. Read the assignment prompt, student solution, optional reference, and rubric below.",
        "2. Start a solver agent to independently solve or verify the work.",
        "3. Start a reviewer agent with the same context but without telling it to defer to the solver.",
        "4. Compare the solver and reviewer outputs problem by problem.",
        "5. If they agree, give the user a final consensus with confidence and any caveats.",
        "6. If they disagree, send the disputed items back to the solver for revision or defense.",
        "7. After the solver responds, make a final decision and tell the user exactly what to change.",
        "8. If confidence remains low, ask for a reference answer, rubric, instructor note, or human review before submission.",
        "",
        "## Solver Agent Packet",
        "",
        "You are the solver/checker. Derive the expected answer independently from the prompt.",
        "Use the reference/rubric if provided, but do not assume the student's answer is correct.",
        "Return a concise table with problem, expected result, student result, status, and fix if needed.",
        "Show enough reasoning to make arithmetic, definitions, and conclusion checks auditable.",
        "",
        "## Reviewer Agent Packet",
        "",
        "You are the independent reviewer. Be skeptical of arithmetic, rounding, critical values, signs, units, and wording.",
        "Do not simply agree with the solver. Identify any answer you would change and explain why.",
        "If an answer is acceptable under multiple conventions, state the convention and preferred final form.",
        "Return disputed items first, then accepted items.",
        "",
        "## Disagreement Resolution Packet",
        "",
        "If the reviewer disagrees with the solver, send the disputed items back to the solver with the reviewer evidence.",
        "The solver must either revise the final answer or defend the original answer with a clear convention/source.",
        "The host assistant then decides the final answer and tells the user the exact edit to make.",
        "",
        "## Required Final Chat Output",
        "",
        "- Overall recommendation: submit / revise first / cannot determine.",
        "- Accepted answers: list items that both agents accept.",
        "- Disputed or revised answers: list original answer, reviewer concern, final consensus, and exact replacement.",
        "- Confidence: high / medium / low, with one short reason.",
        "- Submission note: remind the user no submission should be made unless they explicitly confirm.",
        "",
        "## Assignment Prompt",
        "",
        prompt or "_No prompt text was provided. Ask the user for the assignment prompt before review._",
        "",
        "## Student Solution",
        "",
        solution or "_No solution text was provided._",
        "",
        "## Reference Answer",
        "",
        reference or "_No reference answer provided. Use independent derivation and lower confidence._",
        "",
        "## Rubric / Grading Notes",
        "",
        rubric or "_No rubric provided._",
    ]
    artifact_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    readiness = []
    if not prompt:
        readiness.append("Prompt text is missing; the host assistant should ask for it.")
    if not solution:
        readiness.append("Student solution text is missing or unreadable.")
    if not reference and not rubric:
        readiness.append(
            "No reference answer or rubric is available; use independent derivation and report confidence honestly."
        )
    if not readiness:
        readiness.append("Prompt and solution context are present.")

    return (
        "## Multi-Agent Review Packet Prepared\n\n"
        f"- Artifact: `{artifact_path}`\n"
        "- Host-agent workflow required: spawn or use a solver agent, spawn an independent reviewer agent, then resolve disagreements before answering the user.\n"
        "- Important: MCP cannot directly spawn Codex/Claude subagents; the calling assistant must run the agents and report the consensus in chat.\n\n"
        "### Readiness Notes\n"
        + "\n".join(f"- {item}" for item in readiness)
    )


def _chat_review_summary(quick_review: str) -> str:
    issues = _section_bullets(quick_review, "Possible Correctness Issues")
    warnings = _section_bullets(quick_review, "Warnings")
    verdict = _section_bullets(quick_review, "Verdict")

    lines = [
        "## User-Facing Chat Summary",
        "",
        "Use this as the starting point for the answer shown in chat.",
        "",
    ]
    if verdict:
        lines.append("### Current Automated Verdict")
        lines.extend(verdict)
        lines.append("")
    if issues:
        lines.append("### Parts That May Be Inaccurate Or Need Revision")
        lines.extend(issues)
        lines.append("")
    else:
        lines.append("### Parts That May Be Inaccurate Or Need Revision")
        lines.append("- No specific mismatch was automatically detected.")
        lines.append("")
    if warnings:
        lines.append("### Additional Checks To Tell The User")
        lines.extend(warnings)
        lines.append("")
    lines.extend(
        [
            "### Important",
            "- Automated signals are not enough for a final correctness judgment.",
            "- The calling assistant should still read the artifact and give per-problem feedback directly in the conversation.",
        ]
    )
    return "\n".join(lines)


def _section_bullets(markdown: str, heading: str) -> list[str]:
    lines = markdown.splitlines()
    start = None
    marker = f"### {heading}"
    for index, line in enumerate(lines):
        if line.strip() == marker:
            start = index + 1
            break
    if start is None:
        return []

    bullets: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("### "):
            break
        if stripped.startswith("- "):
            bullets.append(stripped)
    return bullets


def make_practice_version(
    assignment_title: str,
    assignment_text: str | None,
    output_path: str | None = None,
) -> str:
    """Create a similar-but-not-identical practice prompt plan."""
    title = assignment_title.strip() or "Canvas Homework"
    lines = [
        f"# {title} Practice Version",
        "",
        "This is a similar but not identical practice version for studying.",
        "It is not meant to be submitted for the original assignment.",
        "",
    ]
    for number, body in _questions(assignment_text):
        lower = body.lower()
        lines.extend([f"## Practice Problem {number}", ""])
        if "least square" in lower or "regression" in lower:
            lines.extend(
                [
                    "Use a different small least squares regression data summary with the same estimator formulas.",
                    "Practice identifying x-bar, y-bar, Sxx, Sxy, and the fitted line.",
                ]
            )
        elif "confidence interval" in lower or "prediction interval" in lower:
            lines.extend(
                [
                    "Use a different prediction point and ask for the matching interval.",
                    "Practice deciding whether the interval is for a mean or an individual value.",
                ]
            )
        else:
            lines.extend(
                [
                    "Rewrite the problem with different labels and numbers.",
                    "Solve the practice version before returning to the original.",
                ]
            )
        lines.append("")

    result = "\n".join(lines).rstrip() + "\n"
    if output_path:
        Path(output_path).expanduser().write_text(result, encoding="utf-8")
        return f"Practice version written to `{Path(output_path).expanduser()}`."
    return result


def extract_due_and_submission_target(assignment_details: str) -> str:
    """Extract deadline and where the finished work should be submitted."""
    text = _plain(assignment_details)
    due_match = re.search(r"(?mi)^-\s*Due:\s*(.+)$", text)
    due = due_match.group(1).strip() if due_match else "Not found"
    lower = text.lower()
    if "gradescope" in lower:
        target = "Gradescope"
    elif "canvas" in lower or "submission types:" in lower:
        target = "Canvas"
    else:
        target = "Unknown"

    return (
        "## Due Date And Submission Target\n\n"
        f"- Due: {due}\n"
        f"- Submission target: {target}\n"
        "- Always review the assignment page before final submission.\n"
    )


def prepare_homework_help_pack(
    course_id: str,
    assignment_id: str,
    output_dir: str | None = None,
    allow_mismatched_files: bool = False,
) -> str:
    """Prepare a local folder with homework support artifacts."""
    workspace_result = prepare_assignment_workspace(
        course_id,
        assignment_id,
        output_dir=output_dir,
        download_linked_files=True,
        max_files=20,
        allow_mismatched_files=allow_mismatched_files,
    )
    if "### User Confirmation Required" in workspace_result and not allow_mismatched_files:
        return (
            "## Homework Help Pack Awaiting Confirmation\n\n"
            "The Canvas assignment appears to link to a file whose homework/assignment "
            "number does not match the assignment title. Before downloading or using that "
            "file, ask the user to confirm whether the Canvas link is intentional. If the "
            "user confirms, rerun this tool with `allow_mismatched_files=True`.\n\n"
            f"{workspace_result}"
        )
    source_result = resolve_assignment_source(course_id, assignment_id)
    if _workspace_has_no_downloads(workspace_result) and _source_needs_clarification(
        source_result
    ):
        return (
            "## Homework Help Pack Awaiting Assignment Source\n\n"
            "Canvas did not provide a clear usable file for this assignment, and the "
            "source resolver found that the real prompt may be elsewhere. Ask the user "
            "for the real assignment source, or inspect the linked GitHub/Gradescope "
            "source before generating a help pack.\n\n"
            f"{source_result}\n\n"
            f"{workspace_result}"
        )
    details = get_assignment_details(course_id, assignment_id, max_description_chars=50000)
    title = _title_from_details(details)
    folder = _folder_from_workspace_result(workspace_result)
    if folder is None:
        return (
            "## Homework Help Pack\n\n"
            "Could not infer workspace folder from the assignment workspace result.\n\n"
            f"{workspace_result}\n"
        )

    folder.mkdir(parents=True, exist_ok=True)
    template_path = folder / "homework_template.md"
    hints_path = folder / "hint_pack.md"
    practice_path = folder / "practice_version.md"
    target_path = folder / "submission_target.md"

    assignment_text = _workspace_text(folder) or details
    create_homework_template(title, assignment_text, str(template_path))
    generate_hint_pack(title, assignment_text, str(hints_path))
    make_practice_version(title, assignment_text, str(practice_path))
    target_path.write_text(extract_due_and_submission_target(details), encoding="utf-8")

    return (
        "## Homework Help Pack Prepared\n\n"
        f"- Folder: `{folder}`\n"
        f"- Assignment details: `{folder / 'assignment.md'}`\n"
        f"- Template: `{template_path}`\n"
        f"- Hint pack: `{hints_path}`\n"
        f"- Practice version: `{practice_path}`\n"
        f"- Submission target: `{target_path}`\n\n"
        "These files support planning, drafting, review, and submission preparation."
    )


def _title_from_details(details: str) -> str:
    for line in details.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Canvas Homework"


def _folder_from_workspace_result(workspace_result: str) -> Path | None:
    match = re.search(r"- Folder: `([^`]+)`", workspace_result)
    if not match:
        return None
    return Path(match.group(1)).expanduser()


def _workspace_has_no_downloads(workspace_result: str) -> bool:
    return "- Downloaded files: 0" in workspace_result


def _source_needs_clarification(source_result: str) -> bool:
    waiting_headers = [
        "## Assignment Source Likely Gradescope",
        "## Assignment Source Likely GitHub",
        "## Assignment Source Needed From User",
        "## Assignment Source Needs User Confirmation",
    ]
    return any(header in source_result for header in waiting_headers)


def _workspace_text(folder: Path) -> str:
    chunks: list[str] = []
    seen: set[str] = set()
    generated = {
        "homework_template.md",
        "hint_pack.md",
        "MISMATCH_WARNING.md",
        "practice_version.md",
        "submission_target.md",
    }
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.name in generated:
            continue
        suffix = path.suffix.lower()
        text = ""
        if suffix in {".md", ".txt"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
        elif suffix == ".pdf":
            text = _pdf_text(path)
        key = re.sub(r"\s+", " ", text).strip()
        if text and key not in seen:
            seen.add(key)
            chunks.append(text)
    return "\n\n".join(chunks).strip()


def _pdf_text(path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _file_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix in {".txt", ".md", ".tex", ".rmd"}:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ""
    return ""


def _collect_text(inline_text: str | None, file_path: str | None) -> str:
    chunks = []
    inline = _plain(inline_text)
    if inline:
        chunks.append(inline)
    if file_path:
        path = Path(file_path).expanduser()
        text = _file_text(path)
        if text:
            chunks.append(text)
    return "\n\n".join(chunks).strip()


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip()).strip("-")
    return slug[:80] or "assignment"


def _problem_numbers(text: str | None) -> list[str]:
    normalized = _plain(text)
    if not normalized:
        return []
    found = set(re.findall(r"(?im)^\s*(?:problem|question)\s+(\d+)\b", normalized))
    found.update(re.findall(r"(?m)^\s*(\d+)[.)]\s+", normalized))
    return sorted(found, key=lambda value: int(value))


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:160]
    return ""


def _looks_like_solution(text: str, filename: str) -> bool:
    lower = f"{filename}\n{text}".lower()
    solution_markers = [
        "solution",
        "solutions",
        "answer",
        "therefore",
        "hence",
        "thus",
        "we have",
        "boxed",
    ]
    return any(marker in lower for marker in solution_markers)


def _looks_prompt_only(submission_text: str, prompt_text: str, filename: str) -> bool:
    lower = submission_text.lower()
    prompt_markers = ["due:", "points", "show that", "derive", "compute"]
    solution_like = _looks_like_solution(submission_text, filename)
    if prompt_text and _line_overlap_ratio(prompt_text, submission_text) > 0.85:
        return True
    return not solution_like and sum(marker in lower for marker in prompt_markers) >= 3


def _line_overlap_ratio(prompt_text: str, submission_text: str) -> float:
    prompt_lines = {
        re.sub(r"\s+", " ", line).strip().lower()
        for line in prompt_text.splitlines()
        if len(re.sub(r"\s+", " ", line).strip()) >= 25
    }
    submission_lines = {
        re.sub(r"\s+", " ", line).strip().lower()
        for line in submission_text.splitlines()
        if len(re.sub(r"\s+", " ", line).strip()) >= 25
    }
    if not prompt_lines:
        return 0.0
    return len(prompt_lines & submission_lines) / len(prompt_lines)


def _add_internal_correctness_checks(solution: str, warnings: list[str]) -> None:
    lower = solution.lower()
    if "therefore" not in lower and "hence" not in lower and "thus" not in lower:
        warnings.append("Solution has few conclusion markers; check final answers are stated clearly.")
    if "=" not in solution and any(word in lower for word in ["compute", "derive", "risk", "estimate"]):
        warnings.append("Solution contains few equations; verify calculations are shown.")
    if any(marker in lower for marker in ["todo", "???", "tbd", "unfinished"]):
        warnings.append("Solution contains unfinished-work markers such as TODO/TBD/???.")


def _reference_answer_checks(solution: str, reference: str) -> list[str]:
    if not reference:
        return []
    issues = []
    solution_sections = _sections_by_problem(solution)
    reference_sections = _sections_by_problem(reference)
    if not reference_sections:
        reference_sections = {"all": reference}
        solution_sections = {"all": solution}

    for number, reference_section in reference_sections.items():
        solution_section = solution_sections.get(number, "")
        if not solution_section:
            issues.append(f"Problem {number}: no matching solution section found.")
            continue
        missing_lines = _missing_reference_answer_lines(solution_section, reference_section)
        if missing_lines:
            preview = "; ".join(missing_lines[:3])
            label = f"Problem {number}" if number != "all" else "Solution"
            issues.append(
                f"{label}: Missing or mismatched reference answer line(s): {preview}"
            )
    return issues


def _reference_overlap_section(solution: str, reference: str) -> list[str]:
    solution_terms = _important_terms(solution)
    reference_terms = _important_terms(reference)
    if not reference_terms:
        return []
    overlap = sorted(solution_terms & reference_terms)
    ratio = len(overlap) / len(reference_terms)
    return [
        "### Reference Comparison",
        f"- Important reference terms matched: {len(overlap)}/{len(reference_terms)} ({ratio:.0%}).",
        f"- Matched sample: {', '.join(overlap[:12]) or '(none)'}",
        "",
    ]


def _rubric_term_checks(solution: str, rubric: str) -> list[str]:
    rubric_terms = _important_terms(rubric)
    solution_terms = _important_terms(solution)
    missing = sorted(rubric_terms - solution_terms)
    if not missing:
        return []
    return [
        "Rubric terms not clearly present in the solution: "
        + ", ".join(missing[:12])
        + "."
    ]


def _sections_by_problem(text: str) -> dict[str, str]:
    matches = list(
        re.finditer(r"(?im)^\s*(?:problem|question)\s+(\d+)\b.*$", text)
    )
    if not matches:
        return {}
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end].strip()
    return sections


def _missing_reference_answer_lines(solution_section: str, reference_section: str) -> list[str]:
    solution_normalized = _normalize_math_text(solution_section)
    missing = []
    for line in _answer_like_lines(reference_section):
        normalized_line = _normalize_math_text(line)
        if normalized_line and normalized_line not in solution_normalized:
            missing.append(line.strip()[:180])
    return missing


def _answer_like_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if len(line) < 8:
            continue
        if any(marker in lower for marker in ["final", "answer", "boxed"]):
            lines.append(line)
            continue
        if "=" in line and any(char.isdigit() for char in line):
            lines.append(line)
    return lines[:20]


def _normalize_math_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"[^a-z0-9=+\-*/().,_{}]", "", text)
    return text


def _important_terms(text: str) -> set[str]:
    stop = {
        "problem",
        "solution",
        "therefore",
        "hence",
        "where",
        "using",
        "show",
        "derive",
        "compute",
        "final",
        "answer",
        "with",
        "that",
        "this",
        "from",
        "have",
    }
    words = {
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", text)
        if word.lower() not in stop
    }
    formulas = set(re.findall(r"[A-Za-z]\([^)]{1,40}\)\s*=\s*[^\s,;]{2,80}", text))
    return words | {formula.lower() for formula in formulas}


def _finish_submission_review(
    lines: list[str],
    issues: list[str],
    warnings: list[str],
    output_path: str | None,
) -> str:
    if issues:
        verdict = "Needs attention before submission"
    elif warnings:
        verdict = "Looks mostly ready, with warnings"
    else:
        verdict = "Looks ready for submission"
    lines.extend(["### Verdict", f"- {verdict}", ""])
    if issues:
        lines.append("### Blocking Issues")
        lines.extend(f"- {issue}" for issue in issues)
        lines.append("")
    if warnings:
        lines.append("### Warnings")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    lines.append(
        "This review checks file/readability/coverage signals. It does not guarantee "
        "that every mathematical step or final answer is correct."
    )
    result = "\n".join(lines).rstrip() + "\n"
    if output_path:
        Path(output_path).expanduser().write_text(result, encoding="utf-8")
        return f"Submission review written to `{Path(output_path).expanduser()}`."
    return result


def _finish_correctness_review(
    lines: list[str],
    issues: list[str],
    warnings: list[str],
    confidence: str,
    output_path: str | None,
) -> str:
    if issues:
        verdict = "Needs correctness review"
    elif warnings:
        verdict = "No obvious correctness issues found, but review warnings remain"
    else:
        verdict = "No obvious correctness issues found"
    lines.extend(["### Verdict", f"- {verdict}", f"- Confidence: {confidence}", ""])
    if issues:
        lines.append("### Possible Correctness Issues")
        lines.extend(f"- {issue}" for issue in issues)
        lines.append("")
    if warnings:
        lines.append("### Warnings")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    lines.append(
        "This tool can catch missing sections, missing reference conclusions, and "
        "surface-level mismatches. It is not an official grade and cannot guarantee "
        "that every proof step is correct."
    )
    result = "\n".join(lines).rstrip() + "\n"
    if output_path:
        Path(output_path).expanduser().write_text(result, encoding="utf-8")
        return f"Correctness review written to `{Path(output_path).expanduser()}`."
    return result

"""Learning-assistance tools that avoid generating submit-ready answers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from canvas_mcp.tools.assignments import get_assignment_details, prepare_assignment_workspace
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
    """Create a student-fillable homework template without solving the work."""
    title = assignment_title.strip() or "Canvas Homework"
    lines = [
        f"# {title} Template",
        "",
        "This template intentionally leaves solution work blank.",
        "Use it to organize your own derivations, calculations, and explanations.",
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
    """Generate conceptual hints and checklists, not final answers."""
    title = assignment_title.strip() or "Canvas Homework"
    lines = [
        f"# {title} Hint Pack",
        "",
        "These are study hints, not final answers. Use them to guide your own work.",
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
    """Prepare a local folder with safe homework support artifacts."""
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
        "These files are designed to support student-authored work, not replace it."
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

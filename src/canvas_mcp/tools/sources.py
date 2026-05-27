"""Assignment source resolution across Canvas, GitHub, and Gradescope."""

from __future__ import annotations

from urllib.parse import urlparse

from canvas_mcp.auth import AuthError, get_client
from canvas_mcp.client import CanvasApiError
from canvas_mcp.formatting import clean_html
from canvas_mcp.tools.assignments import (
    _assignment_resource_mismatch,
    _downloadable_link,
    _extract_links,
)


def resolve_assignment_source(
    course_id: str,
    assignment_id: str,
    user_source_url: str | None = None,
    user_source_kind: str | None = None,
) -> str:
    """Resolve where the real assignment prompt/files should come from."""
    if user_source_url:
        return _provided_source_response(user_source_url, user_source_kind)

    try:
        client = get_client()
        assignment = client.get(
            f"/courses/{course_id}/assignments/{assignment_id}",
            params=[("include[]", "submission"), ("include[]", "all_dates")],
        )
    except AuthError as e:
        return f"Authentication error: {e}"
    except CanvasApiError as e:
        return f"Canvas API error: {e}"
    except Exception as e:
        return f"Error resolving assignment source: {e}"

    return resolve_assignment_source_from_canvas(
        assignment.get("name") or "Canvas Assignment",
        assignment.get("description"),
        client.base_url,
    )


def resolve_assignment_source_from_canvas(
    assignment_name: str,
    description_html: str | None,
    base_url: str,
) -> str:
    """Classify assignment source hints found on a Canvas assignment page."""
    links = _extract_links(description_html, base_url)
    plain = clean_html(description_html, 12000).lower()

    gradescope_links = [link for link in links if _is_gradescope_url(link["url"])]
    github_links = [link for link in links if _is_github_url(link["url"])]
    canvas_files: list[dict[str, str]] = []
    mismatches: list[str] = []

    for link in links:
        if _is_gradescope_url(link["url"]) or _is_github_url(link["url"]):
            continue
        mismatch = _assignment_resource_mismatch(assignment_name, link.get("text"))
        if mismatch:
            mismatches.append(mismatch)
            continue
        if _downloadable_link(link["url"]):
            canvas_files.append(link)

    if gradescope_links or "gradescope" in plain:
        return _gradescope_source_response(assignment_name, gradescope_links)

    if github_links:
        return _github_source_response(assignment_name, github_links)

    if canvas_files:
        lines = [
            "## Assignment Source Looks Usable On Canvas",
            "",
            f"- Assignment: {assignment_name}",
            "- Canvas has downloadable linked files that do not obviously mismatch the assignment title.",
            "",
            "### Canvas Files",
        ]
        lines.extend(_format_links(canvas_files))
        if mismatches:
            lines.extend(["", "### Also Needs User Confirmation"])
            lines.extend(f"- {item}" for item in mismatches)
        return "\n".join(lines)

    if _looks_like_canvas_prompt(plain):
        return "\n".join(
            [
                "## Assignment Source Looks Usable On Canvas",
                "",
                f"- Assignment: {assignment_name}",
                "- Canvas contains substantial assignment instructions even though no separate file was found.",
                "- Use the Canvas assignment text as the prompt after reviewing it.",
            ]
        )

    if mismatches:
        lines = [
            "## Assignment Source Needs User Confirmation",
            "",
            f"- Assignment: {assignment_name}",
            "- Canvas links at least one file whose number appears to disagree with the assignment title.",
            "- Ask the user whether the Canvas link is intentional before downloading or using it.",
            "- If confirmed, rerun the workspace/help tool with `allow_mismatched_files=True`.",
            "",
            "### Mismatches",
        ]
        lines.extend(f"- {item}" for item in mismatches)
        lines.extend(["", _source_question_block()])
        return "\n".join(lines)

    return "\n".join(
        [
            "## Assignment Source Needed From User",
            "",
            f"- Assignment: {assignment_name}",
            "- Canvas does not expose a clear downloadable assignment file, GitHub link, or Gradescope link.",
            "",
            _source_question_block(),
        ]
    )


def _provided_source_response(source_url: str, source_kind: str | None) -> str:
    kind = (source_kind or _classify_url(source_url)).strip().lower()
    if kind == "gradescope":
        return _gradescope_source_response(
            "User-provided assignment source",
            [{"text": source_url, "url": source_url}],
        )
    if kind == "github":
        return _github_source_response(
            "User-provided assignment source",
            [{"text": source_url, "url": source_url}],
        )
    if kind in {"file", "local", "local_file"}:
        return "\n".join(
            [
                "## Assignment Source Provided As Local File",
                "",
                f"- Source: `{source_url}`",
                "- Use this local file/path as the assignment prompt after verifying it matches the Canvas assignment.",
            ]
        )
    return "\n".join(
        [
            "## Assignment Source Provided",
            "",
            f"- Source kind: {source_kind or 'unknown'}",
            f"- Source: {source_url}",
            "- Verify this source matches the Canvas assignment before preparing or submitting work.",
        ]
    )


def _gradescope_source_response(
    assignment_name: str,
    links: list[dict[str, str]],
) -> str:
    lines = [
        "## Assignment Source Likely Gradescope",
        "",
        f"- Assignment: {assignment_name}",
        "- Canvas mentions Gradescope, so the actual prompt/submission target may be on Gradescope.",
        "- Next, use the Gradescope bridge tools to log in and inspect the matching Gradescope course/assignment.",
        "",
        "### Recommended Next Tools",
        "- `tool_gradescope_bridge_status(check_login=True)`",
        "- `tool_gradescope_list_courses()`",
        "- `tool_gradescope_list_assignments(course_id=...)`",
        "- `tool_gradescope_get_assignment_details(course_id=..., assignment_id=...)`",
    ]
    if links:
        lines.extend(["", "### Gradescope Links"])
        lines.extend(_format_links(links))
    else:
        lines.extend(["", "### Missing Link"])
        lines.append("- Canvas mentions Gradescope but does not expose a clear Gradescope URL.")
        lines.append("- Ask the user which Gradescope course/assignment corresponds to this Canvas item.")
    return "\n".join(lines)


def _github_source_response(assignment_name: str, links: list[dict[str, str]]) -> str:
    lines = [
        "## Assignment Source Likely GitHub",
        "",
        f"- Assignment: {assignment_name}",
        "- Canvas points to a GitHub source, so the assignment prompt may live outside Canvas.",
        "- Inspect or clone the linked repository/file before preparing a workspace.",
        "",
        "### GitHub Links",
    ]
    lines.extend(_format_links(links))
    return "\n".join(lines)


def _source_question_block() -> str:
    return "\n".join(
        [
            "### Ask The User",
            "- Where is the actual assignment prompt?",
            "- Acceptable answers: a GitHub URL, a Gradescope course/assignment, a Canvas file confirmation, or a local file path.",
        ]
    )


def _format_links(links: list[dict[str, str]]) -> list[str]:
    return [f"- [{link.get('text') or link['url']}]({link['url']})" for link in links]


def _classify_url(url: str) -> str:
    if _is_gradescope_url(url):
        return "gradescope"
    if _is_github_url(url):
        return "github"
    return "unknown"


def _is_gradescope_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "gradescope.com" or host.endswith(".gradescope.com")


def _is_github_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in {"github.com", "raw.githubusercontent.com"} or host.endswith(
        ".githubusercontent.com"
    )


def _looks_like_canvas_prompt(plain_text: str) -> bool:
    text = " ".join(plain_text.split())
    if len(text) >= 500:
        return True
    prompt_markers = [
        "problem",
        "question",
        "show that",
        "prove that",
        "calculate",
        "derive",
        "write out",
    ]
    numbered_items = any(f"{number}." in text for number in range(1, 5))
    return numbered_items and any(marker in text for marker in prompt_markers)

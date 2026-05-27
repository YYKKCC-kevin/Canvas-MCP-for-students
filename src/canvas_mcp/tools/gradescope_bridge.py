"""Optional bridge to a local gradescope-mcp installation."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv


def gradescope_bridge_status(
    gradescope_mcp_path: str | None = None,
    check_login: bool = False,
) -> str:
    """Check whether a local gradescope-mcp can be imported and used."""
    ready = _prepare_gradescope_bridge(gradescope_mcp_path)
    if not ready.ok:
        return ready.message

    email = os.environ.get("GRADESCOPE_EMAIL", "").strip()
    password = os.environ.get("GRADESCOPE_PASSWORD", "").strip()
    lines = [
        "## Gradescope Bridge Ready",
        "",
        f"- gradescope-mcp path: `{ready.path}`",
        f"- GRADESCOPE_EMAIL: {'set' if email else 'missing'}",
        f"- GRADESCOPE_PASSWORD: {'set' if password else 'missing'}",
    ]
    if not email or not password:
        lines.append(
            "- Add Gradescope credentials to `.env` or to the linked gradescope-mcp `.env` before login."
        )
        return "\n".join(lines)

    if check_login:
        try:
            from gradescope_mcp.tools.courses import list_courses

            preview = list_courses()
        except Exception as e:
            return "\n".join(lines + ["", f"Login check failed: {e}"])
        lines.extend(["", "### Login Check", preview])
    return "\n".join(lines)


def gradescope_list_courses(gradescope_mcp_path: str | None = None) -> str:
    """List Gradescope courses via a local gradescope-mcp installation."""
    return _call_gradescope_tool(
        "gradescope_mcp.tools.courses",
        "list_courses",
        gradescope_mcp_path,
    )


def gradescope_list_assignments(
    course_id: str,
    gradescope_mcp_path: str | None = None,
) -> str:
    """List Gradescope assignments for a course via gradescope-mcp."""
    return _call_gradescope_tool(
        "gradescope_mcp.tools.assignments",
        "get_assignments",
        gradescope_mcp_path,
        course_id,
    )


def gradescope_get_assignment_details(
    course_id: str,
    assignment_id: str,
    gradescope_mcp_path: str | None = None,
) -> str:
    """Get one Gradescope assignment's details via gradescope-mcp."""
    return _call_gradescope_tool(
        "gradescope_mcp.tools.assignments",
        "get_assignment_details",
        gradescope_mcp_path,
        course_id,
        assignment_id,
    )


class _BridgeStatus:
    def __init__(self, ok: bool, message: str, path: Path | None = None) -> None:
        self.ok = ok
        self.message = message
        self.path = path


def _call_gradescope_tool(
    module_name: str,
    function_name: str,
    gradescope_mcp_path: str | None,
    *args: str,
) -> str:
    ready = _prepare_gradescope_bridge(gradescope_mcp_path)
    if not ready.ok:
        return ready.message
    try:
        module = __import__(module_name, fromlist=[function_name])
        fn: Callable[..., str] = getattr(module, function_name)
        return fn(*args)
    except Exception as e:
        return f"Error calling gradescope-mcp `{function_name}`: {e}"


def _prepare_gradescope_bridge(gradescope_mcp_path: str | None = None) -> _BridgeStatus:
    path = _resolve_gradescope_mcp_path(gradescope_mcp_path)
    if path is None:
        return _BridgeStatus(
            False,
            "\n".join(
                [
                    "## Gradescope Bridge Not Configured",
                    "",
                    "- Set `GRADESCOPE_MCP_PATH` to your local gradescope-mcp folder, or clone it at `~/gradescope-mcp`.",
                    "- Add `GRADESCOPE_EMAIL` and `GRADESCOPE_PASSWORD` to `.env` or to the gradescope-mcp `.env`.",
                ]
            ),
        )

    dotenv_path = path / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=False)

    src_path = path / "src"
    if not src_path.exists():
        return _BridgeStatus(
            False,
            f"Gradescope bridge path `{path}` does not contain a `src` folder.",
        )
    src_string = str(src_path)
    if src_string not in sys.path:
        sys.path.insert(0, src_string)

    try:
        __import__("gradescope_mcp")
    except Exception as e:
        return _BridgeStatus(False, f"Could not import gradescope-mcp from `{path}`: {e}")

    return _BridgeStatus(True, "", path)


def _resolve_gradescope_mcp_path(path: str | None = None) -> Path | None:
    candidates = []
    if path:
        candidates.append(Path(path).expanduser())
    env_path = os.environ.get("GRADESCOPE_MCP_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(
        [
            Path.cwd().parent / "gradescope-mcp",
            Path.home() / "gradescope-mcp",
        ]
    )

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    return None

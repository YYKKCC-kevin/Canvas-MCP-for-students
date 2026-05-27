"""Formatting helpers for tool output."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from typing import Any

from bs4 import BeautifulSoup


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_No rows._"
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return "\n".join(out)


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("\n", " ").replace("|", "\\|")


def clean_html(html: str | None, max_chars: int | None = None) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    for tag in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4"]):
        tag.append("\n")

    text = soup.get_text(" ")
    text = unescape(text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()
    if max_chars and len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def parse_canvas_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def human_datetime(value: str | None) -> str:
    dt = parse_canvas_datetime(value)
    if dt is None:
        return value or ""
    local = dt.astimezone()
    return local.strftime("%Y-%m-%d %H:%M %Z")


def due_status(due_at: str | None, submitted_at: str | None, excused: bool = False) -> str:
    if excused:
        return "excused"
    if submitted_at:
        return "submitted"
    due = parse_canvas_datetime(due_at)
    if due is None:
        return "undated"
    now = datetime.now(timezone.utc)
    if due.astimezone(timezone.utc) < now:
        return "overdue"
    return "open"

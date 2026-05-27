"""Authentication and client lifecycle for Canvas."""

from __future__ import annotations

import os
from pathlib import Path

from canvas_mcp.client import CanvasClient


class AuthError(Exception):
    """Raised when Canvas credentials are missing or invalid."""


_client: CanvasClient | None = None
_client_key: tuple[str, ...] | None = None


TOKEN_PLACEHOLDERS = {
    "paste_your_canvas_access_token_here",
    "your_canvas_access_token",
    "replace_me",
}


def get_client() -> CanvasClient:
    """Return a cached Canvas API client configured from environment variables."""
    global _client, _client_key

    base_url = os.environ.get("CANVAS_BASE_URL", "").strip()
    raw_token = (
        os.environ.get("CANVAS_ACCESS_TOKEN", "").strip()
        or os.environ.get("CANVAS_API_TOKEN", "").strip()
        or os.environ.get("CANVAS_TOKEN", "").strip()
    )
    token = "" if raw_token in TOKEN_PLACEHOLDERS else raw_token
    storage_state = os.environ.get("CANVAS_STORAGE_STATE", ".canvas-storage-state.json").strip()

    if not base_url:
        raise AuthError("Missing CANVAS_BASE_URL. Example: https://canvas.eee.uci.edu")

    if token:
        key = (base_url, "token", token)
        if _client is not None and _client_key == key:
            return _client
        _client = CanvasClient(base_url=base_url, token=token)
        _client_key = key
        return _client

    state_path = Path(storage_state).expanduser()
    if not state_path.exists():
        raise AuthError(
            "Missing Canvas auth. Either set CANVAS_ACCESS_TOKEN or run "
            "`canvas-mcp-login` after setting CANVAS_EMAIL and CANVAS_PASSWORD."
        )

    key = (base_url, "storage_state", str(state_path), str(state_path.stat().st_mtime_ns))
    if _client is not None and _client_key == key:
        return _client

    _client = CanvasClient(base_url=base_url, storage_state_path=str(state_path))
    _client_key = key
    return _client


def reset_client() -> None:
    """Clear the cached client, forcing env vars to be re-read next time."""
    global _client, _client_key
    _client = None
    _client_key = None

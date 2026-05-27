"""Authentication and client lifecycle for Canvas."""

from __future__ import annotations

import os

from canvas_mcp.client import CanvasClient


class AuthError(Exception):
    """Raised when Canvas credentials are missing or invalid."""


_client: CanvasClient | None = None
_client_key: tuple[str, str] | None = None


def get_client() -> CanvasClient:
    """Return a cached Canvas API client configured from environment variables."""
    global _client, _client_key

    base_url = os.environ.get("CANVAS_BASE_URL", "").strip()
    token = (
        os.environ.get("CANVAS_ACCESS_TOKEN", "").strip()
        or os.environ.get("CANVAS_API_TOKEN", "").strip()
        or os.environ.get("CANVAS_TOKEN", "").strip()
    )

    if not base_url:
        raise AuthError("Missing CANVAS_BASE_URL. Example: https://canvas.eee.uci.edu")
    if not token:
        raise AuthError("Missing CANVAS_ACCESS_TOKEN.")

    key = (base_url, token)
    if _client is not None and _client_key == key:
        return _client

    _client = CanvasClient(base_url=base_url, token=token)
    _client_key = key
    return _client


def reset_client() -> None:
    """Clear the cached client, forcing env vars to be re-read next time."""
    global _client, _client_key
    _client = None
    _client_key = None

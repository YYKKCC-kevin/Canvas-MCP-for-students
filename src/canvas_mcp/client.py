"""Small Canvas REST API client."""

from __future__ import annotations

import os
import json
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


class CanvasApiError(Exception):
    """Raised when Canvas returns a non-successful response."""


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        match = re.search(r"<([^>]+)>;\s*rel=\"next\"", part.strip())
        if match:
            return match.group(1)
    return None


@dataclass
class CanvasClient:
    base_url: str
    token: str | None = None
    storage_state_path: str | None = None
    timeout: int = 30
    max_pages: int = field(
        default_factory=lambda: int(os.environ.get("CANVAS_MAX_PAGES", "25"))
    )

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1/"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "canvas-mcp/0.1",
            }
        )
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        elif self.storage_state_path:
            self._load_storage_state(self.storage_state_path)

    def _load_storage_state(self, storage_state_path: str) -> None:
        path = Path(storage_state_path).expanduser()
        state = json.loads(path.read_text(encoding="utf-8"))
        for cookie in state.get("cookies", []):
            name = cookie.get("name")
            value = cookie.get("value")
            if not name or value is None:
                continue
            self.session.cookies.set(
                name,
                value,
                domain=cookie.get("domain"),
                path=cookie.get("path") or "/",
            )

    def url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(self.api_base, path_or_url.lstrip("/"))

    def request(self, method: str, path_or_url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.request(method, self.url(path_or_url), **kwargs)
        if response.status_code >= 400:
            detail = response.text[:800].replace("\n", " ")
            raise CanvasApiError(
                f"Canvas API {method} {path_or_url} failed "
                f"with status {response.status_code}: {detail}"
            )
        return response

    def get(self, path_or_url: str, params: Any | None = None) -> Any:
        response = self.request("GET", path_or_url, params=params)
        if not response.content:
            return None
        return response.json()

    def post_form(self, path_or_url: str, data: dict[str, Any]) -> Any:
        headers = {}
        if not self.token:
            csrf = self._csrf_token()
            if csrf:
                headers["X-CSRF-Token"] = csrf
        response = self.request("POST", path_or_url, data=data, headers=headers or None)
        if not response.content:
            return None
        return response.json()

    def _csrf_token(self) -> str | None:
        for cookie in self.session.cookies:
            if "csrf" in cookie.name.lower():
                return cookie.value
        return None

    def get_paginated(self, path_or_url: str, params: Any | None = None) -> list[Any]:
        results: list[Any] = []
        next_url: str | None = self.url(path_or_url)
        next_params = params

        for _ in range(self.max_pages):
            response = self.request("GET", next_url, params=next_params)
            payload = response.json()
            if isinstance(payload, list):
                results.extend(payload)
            else:
                results.append(payload)

            next_url = _next_link(response.headers.get("Link"))
            next_params = None
            if not next_url:
                break
        return results

    def download(self, url: str, max_bytes: int = 50 * 1024 * 1024) -> requests.Response:
        response = self.request("GET", url, stream=True)
        size = int(response.headers.get("Content-Length") or 0)
        if size > max_bytes:
            raise CanvasApiError(f"Refusing to download {size} bytes from {url}")
        return response

    def upload_submission_file(
        self,
        course_id: str,
        assignment_id: str,
        file_path: Path,
    ) -> int:
        """Upload a local file for a Canvas online_upload submission."""
        path = file_path.expanduser()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        init_payload = {
            "name": path.name,
            "size": str(path.stat().st_size),
            "content_type": content_type,
        }
        # Canvas requires multipart/form-data even for the upload-init metadata.
        init_response = self.request(
            "POST",
            f"/courses/{course_id}/assignments/{assignment_id}/submissions/self/files",
            files={key: (None, value) for key, value in init_payload.items()},
        )
        init = init_response.json()
        upload_url = init.get("upload_url")
        upload_params = init.get("upload_params") or {}
        if not upload_url:
            raise CanvasApiError("Canvas did not return upload_url for submission file.")

        with path.open("rb") as fh:
            upload_response = requests.post(
                upload_url,
                data=upload_params,
                files={"file": (path.name, fh, content_type)},
                timeout=self.timeout,
                allow_redirects=False,
            )
        if upload_response.status_code in {301, 302, 303, 307, 308}:
            location = upload_response.headers.get("Location")
            if not location:
                raise CanvasApiError("Canvas upload redirect did not include Location.")
            final = self.request("GET", location)
            payload = final.json()
        elif 200 <= upload_response.status_code < 300:
            payload = upload_response.json() if upload_response.content else {}
        else:
            detail = upload_response.text[:800].replace("\n", " ")
            raise CanvasApiError(
                f"Canvas file upload failed with status {upload_response.status_code}: {detail}"
            )

        file_id = payload.get("id") or payload.get("attachment", {}).get("id")
        if not file_id:
            raise CanvasApiError(f"Canvas upload response did not include file id: {payload}")
        return int(file_id)

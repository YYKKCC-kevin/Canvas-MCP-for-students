# Canvas MCP

Local MCP server for Canvas LMS. It is designed like a safer, cleaner cousin of the local Gradescope MCP: API-token authentication, read-only tools by default, and explicit confirmation for anything that can submit work.

## What It Can Do

- List active Canvas courses.
- Show upcoming, overdue, unsubmitted, or undated assignments with due dates.
- Query Canvas planner/todo items.
- Fetch full assignment details, including submission status and cleaned instructions.
- Prepare a local assignment workspace with `assignment.md` and optionally downloaded linked files.
- Submit online text or URL assignments only when `confirm_write=True`.

## Safety Model

This server helps Codex collect assignment context and prepare work. It does not silently submit anything. Submission tools return a dry-run confirmation unless `confirm_write=True` is provided.

For academic work, use the workspace tools to understand requirements, draft your own solution, run checks, and decide what to submit.

## Setup

1. Create a Canvas token in Canvas: `Account -> Settings -> Approved Integrations -> New Access Token`.
2. Copy `.env.example` to `.env`.
3. Fill in your Canvas credentials:

```bash
# Canvas credentials
CANVAS_BASE_URL=https://canvas.eee.uci.edu
CANVAS_ACCESS_TOKEN=paste_your_canvas_access_token_here
```

Canvas username/password are intentionally not used. Canvas API access should use a personal access token, which is safer and works better with campus SSO/2FA.

4. Install and run:

```bash
cd canvas-mcp
python -m venv .venv
. .venv/bin/activate
pip install -e .
canvas-mcp
```

## How To Get `CANVAS_ACCESS_TOKEN`

1. Open your Canvas website in a browser, for example `https://canvas.eee.uci.edu` for UCI.
2. Log in normally with your school Canvas/SSO username and password.
3. Click `Account`.
4. Click `Settings`.
5. Find `Approved Integrations`.
6. Click `New Access Token`.
7. Give it a purpose such as `Canvas MCP for Students`.
8. Copy the generated token immediately and paste it into `.env`.

Do not put your Canvas username or password in `.env`. This MCP uses Canvas's API with an `Authorization: Bearer <token>` header, so the value it needs is the generated access token, not the login password.

## Codex MCP Config Snippet

See `mcp-desktop-config-snippet.json`. If your path contains spaces, keep each argument as a separate JSON string exactly like the snippet.

## Useful Tool Flow

1. `tool_list_courses`
2. `tool_get_todo_items` or `tool_get_missing_work`
3. `tool_get_assignment_details`
4. `tool_prepare_assignment_workspace`
5. Let Codex work inside the generated folder.
6. If needed, manually review the result and call `tool_submit_text_assignment(..., confirm_write=True)` or `tool_submit_url_assignment(..., confirm_write=True)`.

## Notes

Canvas APIs are paginated. This server follows pagination up to `CANVAS_MAX_PAGES`.

File downloads are best-effort because instructors can link content through modules, external tools, Google Drive, or locked Canvas files. The workspace tool saves all discovered links in `assignment.md` even when it cannot download them.

Most users only need `CANVAS_BASE_URL` and `CANVAS_ACCESS_TOKEN`. `CANVAS_DOWNLOAD_DIR` and `CANVAS_MAX_PAGES` are optional advanced settings.

## Canvas API References

- Managing Canvas API access tokens: https://community.canvaslms.com/t5/Canvas-Basics-Guide/How-do-I-manage-API-access-tokens-in-my-user-account/ta-p/615312
- Courses API: https://canvas.instructure.com/doc/api/courses.html
- Assignments API: https://canvas.instructure.com/doc/api/assignments.html
- Submissions API: https://canvas.instructure.com/doc/api/submissions.html

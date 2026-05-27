# Canvas MCP

Local MCP server for Canvas LMS. It is designed like a safer, cleaner cousin of the local Gradescope MCP: browser login with Duo support, optional API-token authentication, read-only tools by default, and explicit confirmation for anything that can submit work.

## What It Can Do

- List active Canvas courses.
- Show upcoming, overdue, unsubmitted, or undated assignments with due dates.
- Query Canvas planner/todo items.
- Fetch full assignment details, including submission status and cleaned instructions.
- Prepare a local assignment workspace with `assignment.md` and optionally downloaded linked files.
- Create safe homework help packs: fill-in templates, hint packs, practice versions, and draft checklists.
- Submit completed student-authored text, URL, or file-upload assignments only when `confirm_write=True`.

## Safety Model

This server helps Codex collect assignment context and prepare work. It does not silently submit anything. Submission tools return a dry-run confirmation unless `confirm_write=True` is provided.

For academic work, use the workspace tools to understand requirements, draft your own solution, run checks, and decide what to submit.

If you use browser login mode, keep `.env` local and private. Duo reduces risk, but a plaintext school password is still sensitive.

The homework-help tools are designed for learning support. They intentionally create scaffolds, hints, practice prompts, and draft checks rather than submit-ready solutions.

## Setup

1. Install the package:

```bash
cd canvas-mcp
python -m venv .venv
. .venv/bin/activate
pip install -e ".[browser]"
python -m playwright install chromium
```

2. Copy `.env.example` to `.env` and fill in your Canvas login:

```bash
# Canvas credentials
CANVAS_BASE_URL=https://canvas.eee.uci.edu
CANVAS_AUTH_MODE=browser
CANVAS_EMAIL=your_username_or_email
CANVAS_PASSWORD=your_password
CANVAS_STORAGE_STATE=.canvas-storage-state.json
```

For UCI, `CANVAS_EMAIL` can be your UCInetID such as `kuanchey`, or your full campus email if your login page expects that.

3. Log in once through the browser helper:

```bash
canvas-mcp-login
```

The helper opens a real browser, fills your username/password, and waits while you approve Duo on your phone. Once Canvas has loaded, return to the terminal and press Enter. It saves a local browser session to `.canvas-storage-state.json`.

4. Run the MCP server:

```bash
canvas-mcp
```

If the session expires, run `canvas-mcp-login` again.

## Alternative Token Mode

Canvas API tokens are more reliable than browser sessions. If you prefer token mode, set `CANVAS_ACCESS_TOKEN` in `.env`; it takes priority over browser login:

```bash
CANVAS_BASE_URL=https://canvas.eee.uci.edu
CANVAS_ACCESS_TOKEN=paste_your_canvas_access_token_here
```

To create a token:

1. Open your Canvas website in a browser, for example `https://canvas.eee.uci.edu` for UCI.
2. Log in normally with your school Canvas/SSO username and password.
3. Click `Account`.
4. Click `Settings`.
5. Find `Approved Integrations`.
6. Click `New Access Token`.
7. Give it a purpose such as `Canvas MCP for Students`.
8. Copy the generated token immediately and paste it into `.env`.

In token mode, this MCP uses Canvas's API with an `Authorization: Bearer <token>` header.

## Codex MCP Config Snippet

See `mcp-desktop-config-snippet.json`. If your path contains spaces, keep each argument as a separate JSON string exactly like the snippet.

## Useful Tool Flow

1. Run `canvas-mcp-login` if you are using browser/Duo login mode.
2. `tool_list_courses`
3. `tool_get_todo_items` or `tool_get_missing_work`
4. `tool_get_assignment_details`
5. `tool_prepare_assignment_workspace`
6. `tool_prepare_homework_help_pack`
7. Write your own solution in the generated template.
8. Use `tool_check_my_draft` on your completed draft.
9. If needed, manually review the result and call `tool_submit_text_assignment(...)`, `tool_submit_url_assignment(...)`, or `tool_submit_file_assignment(...)`.
10. Submission tools first return a dry run. Re-run with `confirm_write=True` only after you have reviewed the exact completed work.

## Homework Help Tools

- `tool_prepare_homework_help_pack(course_id, assignment_id)`: creates `homework_template.md`, `hint_pack.md`, `practice_version.md`, and `submission_target.md` beside the assignment files.
- `tool_create_homework_template(...)`: creates a blank, fill-in structure by problem.
- `tool_generate_hint_pack(...)`: gives concepts, formulas to consider, and checklist-style hints.
- `tool_make_practice_version(...)`: creates a similar but not identical practice plan.
- `tool_check_my_draft(...)`: checks a student-authored draft for missing sections and common omissions.
- `tool_extract_due_and_submission_target(...)`: summarizes the due date and whether Canvas or Gradescope appears to be the target.

## Submission Tools

- `tool_submit_text_assignment(...)`: submits finished text-entry work to Canvas.
- `tool_submit_url_assignment(...)`: submits a finished URL to Canvas.
- `tool_submit_file_assignment(...)`: uploads a completed local file and submits it to a Canvas `online_upload` assignment.

Canvas assignments that say to submit on Gradescope should be submitted through Gradescope, not with Canvas file upload.

## Notes

Canvas APIs are paginated. This server follows pagination up to `CANVAS_MAX_PAGES`.

File downloads are best-effort because instructors can link content through modules, external tools, Google Drive, or locked Canvas files. The workspace tool saves all discovered links in `assignment.md` even when it cannot download them.

The workspace and homework-help tools compare the assignment number with linked homework file names. Normal linked files download directly. If Canvas says `Assignment 4` but links something like `HW2.pdf`, the tool asks for user confirmation before downloading or generating a help pack from that file. After manually confirming the Canvas link is intentional, rerun with `allow_mismatched_files=True`.

By default, assignment files are saved under `./canvas-mcp-downloads` relative to the directory where the MCP server is started. In Codex/Claude, that usually means the current project or conversation workspace. You can also set `CANVAS_DOWNLOAD_DIR` in `.env`, or pass `output_dir` to `tool_prepare_assignment_workspace` / `tool_prepare_homework_help_pack`.

Most users only need `CANVAS_BASE_URL`, `CANVAS_EMAIL`, `CANVAS_PASSWORD`, and `CANVAS_STORAGE_STATE` for browser/Duo login mode. `CANVAS_DOWNLOAD_DIR` and `CANVAS_MAX_PAGES` are optional advanced settings.

## Canvas API References

- Managing Canvas API access tokens: https://community.canvaslms.com/t5/Canvas-Basics-Guide/How-do-I-manage-API-access-tokens-in-my-user-account/ta-p/615312
- Courses API: https://canvas.instructure.com/doc/api/courses.html
- Assignments API: https://canvas.instructure.com/doc/api/assignments.html
- Submissions API: https://canvas.instructure.com/doc/api/submissions.html
- File upload workflow: https://canvas.instructure.com/doc/api/file.file_uploads.html

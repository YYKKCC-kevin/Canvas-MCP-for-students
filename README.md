# Canvas MCP

Local MCP server for Canvas LMS. It is designed like a safer, cleaner cousin of the local Gradescope MCP: browser login with Duo support, optional API-token authentication, read-only tools by default, and explicit confirmation for anything that can submit work.

## What It Can Do

- List active Canvas courses.
- Show upcoming, overdue, unsubmitted, or undated assignments with due dates.
- Query Canvas planner/todo items.
- Read course announcements, discussion topics, syllabus/class information, and module/lecture materials.
- Find exam-, quiz-, test-, midterm-, and final-like Canvas items across active courses.
- Fetch full assignment details, including submission status and cleaned instructions.
- Resolve where the real assignment prompt lives: Canvas files, GitHub, Gradescope, or a user-provided file/link.
- Prepare a local assignment workspace with `assignment.md` and optionally downloaded linked files.
- Create safe homework help packs: fill-in templates, hint packs, practice versions, and draft checklists.
- Review a finished submission file before upload for readability, prompt-vs-solution mistakes, and problem coverage.
- Prepare Gradescope-style correctness review artifacts so an agent can judge solutions even when no reference answer is provided.
- Prepare multi-agent review packets for solver-agent, reviewer-agent, and disagreement-resolution workflows.
- Run quick correctness checks when a reference answer or rubric is available.
- Optionally bridge to a local `gradescope-mcp` install for Gradescope course/assignment lookup.
- Submit completed student-authored text, URL, or file-upload assignments only when `confirm_write=True`.
- Fall back to browser-based Canvas upload when Canvas rejects API file-upload initialization.

## Safety Model

This server helps Codex collect assignment context and prepare work. It does not silently submit anything. Submission tools return a dry-run confirmation unless `confirm_write=True` is provided.

For academic work, use the workspace tools to understand requirements, draft your own solution, run checks, and decide what to submit.

If you use browser login mode, keep `.env` local and private. Duo reduces risk, but a plaintext school password is still sensitive.

The homework-help tools support coursework workflows, including assignment context gathering, structured drafting, targeted help packs, practice prompts, draft checks, and submission preparation.

## Setup

1. Install the package:

```bash
cd canvas-mcp
python -m venv .venv
. .venv/bin/activate
pip install -e ".[browser]"
python -m playwright install chromium
```

If you also want the optional Gradescope bridge in the same environment:

```bash
pip install -e ".[browser,gradescope]"
```

2. Copy `.env.example` to `.env` and fill in your Canvas login:

```bash
# Canvas credentials
CANVAS_BASE_URL=your_canvas_address
# Example: CANVAS_BASE_URL=https://canvas.eee.uci.edu
CANVAS_AUTH_MODE=browser
CANVAS_EMAIL=your_username_or_email
CANVAS_PASSWORD=your_password
CANVAS_STORAGE_STATE=.canvas-storage-state.json
```

`CANVAS_BASE_URL` should be your school's Canvas website. `CANVAS_EMAIL` can be your username, school email, or whatever your Canvas/SSO login page expects.

Note: use the Canvas main address, not the school's temporary SSO redirect URL. For example, use `https://canvas.ucsd.edu` or `https://canvas.eee.uci.edu`, not a URL containing `/SAML2/Redirect/SSO?...`; those redirect links are often one-time or expired and can confuse the login helper.

3. Log in once through the browser helper:

```bash
canvas-mcp-login
```

The helper opens a real browser, fills your username/password, and waits while you approve Duo on your phone. It also tries to click common post-login prompts such as `Skip for now`, `Trust this browser`, `Yes, this is my device`, `暂时跳过`, and `是，这是我的设备`, including prompts embedded in Duo/SSO frames. Once Canvas has loaded, it saves a local browser session to `.canvas-storage-state.json` automatically. If your school's login flow redirects unusually and automatic detection times out, the helper will ask you to press Enter as a manual fallback.

4. Run the MCP server:

```bash
canvas-mcp
```

If the session expires, run `canvas-mcp-login` again.

## Alternative Token Mode

Canvas API tokens are more reliable than browser sessions. If you prefer token mode, set `CANVAS_ACCESS_TOKEN` in `.env`; it takes priority over browser login:

```bash
CANVAS_BASE_URL=your_canvas_address
# Example: CANVAS_BASE_URL=https://canvas.eee.uci.edu
CANVAS_ACCESS_TOKEN=paste_your_canvas_access_token_here
```

Use the same Canvas main address rule in token mode: `CANVAS_BASE_URL` should be the Canvas site root, not an SSO login URL.

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

## Optional Gradescope Bridge

Some courses use Canvas only for deadlines while the actual prompt or submission lives on Gradescope. If you also have `gradescope-mcp` locally, Canvas MCP can hand off read-only Gradescope lookup through bridge tools.

Add these optional values to `.env`:

```bash
GRADESCOPE_MCP_PATH=/Users/yourname/gradescope-mcp
GRADESCOPE_EMAIL=your_email@example.com
GRADESCOPE_PASSWORD=your_password
```

If `gradescope-mcp` is cloned at `~/gradescope-mcp`, `GRADESCOPE_MCP_PATH` can be omitted. The bridge reuses `gradescope-mcp` for login and assignment lookup; write-capable Gradescope actions remain governed by that MCP's own confirmation rules.

## Codex MCP Config Snippet

See `mcp-desktop-config-snippet.json`. Replace `/absolute/path/to/Canvas-MCP-for-students` with the folder where you cloned this repo. If your path contains spaces, keep each argument as a separate JSON string exactly like the snippet.

## Useful Tool Flow

1. Run `canvas-mcp-login` if you are using browser/Duo login mode.
2. `tool_list_courses`
3. `tool_get_todo_items` or `tool_get_missing_work`
4. Use `tool_list_course_announcements(...)`, `tool_list_exam_items(...)`, `tool_list_course_discussions(...)`, `tool_get_course_info(...)`, or `tool_list_course_modules(...)` when you need notices, exam dates, discussion posts, syllabus/class info, or lecture/module materials.
5. `tool_get_assignment_details`
6. `tool_resolve_assignment_source`
7. If the source is Canvas, run `tool_prepare_assignment_workspace`.
8. If the source is GitHub, inspect or clone the linked repo/file before preparing work.
9. If the source is Gradescope, run `tool_gradescope_bridge_status`, then list Gradescope courses/assignments.
10. `tool_prepare_homework_help_pack`
11. Write your own solution in the generated template.
12. Use `tool_check_my_draft` while drafting.
13. Use `tool_review_solution_for_chat(...)` when you want the assistant to tell the user directly what is inaccurate or needs revision.
14. Use `tool_prepare_multi_agent_review_packet(...)` when you want a solver agent and an independent reviewer agent to check the solution, then send disagreements back to the solver before the assistant gives final feedback.
15. Use `tool_prepare_solution_review_artifact(...)` for a reusable deeper review artifact, especially if no reference answer exists.
16. Optionally use `tool_review_solution_correctness(...)` for faster reference/rubric-based checks.
17. Use `tool_review_submission_file(...)` on the final PDF/file before upload.
18. Run the relevant submission tool once without `confirm_write` for a dry run.
19. Re-run with `confirm_write=True` only after reviewing the exact file/path/assignment target.
20. Run `tool_get_my_submission` after submission to confirm Canvas status.

If `tool_resolve_assignment_source` cannot identify the true prompt, it asks the user where the assignment lives instead of guessing.

## Tool Inventory

### Course And Deadline Tools

- `tool_list_courses(...)`: lists active/completed Canvas courses and optional scores.
- `tool_list_course_assignments(...)`: lists assignments in one course by bucket such as upcoming, overdue, unsubmitted, or all.
- `tool_get_missing_work(...)`: finds unsubmitted work across courses within a date window.
- `tool_get_todo_items(...)`: reads Canvas planner/todo items.
- `tool_get_assignment_details(...)`: fetches one Canvas assignment's deadline, status, instructions, submission type, and links.

### Course Content And Exam Tools

- `tool_list_course_announcements(...)`: lists recent announcements for one course or all active courses, including posted time, author, preview text, and Canvas URL.
- `tool_list_exam_items(...)`: finds exam-, quiz-, test-, midterm-, and final-like Canvas assignment items across active courses or within one course.
- `tool_list_course_discussions(...)`: lists discussion topics for a course, with an option to include announcement-style discussion topics.
- `tool_get_course_info(...)`: fetches course metadata, teachers, sections, term, time zone, and syllabus/class information exposed by Canvas.
- `tool_list_course_modules(...)`: lists Canvas modules and module items, useful for lecture slides, weekly class materials, readings, pages, files, and external links.

### Assignment Source Tools

- `tool_resolve_assignment_source(...)`: decides whether the real prompt is on Canvas, GitHub, Gradescope, a user-provided URL/path, or unclear.
- `tool_prepare_assignment_workspace(...)`: creates a local folder with `assignment.md` and linked files when the source is safe to use.

The source resolver prevents common mistakes. For example, if Canvas says `Assignment 4` but links `HW2.pdf`, the tool asks the user to confirm instead of silently downloading the wrong file. If Canvas mentions Gradescope, use the Gradescope bridge before preparing or submitting work. If Canvas points to GitHub, inspect/clone that source first.

## Homework Help Tools

- `tool_resolve_assignment_source(course_id, assignment_id)`: checks whether the actual prompt is on Canvas, GitHub, Gradescope, or needs user clarification.
- `tool_prepare_homework_help_pack(course_id, assignment_id)`: creates `homework_template.md`, `hint_pack.md`, `practice_version.md`, and `submission_target.md` beside the assignment files.
- `tool_create_homework_template(...)`: creates a structured, editable workspace by problem.
- `tool_generate_hint_pack(...)`: gives concepts, formulas to consider, checklist-style checks, and drafting cues.
- `tool_make_practice_version(...)`: creates a similar but not identical practice plan.
- `tool_check_my_draft(...)`: checks a student-authored draft for missing sections and common omissions.
- `tool_review_solution_for_chat(...)`: prepares a review artifact and returns a user-facing chat summary plus automatically detected review signals. Use this when the user expects the assistant to say what is inaccurate and what should be changed in the conversation, not just where the artifact was saved.
- `tool_prepare_multi_agent_review_packet(...)`: prepares a solver/reviewer/disagreement-resolution packet. The MCP cannot directly spawn Codex or Claude subagents by itself, but the packet tells the host assistant to run a solver agent, run an independent reviewer agent, compare their outputs, send disagreements back to the solver, and report the final consensus directly in chat.
- `tool_prepare_solution_review_artifact(...)`: prepares a Gradescope-style artifact containing the prompt, student solution, optional reference/rubric, and detailed agent instructions. This is the preferred way to let Codex/Claude review whether a student's solution is correct when no answer key is available.
- `tool_review_solution_correctness(...)`: runs a faster automated correctness-oriented check. It is strongest when given `reference_text`, `reference_path`, or `rubric_text`; without those, it clearly reports low confidence and only performs internal consistency checks.
- `tool_review_submission_file(...)`: reviews a finished file for readability, expected problem coverage, and prompt-file-vs-solution-file mistakes before upload.
- `tool_extract_due_and_submission_target(...)`: summarizes the due date and whether Canvas or Gradescope appears to be the target.

Correctness review has four modes:

- Chat-ready mode: run `tool_review_solution_for_chat(...)`. It returns the artifact path, quick detected issues, and a required follow-up instruction that the assistant must tell the user what is wrong or incomplete directly in chat instead of only returning the artifact path.
- Multi-agent consensus mode: run `tool_prepare_multi_agent_review_packet(...)`. The MCP writes a packet for a solver agent, an independent reviewer agent, and a final disagreement-resolution pass. If the reviewer disagrees, the host assistant should send the disputed items back to the solver, then tell the user the exact final edits and confidence level.
- Agent-assisted mode: run `tool_prepare_solution_review_artifact(...)`, then have Codex/Claude read the artifact and produce a per-problem correctness review. This mirrors the Gradescope MCP workflow: the MCP gathers and structures evidence, while the agent reasons from the prompt, solution, rubric, and domain knowledge.
- Automated quick-check mode: run `tool_review_solution_correctness(...)`. This catches missing reference conclusions, suspicious formula mismatches, missing problem sections, and rubric terms that do not appear in the solution. It is not an official grade and cannot guarantee every proof step is correct.

`tool_check_my_draft` and `tool_review_submission_file` remain structural checks that help catch dangerous submission mistakes like uploading the prompt instead of the solution.

## Submission Tools

- `tool_get_my_submission(...)`: checks the current Canvas submission state after upload.
- `tool_submit_text_assignment(...)`: submits finished text-entry work to Canvas.
- `tool_submit_url_assignment(...)`: submits a finished URL to Canvas.
- `tool_submit_file_assignment(...)`: uploads a completed local file and submits it to a Canvas `online_upload` assignment.

All submission tools require an explicit write confirmation. First call them with `confirm_write=False` or omit it to see a no-op dry run. Only call again with `confirm_write=True` after checking the course ID, assignment ID, file path, and submission type. Submission comments are never sent by default; if `comment` is provided, the tool also requires `confirm_comment=True` so an assistant cannot add a Canvas comment unless the user explicitly requested that exact comment.

For file uploads, the tool first tries the Canvas API. Some Canvas instances reject browser-session API upload initialization; in that case, `tool_submit_file_assignment` can fall back to the saved browser session and upload through the Canvas assignment web page. After submitting, always call `tool_get_my_submission` to verify `workflow_state=submitted`.

Canvas assignments that say to submit on Gradescope should be submitted through Gradescope, not with Canvas file upload.

## Gradescope Bridge Tools

- `tool_gradescope_bridge_status(...)`: checks whether local `gradescope-mcp` is available and optionally verifies login.
- `tool_gradescope_list_courses(...)`: lists Gradescope courses through local `gradescope-mcp`.
- `tool_gradescope_list_assignments(...)`: lists assignments for one Gradescope course.
- `tool_gradescope_get_assignment_details(...)`: reads one Gradescope assignment's details.

## Credits

- `YYKKCC-kevin`: project owner and maintainer.
- [`Codex`](https://github.com/codex): implementation assistant for Canvas MCP workflows.

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

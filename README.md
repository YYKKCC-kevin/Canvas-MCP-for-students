# Canvas MCP

Local MCP server for Canvas LMS. It is designed like a safer, cleaner cousin of the local Gradescope MCP: browser login with Duo support, optional API-token authentication, read-only tools by default, and explicit confirmation for anything that can submit work.

<details>
<summary><strong>中文</strong></summary>

## Canvas MCP 中文说明

Canvas MCP 是一个本地运行的 Canvas 学习助手 MCP server。它可以让 Codex、Claude 等支持 MCP 的智能体登录学校 Canvas，读取课程、公告、作业、DDL、模块资料和提交状态，并在用户明确确认后帮助上传已经完成的作业文件。

### 它可以做什么

- 查看当前学期 Canvas 课程，包括学生课程和 TA/助教相关课程。
- 汇总 upcoming、overdue、unsubmitted、undated 等不同状态的作业和 DDL。
- 查看 Canvas planner/todo、公告、discussion、syllabus、modules、lecture materials 等课程信息。
- 打开某个 assignment 的完整说明、提交方式、due date 和当前提交状态。
- 自动创建本地作业工作区，保存 `assignment.md`，并尽量下载 Canvas 里链接的 PDF、文档或其他附件。
- 判断作业真正来源是在 Canvas、GitHub、Gradescope，还是用户提供的本地文件/链接。
- 准备 multi-agent review packet，让一个 agent 完成作业，另一个 agent 独立检查，然后再整合分歧。
- 检查最终提交文件，帮助发现上传错文件、漏题、格式不合要求、说明和答案不匹配等问题。
- 在用户明确确认后，提交 Canvas 的 text、URL 或 file-upload assignment。
- 如果 Canvas API 不接受文件上传初始化，可以尝试使用保存好的浏览器 session 走网页上传 fallback。
- 读取课件正文：PDF、PPTX（含演讲者备注）、DOCX、Jupyter notebook、HTML、纯文本，用来总结 slides、整理知识点。
- 内置 Gradescope 支持：查看你的 Gradescope 课程和作业，并在你确认后上传已完成的文件，不需要另装 `gradescope-mcp`。
- 提供一组 `/` 斜杠命令（MCP prompts），把常用流程做成现成的工作流，例如了解作业、总结课件、考试复习与押题、提交前检查、确认后提交。

### 安全和确认机制

Canvas MCP 默认偏向只读操作。任何会写入 Canvas 或提交作业的工具，都需要显式确认，例如 `confirm_write=True`。如果要添加提交评论，还需要额外的 `confirm_comment=True`，避免智能体在用户没有要求时私自添加 comment。

在课程作业场景中，建议先确认两件事：

- 这门课或老师是否允许使用 AI 工具辅助完成该作业。
- 用户是否希望 AI 帮助完成、检查、上传或提交该作业。

如果老师允许使用 AI，并且用户明确要求完成或提交，MCP 可以配合智能体完成作业、检查文件并提交。Canvas 上名为 exam / midterm / final / test 的条目按普通作业处理（实际考试通常是线下进行，成绩由助教在 Gradescope 批改），同样先确认老师是否允许使用 AI。

### 一键安装（推荐）

```bash
git clone https://github.com/YYKKCC-kevin/Canvas-MCP-for-students.git
cd Canvas-MCP-for-students
python3 install.py
```

安装向导会依次询问学校的 Canvas 网址、登录方式（浏览器登录或 API token）、用户名和密码（输入时不显示），然后自动：

- 把配置写入本地 `.env`（仅当前用户可读，已被 `.gitignore` 排除），**不会**修改 `.env.example`；
- 创建 `.venv` 并安装依赖，浏览器登录模式下还会安装 Chromium；
- 询问是否现在登录一次（在手机上批准 Duo）；
- 打印把它连接到 Claude Code / Codex 的命令。

让 AI 代你安装时，请它只运行 `python3 install.py`，并在需要输入密码或 token 时自己在终端里输入，不要把密码发给 AI。重新运行向导可以更新配置，其他设置（如 Gradescope）会保留。

如果作业要求在 Gradescope 提交，可以在向导末尾选择设置 Gradescope，或之后单独运行 `python3 install.py --gradescope-only`。Gradescope 的密码只在终端里输入，任何工具都不接收密码，所以不会出现在聊天记录里。

下面是手动安装方式。

### 手动安装

```bash
cd canvas-mcp
python -m venv .venv
. .venv/bin/activate
pip install -e ".[browser]"
python -m playwright install chromium
```

如果还想启用 Gradescope bridge：

```bash
pip install -e ".[browser,gradescope]"
```

### 配置 Canvas 登录

复制 `.env.example` 为 `.env`，然后填入学校 Canvas 地址、用户名和密码：

```bash
CANVAS_BASE_URL=your_canvas_address
# 例如:
# CANVAS_BASE_URL=https://canvas.ucsd.edu
# CANVAS_BASE_URL=https://canvas.eee.uci.edu
CANVAS_AUTH_MODE=browser
CANVAS_EMAIL=your_username_or_email
CANVAS_PASSWORD=your_password
CANVAS_STORAGE_STATE=.canvas-storage-state.json
```

`CANVAS_BASE_URL` 应该填写学校 Canvas 主页地址，不要填写临时 SSO redirect URL。比如使用 `https://canvas.ucsd.edu` 或 `https://canvas.eee.uci.edu`，不要使用带有 `/SAML2/Redirect/SSO?...` 的一次性跳转链接。

### 第一次登录

```bash
canvas-mcp-login
```

这个命令会打开真实浏览器，自动填写账号密码，然后等待你在手机上通过 Duo。登录过程中它也会尝试自动点击常见按钮，例如 `Skip for now`、`Trust this browser`、`Yes, this is my device`、`暂时跳过`、`是，这是我的设备` 等。登录成功后，会把浏览器 session 保存到 `.canvas-storage-state.json`，以后 MCP 就可以复用这个登录状态。

如果 session 过期，重新运行：

```bash
canvas-mcp-login
```

### 运行 MCP server

```bash
canvas-mcp
```

在 Codex 或 Claude 的 MCP 配置里，可以参考仓库中的 `mcp-desktop-config-snippet.json`，把路径换成你本地 clone 的 Canvas MCP 路径。

### `/` 斜杠命令（prompts）

除了工具，服务器还提供现成的工作流。在支持 MCP prompts 的客户端里输入 `/`，就能看到 `MCP_Canvas:<名称>` 之类的条目。所有参数都是可选的：不填课程或作业时，AI 会自己查找并让你确认。

| Prompt | 作用 |
| --- | --- |
| `my_courses_overview` | 当前学期课程、你的身份、老师、上课时间、office hours |
| `course_requirements` | 课程大纲摘要：评分、日程、政策，以及课程对 AI 使用的规定 |
| `deadlines_and_exams` | 把逾期、即将到期的作业和考试日期放到一条时间线上 |
| `summarize_lecture_materials` | 总结课件和模块资料，可以按主题筛选 |
| `study_for_exam` | 读取课件、作业和往年考卷，整理知识点（通俗解释、公式、例子、常见坑），按证据预测可能的考题并标注把握程度，再排出每日复习计划 |
| `start_assignment` | 作业要求、截止时间、提交位置，以及 AI 权限确认。不写答案 |
| `complete_assignment` | 在你确认老师允许 AI 之后起草作业（也可以用 `ai_policy_note` 直接说明）。从不提交 |
| `review_before_submit` | 检查成品文件是否完整、正确。从不提交 |
| `submit_assignment` | 先列出将要提交的内容，你明确说 yes 之后才提交，Canvas 和 Gradescope 都适用 |

安全规则写在 prompt 里：没有确认 AI 权限就不代写；没有对具体摘要的明确同意就不提交；读不出的文件不编造内容。`study_for_exam` 的考题预测只是根据材料的推断，AI 会明确说这是推测，不会假装知道真题。prompt 的源码在 `src/canvas_mcp/prompts.py`。

### 读取课件

`tool_read_course_file` 把课件下载到内存里，只返回文字，**不会在你的电脑上留下文件**。长文件会分段返回，按提示的 `start_char` 继续读即可。

两种情况会临时保存一份副本，让 AI 仍然能读：

- **扫描件或纯图片文件**：AI 打开副本直接看页面图像。
- **旧版 `.ppt` / `.doc`**：用 LibreOffice（需已安装）转换成 `.pptx` / `.docx` 后读取文字。

副本放在系统临时目录，30 分钟后自动删除，服务器退出时也会删除，也可以随时调用 `tool_clear_temp_materials` 立刻清掉。暂不支持 `.xls`。

### Gradescope 支持

有些课程在 Canvas 上只放截止时间，真正的题目和提交在 Gradescope。Canvas MCP 内置了 Gradescope 支持，只操作你自己的学生账号：查看课程和作业，上传已完成的文件。

在终端运行一次：

```bash
python3 install.py --gradescope-only
```

向导会询问 Gradescope 邮箱和密码（输入时不显示），保存到本地 `.env`，安装 `gradescopeapi`，并检查能否登录。普通安装结束时也可以选择现在设置。设置完成后需要重启 AI 客户端。

**密码只会在安装向导里输入。** 没有任何工具接收密码参数，所以不会出现在聊天记录里。如果 AI 让你把密码贴到聊天里，请拒绝，改用上面的命令。

遇到需要在 Gradescope 提交的作业，`submit_assignment` 会这样走：

1. 检查 Gradescope 是否已设置，没设置就提示你去终端运行上面的命令。
2. 如果 Canvas 里直接给了 Gradescope 作业链接，就直接读出课程和作业 ID；否则列出你的 Gradescope 课程和作业，让你确认是哪一份（Gradescope 的 ID 和 Canvas 不同）。
3. 预览将要上传的内容：作业名、截止时间、当前状态、文件名。如果已过截止时间会有警告。此时不会上传任何东西。
4. 你明确说 yes 之后才真正上传，并返回提交页面链接和最新状态。

需要知道的限制：

- 登录用的是 Gradescope 邮箱和密码。如果你平时用学校单点登录，请先在 gradescope.com 用"忘记密码"设置一个 Gradescope 密码。
- 上传文件不会标注哪几页对应哪道题。需要标注的作业，请在提交页面上自己完成。
- 只支持文件上传。AI 不会改成绩、延期，也不会操作教师账号。

如果你已经单独装了 `gradescope-mcp`（在 `.env` 里设置 `GRADESCOPE_MCP_PATH`，或克隆在 `~/gradescope-mcp`），查询类工具会优先使用它；提交始终使用内置支持。

### 常用流程

1. 运行 `canvas-mcp-login` 完成浏览器登录和 Duo 验证。
2. 用 `tool_list_courses` 查看课程。
3. 用 `tool_get_todo_items` 或 `tool_get_missing_work` 汇总 DDL 和未提交作业。
4. 用 `tool_get_assignment_details` 查看某个作业说明。
5. 用 `tool_resolve_assignment_source` 判断真正的作业材料在哪里。
6. 用 `tool_prepare_assignment_workspace` 下载并整理作业材料。
7. 如果需要完成作业，先确认老师允许 AI 辅助。
8. 用 multi-agent 工作流完成草稿和独立检查。
9. 用 `tool_review_submission_file` 检查最终文件。
10. 只有在用户明确说提交后，才用提交工具并设置 `confirm_write=True`。
11. 提交后用 `tool_get_my_submission` 确认 Canvas 状态为 `submitted`。
12. 如果作业要求在 Gradescope 提交，改用 `tool_gradescope_submit_assignment`：先不带 `confirm_write` 预览，确认后再带 `confirm_write=True` 上传。

### 隐私提醒

不要把下面这些文件或信息提交到 GitHub：

- `.env`
- Canvas 密码
- API token
- `.canvas-storage-state.json`
- 浏览器 session 文件
- 私人课程资料、成绩、提交文件或学生信息

</details>

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
- Read lecture files (PDF, PPTX with speaker notes, DOCX, notebooks, HTML, text) in memory to summarize slides and build study notes.
- List your Gradescope courses and assignments and upload a finished file, using built-in support that needs no separate `gradescope-mcp`.
- Offer slash-command prompts for the common workflows, including exam study notes with evidence-based question predictions.
- Submit completed student-authored text, URL, or file-upload assignments only when `confirm_write=True`.
- Fall back to browser-based Canvas upload when Canvas rejects API file-upload initialization.

## Safety Model

This server helps Codex collect assignment context and prepare work. It does not silently submit anything. Submission tools return a dry-run confirmation unless `confirm_write=True` is provided.

For homework or coursework completion requests, the assistant should first confirm two things with the user:

- Whether the course or instructor allows the student to use AI tools for this assignment.
- Whether the user wants AI assistance to complete, review, and/or submit the work.

If the user confirms AI assistance is allowed and asks for completion or submission, the assistant should help complete the assignment, check the work, upload it, and submit it when the relevant submission tool has explicit write confirmation. It should not use a blanket refusal such as "I cannot help you complete this" after the user has confirmed the work is AI-permitted. If AI permission is unknown, ask for confirmation and provide learning, debugging, or review support while waiting. Items named exam, midterm, final, or test on Canvas are treated like any other assignment (real exams are normally taken offline and graded on Gradescope), so the same AI-permission check applies.

If you use browser login mode, keep `.env` local and private. Duo reduces risk, but a plaintext school password is still sensitive.

The homework-help tools support coursework workflows, including assignment context gathering, structured drafting, targeted help packs, practice prompts, draft checks, and submission preparation.

## Quick Install (Recommended)

```bash
git clone https://github.com/YYKKCC-kevin/Canvas-MCP-for-students.git
cd Canvas-MCP-for-students
python3 install.py
```

The installer asks for your school's Canvas address, the login method (browser login or API token), and your username and password (hidden while typing). It then:

- writes them to a local `.env` (owner-only, git-ignored) and never touches `.env.example`;
- creates `.venv` and installs the dependencies, plus Chromium for browser login;
- offers to run the first login (approve Duo on your phone);
- prints the commands to connect it to Claude Code or Codex.

If an AI assistant runs the installer for you, have it run only `python3 install.py` and type the password or token yourself in the terminal. Do not paste it into the chat. Re-running the installer updates your settings and keeps unrelated ones such as Gradescope.

For scripts, pass `--base-url` and `--auth-mode`, and pipe the secret with `--password-stdin` or `--token-stdin`. Secrets are deliberately not accepted as command-line arguments.

Prefer to do it by hand? Follow the steps below.

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

## Gradescope Support

Some courses use Canvas only for deadlines while the actual prompt or submission lives on Gradescope. Canvas MCP has built-in Gradescope support, so no separate project is needed. It acts only on your own student account: list your courses and assignments, and upload a finished file.

Set it up once, in a terminal:

```bash
python3 install.py --gradescope-only
```

The installer asks for your Gradescope email and password (hidden while typing), saves them to the local `.env`, installs the `gradescopeapi` package, and checks that the login works. You can also answer yes to the Gradescope question at the end of a normal `python3 install.py` run. Restart your AI client afterwards.

Your Gradescope password is only ever typed into the installer. No tool accepts a password, so it cannot end up in a chat. If an assistant asks you to paste it, run the installer instead.

When a Canvas assignment is submitted on Gradescope, the `submit_assignment` prompt finds the matching Gradescope assignment, asks you to confirm it, previews exactly what will be uploaded (with a warning if the deadline has passed), and uploads only after you say yes.

Limits to know about:

- Login uses a Gradescope email and password. If you normally sign in with school single sign-on, first set a Gradescope password with "Forgot password" on gradescope.com.
- Uploading a file does not mark which pages answer which questions. For assignments that need that, finish it on the submission page.
- Only file uploads are supported. The assistant never changes grades, extensions, or anything on an instructor account.

If you already have a separate `gradescope-mcp` project (`GRADESCOPE_MCP_PATH` in `.env`, or a clone at `~/gradescope-mcp`), the lookup tools use it. Submission always uses the built-in support.

## Codex MCP Config Snippet

See `mcp-desktop-config-snippet.json`. Replace `/absolute/path/to/Canvas-MCP-for-students` with the folder where you cloned this repo. If your path contains spaces, keep each argument as a separate JSON string exactly like the snippet.

## Slash-Command Prompts

Besides tools, the server provides prompts: ready-made workflows that appear when you type `/` in clients that support MCP prompts, listed as `MCP_Canvas:<name>` or similar. All arguments are optional; if you leave out a course or assignment, the assistant looks it up and asks you to confirm.

| Prompt | What it does |
| --- | --- |
| `my_courses_overview` | Current-term courses with your role, instructor, class times, office hours |
| `course_requirements` | Syllabus summary: grading, schedule, policies, and what the course says about AI use |
| `deadlines_and_exams` | One timeline of overdue work, upcoming deadlines, and exam dates |
| `summarize_lecture_materials` | Summaries of lecture slides and module materials, optionally by topic |
| `study_for_exam` | Condenses slides, homework and past exams into key points, predicts likely questions with cited evidence, and builds a day-by-day plan |
| `start_assignment` | Requirements, deadline, submission target, and the AI-permission question. Writes no answers |
| `complete_assignment` | Drafts the work, only after you confirm AI use is allowed (or pass `ai_policy_note`). Never submits |
| `review_before_submit` | Readiness and correctness check of a finished file. Never submits |
| `submit_assignment` | Shows exactly what will be submitted and submits only after you say yes, on Canvas or on Gradescope |

Safety rules are written into the prompts themselves: no AI-written work without the AI-permission check, no submission without an explicit yes to a specific summary, and no invented slide content when a file cannot be read. Prompts live in `src/canvas_mcp/prompts.py`.

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
11. For homework completion requests, confirm that AI assistance is allowed for this assignment and that the user wants AI to complete/review/submit it.
12. If confirmed, complete the work or prepare the requested draft; otherwise provide learning, debugging, or review help.
13. Use `tool_check_my_draft` while drafting.
14. Use `tool_review_solution_for_chat(...)` when you want the assistant to tell the user directly what is inaccurate or needs revision.
15. Use `tool_prepare_multi_agent_review_packet(...)` when you want a solver agent and an independent reviewer agent to check the solution, then send disagreements back to the solver before the assistant gives final feedback.
16. Use `tool_prepare_solution_review_artifact(...)` for a reusable deeper review artifact, especially if no reference answer exists.
17. Optionally use `tool_review_solution_correctness(...)` for faster reference/rubric-based checks.
18. Use `tool_review_submission_file(...)` on the final PDF/file before upload.
19. Run the relevant submission tool once without `confirm_write` for a dry run.
20. Re-run with `confirm_write=True` only after reviewing the exact file/path/assignment target.
21. Run `tool_get_my_submission` after submission to confirm Canvas status.

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
- `tool_list_course_modules(...)`: lists Canvas modules and module items, useful for lecture slides, weekly class materials, readings, pages, files, and external links. The ID column holds the file ID of File items.
- `tool_read_course_file(course_id, file, max_chars, start_char)`: reads the text of a lecture file (PDF, PPTX with speaker notes, DOCX, notebooks, HTML, plain text). The file is downloaded into memory and only its text is returned, so nothing is saved to your computer. Long files are returned in chunks: pass the `start_char` the result suggests to continue. Two cases save a temporary copy so the assistant can still read them: scanned or image-only files (the assistant opens the copy and looks at the pages) and legacy `.ppt`/`.doc` files (converted to `.pptx`/`.docx` with LibreOffice, if installed, and read as text). Copies live in the system temp folder and are deleted after 30 minutes, when the server stops, or by `tool_clear_temp_materials`.
- `tool_clear_temp_materials()`: deletes the temporary copies right away.

### Assignment Source Tools

- `tool_resolve_assignment_source(...)`: decides whether the real prompt is on Canvas, GitHub, Gradescope, a user-provided URL/path, or unclear.
- `tool_prepare_assignment_workspace(...)`: creates a local folder with `assignment.md` and linked files when the source is safe to use.

The source resolver prevents common mistakes. For example, if Canvas says `Assignment 4` but links `HW2.pdf`, the tool asks the user to confirm instead of silently downloading the wrong file. If Canvas mentions Gradescope, use the Gradescope tools before preparing or submitting work; when Canvas links straight to the Gradescope assignment, the course and assignment IDs are read from the link. If Canvas points to GitHub, inspect/clone that source first.

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

## Gradescope Tools

- `tool_gradescope_bridge_status(...)`: checks Gradescope readiness (built-in support, or a local `gradescope-mcp` if configured) and optionally verifies login.
- `tool_gradescope_list_courses(...)`: lists your Gradescope courses.
- `tool_gradescope_list_assignments(...)`: lists assignments for one Gradescope course, with due and late-due dates and status.
- `tool_gradescope_get_assignment_details(...)`: reads one Gradescope assignment's details.
- `tool_gradescope_submit_assignment(course_id, assignment_id, file_paths, confirm_write)`: uploads finished files to a Gradescope assignment. Without `confirm_write=True` it only previews. Use Gradescope IDs, not Canvas IDs.

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

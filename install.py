#!/usr/bin/env python3
"""Interactive installer for Canvas MCP.

Run it from the repository root:

    python3 install.py

It asks for your school's Canvas address and login, writes them to a local
`.env` (permissions 600, git-ignored), installs the package into `.venv`,
and optionally runs the first browser login.

Credentials are never written to `.env.example` (which is committed to git and
is not read by the server) and are never accepted as command-line arguments
(they would end up in your shell history). For automation, pipe a single
secret on stdin with --password-stdin or --token-stdin.

只用标准库，不需要提前安装任何依赖。账号密码只写入本地 `.env`，不会写进
`.env.example`，也不会出现在命令行参数里。
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
import venv
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
GITIGNORE_PATH = ROOT / ".gitignore"
STORAGE_STATE_PATH = ROOT / ".canvas-storage-state.json"

ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
SAFE_VALUE = re.compile(r"^[A-Za-z0-9_./:@+\-]*$")
SSO_HINTS = ("/saml", "/idp/", "/sso", "/cas/", "/shibboleth", "/oauth")

ZH = False  # set in main() from --lang / locale


def t(en: str, zh: str) -> str:
    return zh if ZH else en


def die(en: str, zh: str, code: int = 1) -> "None":
    print(f"\n[x] {t(en, zh)}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------------
# Pure helpers (unit-testable)
# --------------------------------------------------------------------------


def normalize_base_url(raw: str) -> str:
    """Reduce whatever the user typed to https://host[:port].

    Raises ValueError with a short reason if it cannot be a Canvas root.
    """
    value = (raw or "").strip().strip("'\"")
    if not value:
        raise ValueError("empty")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("not a web address")
    path = (parsed.path or "").lower()
    if any(hint in path for hint in SSO_HINTS):
        raise ValueError("looks like a one-time SSO redirect link, not the Canvas home page")
    host = parsed.hostname.lower()
    if "." not in host and host != "localhost":
        raise ValueError("host name has no domain")
    # Always https for real hosts; keep http only for local testing.
    scheme = "http" if host in ("localhost", "127.0.0.1") and parsed.scheme == "http" else "https"
    netloc = host + (f":{parsed.port}" if parsed.port else "")
    return f"{scheme}://{netloc}"


def format_env_value(value: str) -> str:
    """Quote a value so python-dotenv reads it back unchanged."""
    if "\n" in value or "\r" in value:
        raise ValueError("value contains a line break")
    if SAFE_VALUE.match(value):
        return value
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def read_env_keys(path: Path) -> dict[str, str]:
    """Return KEY -> raw value for assignments in an existing .env."""
    found: dict[str, str] = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_LINE.match(line)
        if match and not line.lstrip().startswith("#"):
            found[match.group(1)] = match.group(2).strip().strip("'\"")
    return found


def merge_env_text(existing: str, updates: dict[str, str]) -> str:
    """Replace assignments in place, append missing keys, keep everything else."""
    remaining = dict(updates)
    out: list[str] = []
    for line in existing.splitlines():
        match = ENV_LINE.match(line)
        if match and not line.lstrip().startswith("#") and match.group(1) in remaining:
            key = match.group(1)
            out.append(f"{key}={format_env_value(remaining.pop(key))}")
        else:
            out.append(line)
    if remaining and out and out[-1].strip():
        out.append("")
    for key, value in remaining.items():
        out.append(f"{key}={format_env_value(value)}")
    return "\n".join(out) + "\n"


def write_private(path: Path, text: str) -> None:
    """Write a file readable only by the current user."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass  # Windows: best effort
    os.replace(tmp, path)


def venv_python() -> Path:
    sub = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return ROOT / ".venv" / sub


def venv_script(name: str) -> Path:
    sub = f"Scripts/{name}.exe" if os.name == "nt" else f"bin/{name}"
    return ROOT / ".venv" / sub


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------


def interactive() -> bool:
    return sys.stdin.isatty()


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def ask_yes_no(prompt: str, default: bool) -> bool:
    if not interactive():
        return default
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "是", "好")


def ask_secret(prompt: str, keep_existing: bool) -> str:
    extra = t(" (Enter keeps the saved one)", "（直接回车保留已保存的）") if keep_existing else ""
    return getpass.getpass(f"{prompt}{extra}: ").strip()


def prompt_base_url(current: str) -> str:
    while True:
        raw = ask(
            t(
                "Your school's Canvas address, e.g. canvas.ucsd.edu or canvas.eee.uci.edu",
                "学校的 Canvas 网址，例如 canvas.ucsd.edu 或 canvas.eee.uci.edu",
            ),
            current or None,
        )
        try:
            url = normalize_base_url(raw)
        except ValueError as exc:
            print(f"  [!] {exc}. " + t("Please enter the Canvas home page address.", "请输入 Canvas 主页地址。"))
            continue
        if url != raw.strip().rstrip("/"):
            print("  -> " + t(f"Using {url}", f"将使用 {url}"))
        return url


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------


def run(cmd: list[str], **kwargs) -> int:
    print("  $ " + " ".join(str(c) for c in cmd))
    return subprocess.call([str(c) for c in cmd], cwd=ROOT, **kwargs)


def install_package(auth_mode: str) -> None:
    if sys.version_info < (3, 10):
        die("Python 3.10 or newer is required.", "需要 Python 3.10 或更高版本。")
    print("\n" + t("Step 2/3: installing into .venv", "第 2/3 步：安装依赖到 .venv"))
    if not venv_python().exists():
        venv.create(ROOT / ".venv", with_pip=True)
    if run([venv_python(), "-m", "pip", "install", "-e", ".[browser]"]) != 0:
        die("pip install failed; see the output above.", "pip 安装失败，请查看上面的输出。")
    if auth_mode == "browser":
        if run([venv_python(), "-m", "playwright", "install", "chromium"]) != 0:
            die(
                "Playwright browser download failed; see the output above.",
                "Playwright 浏览器下载失败，请查看上面的输出。",
            )


def ensure_gitignored() -> None:
    """Make sure a git checkout cannot accidentally commit .env."""
    if not (ROOT / ".git").exists():
        return
    ignored = subprocess.call(
        ["git", "check-ignore", "-q", ".env"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ignored == 0:
        return
    existing = GITIGNORE_PATH.read_text(encoding="utf-8") if GITIGNORE_PATH.exists() else ""
    if not existing.endswith("\n") and existing:
        existing += "\n"
    GITIGNORE_PATH.write_text(existing + ".env\n.canvas-storage-state.json\n", encoding="utf-8")
    print("  " + t("Added .env to .gitignore.", "已把 .env 加入 .gitignore。"))


def verify_token(base_url: str, token: str) -> bool:
    code = (
        "import sys, requests;"
        "r = requests.get(sys.argv[1] + '/api/v1/users/self',"
        " headers={'Authorization': 'Bearer ' + sys.stdin.read().strip()}, timeout=20);"
        "print(r.status_code); sys.exit(0 if r.ok else 1)"
    )
    proc = subprocess.run(
        [str(venv_python()), "-c", code, base_url],
        input=token,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    status = proc.stdout.strip()
    if proc.returncode == 0:
        print("  [ok] " + t("Canvas accepted the token.", "Canvas 已接受该 token。"))
        return True
    if not status.isdigit():
        print(
            "  [!] "
            + t(
                "Could not reach Canvas to check the token. Check the address and your network.",
                "无法连接 Canvas 来校验 token，请检查网址和网络。",
            )
        )
        return False
    print("  [!] " + t(f"Canvas rejected the token (HTTP {status}).", f"Canvas 拒绝了该 token（HTTP {status}）。"))
    return False


def print_next_steps(auth_mode: str, logged_in: bool) -> None:
    launcher = ROOT / ("run-canvas-mcp.sh" if os.name != "nt" else "")
    print("\n" + t("Step 3/3: connect it to your AI client", "第 3/3 步：连接到你的 AI 客户端"))
    if os.name == "nt":
        cmd = f'"{venv_python()}" -m canvas_mcp'
        print("  " + t("Use this command in your MCP client config:", "在 MCP 客户端配置里使用这条命令："))
        print(f"    {cmd}")
    else:
        print("  Claude Code:")
        print(f"    claude mcp add canvas-mcp -- {launcher}")
        print("  Codex:")
        print(f"    codex mcp add canvas-mcp -- {launcher}")
    print("  " + t("Then restart the client.", "然后重启客户端。"))
    if auth_mode == "browser" and not logged_in:
        print(
            "\n"
            + t(
                "Before first use, sign in once (approve Duo on your phone):",
                "首次使用前先登录一次（在手机上批准 Duo）：",
            )
        )
        print(f"    {venv_script('canvas-mcp-login')}")
    print(
        "\n"
        + t(
            "Your credentials are only in .env (private to your user account). Do not commit or share it.",
            "账号密码只保存在本地 .env（仅当前用户可读），请勿提交或分享。",
        )
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interactive Canvas MCP installer / Canvas MCP 安装向导")
    p.add_argument("--base-url", help="Canvas home page, e.g. https://canvas.ucsd.edu")
    p.add_argument("--auth-mode", choices=("browser", "token"), help="browser login (Duo) or API token")
    p.add_argument("--username", help="Canvas username or school email (browser mode)")
    p.add_argument("--password-stdin", action="store_true", help="read the password from stdin")
    p.add_argument("--token-stdin", action="store_true", help="read the API token from stdin")
    p.add_argument("--skip-install", action="store_true", help="only write .env, skip pip/playwright")
    p.add_argument("--skip-login", action="store_true", help="do not offer to run canvas-mcp-login")
    p.add_argument("--lang", choices=("en", "zh"), help="message language (default: from locale)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global ZH
    args = parse_args(argv)
    locale = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower()
    ZH = args.lang == "zh" or (args.lang is None and locale.startswith("zh"))

    if args.password_stdin and args.token_stdin:
        die("Use only one of --password-stdin and --token-stdin.", "--password-stdin 与 --token-stdin 只能选一个。")
    if not interactive() and not (args.base_url and args.auth_mode):
        die(
            "No terminal detected. Run this in a terminal, or pass --base-url and --auth-mode "
            "(and pipe the secret with --password-stdin / --token-stdin).",
            "没有检测到终端。请在终端里运行，或传入 --base-url 与 --auth-mode"
            "（密码/token 用 --password-stdin / --token-stdin 从标准输入传入）。",
        )

    existing = read_env_keys(ENV_PATH)
    print(t("Canvas MCP installer", "Canvas MCP 安装向导"))
    print(t("Step 1/3: your Canvas login", "第 1/3 步：填写 Canvas 登录信息"))
    print(
        "  "
        + t(
            "Saved only to .env on this computer; the password is not shown while you type.",
            "只保存到本机的 .env；输入密码时不会显示。",
        )
    )

    # Base URL
    if args.base_url:
        try:
            base_url = normalize_base_url(args.base_url)
        except ValueError as exc:
            die(f"Bad --base-url: {exc}", f"--base-url 不正确：{exc}")
    else:
        base_url = prompt_base_url(existing.get("CANVAS_BASE_URL", ""))

    # Auth mode
    auth_mode = args.auth_mode
    if not auth_mode:
        print(
            "\n"
            + t(
                "Login method:\n  1) Browser login with username + password (+ Duo)\n"
                "  2) Canvas API token (more reliable; create one in Canvas > Account > Settings)",
                "登录方式：\n  1) 浏览器登录：用户名 + 密码（+ Duo）\n"
                "  2) Canvas API token（更稳定；在 Canvas 的 账户 > 设置 中创建）",
            )
        )
        auth_mode = "token" if ask("1 / 2", "1") == "2" else "browser"

    updates: dict[str, str] = {"CANVAS_BASE_URL": base_url}
    secret_for_check = ""

    if auth_mode == "token":
        if args.token_stdin:
            token = sys.stdin.readline().strip()
        else:
            token = ask_secret(t("Canvas API token", "Canvas API token"), "CANVAS_ACCESS_TOKEN" in existing)
        if not token:
            if "CANVAS_ACCESS_TOKEN" not in existing:
                die("A token is required.", "必须提供 token。")
        else:
            updates["CANVAS_ACCESS_TOKEN"] = token
            secret_for_check = token
    else:
        username = args.username or ask(
            t("Canvas username or school email", "Canvas 用户名或学校邮箱"), existing.get("CANVAS_EMAIL") or None
        )
        if not username:
            die("A username is required.", "必须提供用户名。")
        if args.password_stdin:
            password = sys.stdin.readline().strip()
        else:
            password = ask_secret(t("Password", "密码"), "CANVAS_PASSWORD" in existing)
        if not password and "CANVAS_PASSWORD" not in existing:
            die("A password is required.", "必须提供密码。")
        updates.update(
            {
                "CANVAS_AUTH_MODE": "browser",
                "CANVAS_EMAIL": username,
                # Absolute path: a relative one is resolved against whatever
                # directory the AI client launches the server from.
                "CANVAS_STORAGE_STATE": str(STORAGE_STATE_PATH),
            }
        )
        if password:
            updates["CANVAS_PASSWORD"] = password

    # Write .env (never .env.example)
    if ENV_PATH.exists() and interactive() and not ask_yes_no(
        t("\n.env already exists. Update it (other settings are kept)?", "\n.env 已存在，是否更新（其他设置会保留）？"),
        True,
    ):
        die("Cancelled; .env was not changed.", "已取消，.env 未被修改。")
    try:
        text = merge_env_text(ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else "", updates)
    except ValueError as exc:
        die(f"Cannot save that value: {exc}", f"无法保存该值：{exc}")
    write_private(ENV_PATH, text)
    ensure_gitignored()
    print("  [ok] " + t(f"Saved {ENV_PATH} (owner-only).", f"已保存 {ENV_PATH}（仅当前用户可读）。"))

    if not args.skip_install:
        install_package(auth_mode)

    logged_in = False
    if auth_mode == "token" and secret_for_check and not args.skip_install:
        verify_token(base_url, secret_for_check)
    elif auth_mode == "browser" and not args.skip_install and not args.skip_login and interactive():
        if ask_yes_no(
            t("\nSign in now? A browser opens and you approve Duo on your phone.", "\n现在登录吗？会打开浏览器，你在手机上批准 Duo。"),
            True,
        ):
            logged_in = run([venv_script("canvas-mcp-login")]) == 0

    print_next_steps(auth_mode, logged_in)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n" + t("Cancelled.", "已取消。"))
        raise SystemExit(130)

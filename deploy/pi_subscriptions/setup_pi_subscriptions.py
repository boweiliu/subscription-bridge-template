"""Let pi-dev chats on this machine run on the user's subscriptions. Run from the workspace root.

    uv run --no-sync python .external_worktrees/untitled-notes-voice/deploy/pi_subscriptions/setup_pi_subscriptions.py <command>

Commands:

``install``
    Copy the Claude Code add-on for pi (``extensions/pi-claude-code``, vendored from
    earendil-works/pi-claude-code), its login pointer (``extensions/claude-subscription-login.ts``),
    the Codex login bridge (``extensions/codex-subscription-login.ts``) and Meridian's pi add-on
    (``extensions/meridian``, vendored from rynfar/meridian) into ``~/.pi/agent/extensions``, which
    every pi agent on this machine loads.
``claude``
    ``install``, then make (or refresh) the chat app's "Claude subscription" pi account: a pi account
    whose only credential tells the add-on which signed-in Claude Code account folder to run on. Turns
    then go through the real ``claude`` program and count against the plan's limits, not API billing.
``claude-shared``
    ``install``, then run one shared Claude bridge for the whole machine (Meridian, as the supervisord
    program ``claude_subscription_bridge`` on 127.0.0.1:3456) and make (or refresh) the chat app's
    "Claude subscription (shared)" pi account, whose ``meridian/...`` models talk to it. Turns run the
    real ``claude`` program on the same signed-in login as ``claude``, but a Claude process lives only
    while a model step runs, and at most three run at once, instead of one kept warm per chat.
``codex``
    ``install``, then make a "ChatGPT subscription" pi account for each Codex (ChatGPT) account the
    chat app already has signed in. pi reads that account's own Codex login file on every request
    and writes refreshed tokens back into it, so Codex and pi share one login. With no Codex account
    on the machine, signs in with OpenAI's device code instead: prints a code to enter at the address
    shown, then waits (up to 15 minutes) for it.
``status``
    The pi accounts on this machine and which provider each one holds.

Accounts are written through the chat app's own account store (``imbue.chat.accounts``), under its
lock, on the bring-your-own-key lane, so the chat app lists them like any other pi account. The
most-recently-used account is put back afterwards: adding one never changes which account a plain
new chat starts on. OpenCode (Zen or Go) needs no help here: the chat app's sign-in takes its key.
"""

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from imbue.chat import accounts

HERE = Path(__file__).resolve().parent
PI_HOME_EXTENSIONS = Path.home() / ".pi" / "agent" / "extensions"
EXTENSION_ENTRIES = ("pi-claude-code", "claude-subscription-login.ts", "codex-subscription-login.ts", "meridian")
# The chat app's bring-your-own-key lane: its accounts run on the pi harness.
PI_KEY_LANE = "api-key"
CLAUDE_DISPLAY = "Claude subscription"
CODEX_DISPLAY = "ChatGPT subscription"
CLAUDE_PROVIDER = "claude-code"
CODEX_PROVIDER = "openai-codex"
# Any non-empty keys: requests resolve through the named login folder, never through these values.
CLAUDE_PLACEHOLDER_KEY = "claude-code-login"
CODEX_PLACEHOLDER_KEY = "codex-login"
SHARED_DISPLAY = "Claude subscription (shared)"
SHARED_PROVIDER = "meridian"
# Meridian runs without API-key protection on loopback; any non-empty key passes.
SHARED_PLACEHOLDER_KEY = "meridian"
BRIDGE_HOME = Path.home() / ".local" / "share" / "pi-subscriptions" / "meridian"
BRIDGE_PROGRAM = "claude_subscription_bridge"
BRIDGE_HEALTH_URL = "http://127.0.0.1:3456/health"
BRIDGE_CONF = f"""[program:{BRIDGE_PROGRAM}]
; The shared Claude bridge for pi-dev chats (written by setup_pi_subscriptions.py claude-shared in
; .external_worktrees/untitled-notes-voice/deploy/pi_subscriptions; rerun it to update).
command=python3 system/services/oom_priority/bin/oom_tag_service.py user {BRIDGE_HOME / "run.sh"}
directory=/home/user/workspace
autostart=true
autorestart=true
startsecs=5
startretries=5
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/supervisor/{BRIDGE_PROGRAM}-stdout.log
stderr_logfile=/var/log/supervisor/{BRIDGE_PROGRAM}-stderr.log
stdout_logfile_maxbytes=10MB
stderr_logfile_maxbytes=10MB
stdout_logfile_backups=3
stderr_logfile_backups=3
"""


def install() -> None:
    PI_HOME_EXTENSIONS.mkdir(parents=True, exist_ok=True)
    for name in EXTENSION_ENTRIES:
        source = HERE / "extensions" / name
        target = PI_HOME_EXTENSIONS / name
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    print(f"Installed the Claude Code add-on for pi into {PI_HOME_EXTENSIONS}")


def pi_accounts() -> list[tuple[accounts.Account, dict]]:
    """Every pi account with its auth.json (empty when unreadable)."""
    rows = []
    for account in accounts.read_index().accounts:
        harness = accounts.harness_for(account)
        if harness is None or harness.value != "pi-coding":
            continue
        try:
            auth = json.loads((accounts.account_dir(account.id) / "auth.json").read_text())
        except (OSError, ValueError):
            auth = {}
        rows.append((account, auth if isinstance(auth, dict) else {}))
    return rows


def claude_login_dir() -> Path:
    """The folder of this machine's signed-in Claude Code account (the chat app's anthropic lane)."""
    for account in accounts.read_index().accounts:
        folder = accounts.account_dir(account.id)
        if account.lane == "anthropic" and (folder / ".credentials.json").is_file():
            return folder
    raise SystemExit("No signed-in Claude Code account on this machine. Sign in to Claude in the chat app first.")


def link_extensions(folder: Path) -> None:
    """Let a pi run pointed at the account folder itself (the chat app's sign-in check) see the add-on."""
    link = folder / "extensions"
    if not link.exists() and not link.is_symlink():
        link.symlink_to(PI_HOME_EXTENSIONS)


def commit_keeping_mru(account_id: str, display: str) -> accounts.Account:
    previous = accounts.read_index().mru
    account = accounts.commit_account(account_id, PI_KEY_LANE, display)
    if previous and previous != account_id and accounts.account_exists(previous):
        accounts.set_mru(previous)
    return account


def write_auth(folder: Path, auth: dict) -> None:
    path = folder / "auth.json"
    path.write_text(json.dumps(auth, indent=2) + "\n")
    path.chmod(0o600)


def claude() -> None:
    install()
    login_dir = claude_login_dir()
    credential = {
        CLAUDE_PROVIDER: {
            "type": "api_key",
            "key": CLAUDE_PLACEHOLDER_KEY,
            "env": {"PI_CLAUDE_CODE_CONFIG_DIR": str(login_dir)},
        }
    }
    existing = next((account for account, auth in pi_accounts() if CLAUDE_PROVIDER in auth), None)
    if existing is not None:
        folder = accounts.account_dir(existing.id)
        write_auth(folder, credential)
        link_extensions(folder)
        print(f"Refreshed {existing.display!r} ({existing.id}); runs on the Claude login in {login_dir}")
        return
    account_id, folder = accounts.mint_account_dir()
    write_auth(folder, credential)
    link_extensions(folder)
    account = commit_keeping_mru(account_id, CLAUDE_DISPLAY)
    print(f"Added {account.display!r} ({account.id}); runs on the Claude login in {login_dir}")


def bridge_health() -> dict | None:
    try:
        with urllib.request.urlopen(BRIDGE_HEALTH_URL, timeout=3) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def start_bridge(login_dir: Path) -> None:
    """Install the shared bridge's launcher and (re)start it as a supervisord program."""
    claude_path = shutil.which("claude")
    if claude_path is None:
        raise SystemExit("The claude program is not installed on this machine")
    conf_dir = Path.cwd() / "system" / "supervisord.conf.d"
    if not conf_dir.is_dir():
        raise SystemExit("Run this from the workspace root (system/supervisord.conf.d not found)")
    BRIDGE_HOME.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "claude_bridge" / "run_meridian.sh", BRIDGE_HOME / "run.sh")
    guard = BRIDGE_HOME / "claude_subscription_only.py"
    shutil.copy2(HERE / "claude_bridge" / guard.name, guard)
    guard.chmod(0o755)
    env_file = BRIDGE_HOME / "claude-login.env"
    env_file.write_text(f"CLAUDE_CONFIG_DIR={login_dir}\nMERIDIAN_CLAUDE_PATH={claude_path}\n")
    env_file.chmod(0o600)
    (conf_dir / f"{BRIDGE_PROGRAM}.conf").write_text(BRIDGE_CONF)
    subprocess.run(["supervisorctl", "reread"], check=True, capture_output=True)
    subprocess.run(["supervisorctl", "update", BRIDGE_PROGRAM], check=True, capture_output=True)
    # update starts a new program but leaves a running one alone; restart so a changed launcher applies.
    subprocess.run(["supervisorctl", "restart", BRIDGE_PROGRAM], check=False, capture_output=True)
    # The first start installs Meridian, which takes a minute or two.
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        health = bridge_health()
        if health is not None:
            signed_in = (health.get("auth") or {}).get("loggedIn")
            print(f"Shared Claude bridge is up ({health.get('version')}); Claude login signed in: {signed_in}")
            return
        time.sleep(3)
    raise SystemExit(f"The shared Claude bridge did not come up; see /var/log/supervisor/{BRIDGE_PROGRAM}-*.log")


def claude_shared() -> None:
    install()
    login_dir = claude_login_dir()
    start_bridge(login_dir)
    credential = {SHARED_PROVIDER: {"type": "api_key", "key": SHARED_PLACEHOLDER_KEY}}
    existing = next((account for account, auth in pi_accounts() if SHARED_PROVIDER in auth), None)
    if existing is not None:
        folder = accounts.account_dir(existing.id)
        write_auth(folder, credential)
        link_extensions(folder)
        print(f"Refreshed {existing.display!r} ({existing.id}); runs through the shared Claude bridge")
        return
    account_id, folder = accounts.mint_account_dir()
    write_auth(folder, credential)
    link_extensions(folder)
    account = commit_keeping_mru(account_id, SHARED_DISPLAY)
    print(f"Added {account.display!r} ({account.id}); runs through the shared Claude bridge")


def pi_module_dir() -> Path:
    executable = shutil.which("pi")
    if executable is None:
        raise SystemExit("pi is not installed on this machine")
    current = Path(executable).resolve()
    while current != current.parent:
        if (current / "package.json").is_file() and (current / "node_modules" / "@earendil-works" / "pi-ai").is_dir():
            return current
        current = current.parent
    raise SystemExit("Could not find pi's install folder")


def codex_logins() -> list[accounts.Account]:
    """The chat app's Codex accounts signed in with ChatGPT (an API-key Codex account has no tokens)."""
    rows = []
    for account in accounts.read_index().accounts:
        try:
            auth = json.loads((accounts.account_dir(account.id) / "auth.json").read_text())
        except (OSError, ValueError):
            continue
        if account.lane == "openai" and isinstance(auth, dict) and (auth.get("tokens") or {}).get("refresh_token"):
            rows.append(account)
    return rows


def codex() -> None:
    install()
    logins = codex_logins()
    if not logins:
        codex_device_login()
        return
    existing = {
        (auth[CODEX_PROVIDER].get("env") or {}).get("PI_CODEX_HOME"): account
        for account, auth in pi_accounts()
        if isinstance(auth.get(CODEX_PROVIDER), dict)
    }
    for login in logins:
        home = str(accounts.account_dir(login.id))
        if home in existing:
            print(f"{existing[home].display!r} ({existing[home].id}) already runs on the Codex login {login.id}")
            continue
        account_id, folder = accounts.mint_account_dir()
        write_auth(folder, {CODEX_PROVIDER: {"type": "api_key", "key": CODEX_PLACEHOLDER_KEY, "env": {"PI_CODEX_HOME": home}}})
        link_extensions(folder)
        display = CODEX_DISPLAY if not login.name else f"{CODEX_DISPLAY} ({login.name})"
        account = commit_keeping_mru(account_id, display)
        print(f"Added {account.display!r} ({account.id}); runs on the Codex login in {home}")


def codex_device_login() -> None:
    account_id, folder = accounts.mint_account_dir()
    login = subprocess.run(
        ["node", str(HERE / "codex_device_login.mjs"), str(pi_module_dir()), str(folder / "auth.json")],
        timeout=16 * 60,
        check=False,
    )
    if login.returncode != 0 or not (folder / "auth.json").is_file():
        accounts.discard_account_dir(account_id)
        raise SystemExit("ChatGPT sign-in did not finish; nothing was added")
    account = commit_keeping_mru(account_id, CODEX_DISPLAY)
    print(f"Added {account.display!r} ({account.id})")


def status() -> None:
    rows = pi_accounts()
    if not rows:
        print("No pi accounts on this machine")
    for account, auth in rows:
        print(f"{account.id}  {account.display:<30} {', '.join(sorted(auth)) or '(no credential)'}")
    health = bridge_health()
    print(f"Shared Claude bridge: {'up, ' + str(health.get('version')) if health else 'not running'}")


def main() -> None:
    commands = {"install": install, "claude": claude, "claude-shared": claude_shared, "codex": codex, "status": status}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit(f"usage: setup_pi_subscriptions.py {{{','.join(commands)}}}")
    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()

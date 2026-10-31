#!/usr/bin/env python3
"""Relay Claude's protocol unchanged; stop on an observed usage-credit charge.

Like pi-claude-code's billing guard, this reacts to the upstream billing event.
It cannot undo tokens already charged before that event arrives.
"""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path


def main() -> int:
    executable = os.environ.get("MERIDIAN_REAL_CLAUDE_PATH")
    if not executable:
        print("Claude subscription billing: real Claude executable is not configured", file=sys.stderr)
        return 86
    # SDK model discovery and version probes do not perform inference.
    if "--output-format" not in sys.argv[1:]:
        os.execv(executable, [executable, *sys.argv[1:]])
    block_file = Path(os.environ["MERIDIAN_BILLING_BLOCK_FILE"])
    if block_file.exists():
        print("Claude subscription billing: a usage-credit charge was observed; bridge remains blocked", file=sys.stderr)
        return 86
    child = subprocess.Popen([executable, *sys.argv[1:]], stdin=sys.stdin.buffer, stdout=subprocess.PIPE)

    def forward_signal(signum, _frame):
        if child.poll() is None:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)
    assert child.stdout is not None
    try:
        for line in child.stdout:
            try:
                event = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                event = None
            if (
                isinstance(event, dict)
                and event.get("type") == "rate_limit_event"
                and isinstance(event.get("rate_limit_info"), dict)
                and event["rate_limit_info"].get("isUsingOverage") is True
            ):
                block_file.parent.mkdir(parents=True, exist_ok=True)
                block_file.write_text(json.dumps(event, indent=2) + "\n")
                print(
                    "Claude subscription billing: upstream reported usage credits instead of plan limits; "
                    "stopping this request. Turn off usage credits in Claude settings to prevent charges.",
                    file=sys.stderr,
                    flush=True,
                )
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                return 86
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
        return child.wait()
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())

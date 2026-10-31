#!/usr/bin/env python3
"""Create a private repo on the signed-in GitHub account and push a prepared directory to it, through latchkey.

    python3 push_private_repo.py --name <repo> --description "<one line>" --source <dir> [--dry-run] [--existing]

The source directory is a git repository whose current commit is what gets published as ``main``. The script
refuses to go on when the tracked files include anything that looks like a secret or a data folder. It then
(1) checks GitHub access, (2) creates the repo as PRIVATE, (3) closes issues, the wiki, projects, discussions and
outside pull requests, (4) pushes the commit to ``main`` through the latchkey gateway (no token is ever put in a URL or
written to disk), (5) points the source's ``origin`` at the gateway URL, and (6) checks that the repo is private and
that ``main`` is the commit that was pushed. ``--existing`` skips creation for a repo that already exists.
``--dry-run`` prints the plan and touches nothing, not even the network.
"""

import argparse
import json
import os
import re
import subprocess
import sys

NAME_PATTERN = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._-]*$")
# Tracked paths that must never reach GitHub from here: environment files, the workspace's secrets and data folders,
# and files that hold a saved login or a captured request.
FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)\.env(\.|$)"),
    re.compile(r"(^|/)\.secrets(/|$)"),
    re.compile(r"(^|/)data(/|$)"),
    re.compile(r"(^|/)browser_state"),
    re.compile(r"(^|/)credentials\.json"),
    re.compile(r"cookie-handoff-invocations"),
    re.compile(r"(^|/)request\.(env|json)$"),
)


class PublishError(Exception):
    pass


def check_name(name):
    if not NAME_PATTERN.match(name or ""):
        raise PublishError(
            "The repo name may use letters, digits, '.', '_' and '-' only, and may not start with '-'."
        )
    return name


def forbidden_files(tracked):
    """The tracked paths that must not be published."""
    return [
        path
        for path in tracked
        if any(pattern.search(path) for pattern in FORBIDDEN_PATTERNS)
    ]


def create_payload(name, description):
    return {"name": name, "description": description, "private": True}


def lockdown_payload():
    return {
        "pull_request_creation_policy": "collaborators_only",
        "has_issues": False,
        "has_wiki": False,
        "has_projects": False,
        "has_discussions": False,
    }


def lockdown_gaps(repo):
    """The collaboration surfaces a repo answer shows as still open (GitHub can apply a combined update only in part)."""
    return [
        key
        for key in ("has_issues", "has_wiki", "has_projects", "has_discussions")
        if repo.get(key) is not False
    ]


def gateway_url(gateway, owner, name):
    return f"{gateway.rstrip('/')}/gateway/https://github.com/{owner}/{name}.git"


def push_command(source, url, password, override=None):
    """The git command that pushes HEAD to main through the gateway; its headers carry the gateway's own auth."""
    command = [
        "git",
        "-C",
        source,
        "-c",
        f"http.extraHeader=X-Latchkey-Gateway-Password: {password}",
    ]
    if override:
        command += [
            "-c",
            f"http.extraHeader=X-Latchkey-Gateway-Permissions-Override: {override}",
        ]
    return command + ["push", url, "HEAD:refs/heads/main"]


def redacted(command):
    """The command with the gateway's auth material blanked out, safe to print."""
    return [
        re.sub(r"(X-Latchkey-Gateway-[A-Za-z-]+: ).*", r"\1***", part)
        for part in command
    ]


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, **kwargs)


def api(method, path, body=None):
    command = ["latchkey", "curl", "-sS", "-X", method, "https://api.github.com" + path]
    if body is not None:
        command += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    done = run(command)
    if done.returncode:
        raise PublishError(
            f"The GitHub call {method} {path} could not be made: {done.stderr.strip()[:200]}"
        )
    try:
        return json.loads(done.stdout or "{}")
    except ValueError:
        raise PublishError(
            f"GitHub answered {method} {path} with something that is not JSON."
        )


def tracked_files(source):
    done = run(["git", "-C", source, "ls-files"])
    if done.returncode:
        raise PublishError(
            f"{source} is not a git repository with commits ({done.stderr.strip()[:120]})."
        )
    files = [line for line in done.stdout.splitlines() if line]
    if not files:
        raise PublishError(
            f"{source} has no committed files; commit what should be published first."
        )
    return files


def head_sha(source):
    done = run(["git", "-C", source, "rev-parse", "HEAD"])
    if done.returncode:
        raise PublishError("The source has no commit to publish.")
    return done.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument(
        "--existing",
        action="store_true",
        help="the repo exists already; only push and verify",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_name(args.name)
        bad = forbidden_files(tracked_files(args.source))
        if bad:
            raise PublishError(
                "Refusing to publish; these tracked files look like secrets or data: "
                + ", ".join(bad[:10])
            )
        sha = head_sha(args.source)
        gateway = os.environ.get("LATCHKEY_GATEWAY", "")
        password = os.environ.get("LATCHKEY_GATEWAY_PASSWORD", "")
        if not gateway or not password:
            raise PublishError(
                "LATCHKEY_GATEWAY and LATCHKEY_GATEWAY_PASSWORD are not set; this must run inside the workspace."
            )
        if args.dry_run:
            print(
                f"Would create private repo {args.name!r} ({args.description!r}) unless --existing,"
            )
            print(
                "lock down issues, wiki, projects, discussions and outside pull requests,"
            )
            print(
                f"and push {sha[:7]} from {args.source} to main through the gateway. Nothing was done."
            )
            return 0
        me = api("GET", "/user")
        owner = me.get("login")
        if not owner:
            raise PublishError(
                "GitHub access is not approved yet (the /user call returned no login). Request it first."
            )
        if not args.existing:
            created = api(
                "POST", "/user/repos", create_payload(args.name, args.description)
            )
            if created.get("full_name") != f"{owner}/{args.name}":
                raise PublishError(
                    "The repo was not created: "
                    + str(created.get("message") or created)[:200]
                )
            if created.get("private") is not True:
                raise PublishError(
                    "The new repo is not private; stop and fix it by hand before pushing anything."
                )
        lock = api("PATCH", f"/repos/{owner}/{args.name}", lockdown_payload())
        for key in lockdown_gaps(lock):
            # One field at a time: a combined update has been seen to leave one of them on.
            lock = api("PATCH", f"/repos/{owner}/{args.name}", {key: False})
        if lockdown_gaps(lock):
            print(
                "Warning: these repo features could not be switched off; check them by hand: "
                + ", ".join(lockdown_gaps(lock)),
                file=sys.stderr,
            )
        url = gateway_url(gateway, owner, args.name)
        override = os.environ.get("LATCHKEY_GATEWAY_PERMISSIONS_OVERRIDE")
        pushed = run(push_command(args.source, url, password, override))
        if pushed.returncode:
            raise PublishError(
                "The push failed: "
                + pushed.stderr.replace(password, "***").strip()[:300]
            )
        if run(["git", "-C", args.source, "remote", "get-url", "origin"]).returncode:
            run(["git", "-C", args.source, "remote", "add", "origin", url])
        else:
            run(["git", "-C", args.source, "remote", "set-url", "origin", url])
        repo = api("GET", f"/repos/{owner}/{args.name}")
        main_commit = api("GET", f"/repos/{owner}/{args.name}/commits/main")
        if repo.get("private") is not True:
            raise PublishError("The repo is NOT private. Fix this immediately.")
        if main_commit.get("sha") != sha:
            raise PublishError("The repo's main is not the commit that was pushed.")
        print(f"Published {owner}/{args.name} (private), main at {sha[:7]}.")
        print("Fetch and push from the clone need these git options:")
        print(
            "  -c 'http.extraHeader=X-Latchkey-Gateway-Password: $LATCHKEY_GATEWAY_PASSWORD'"
        )
        return 0
    except PublishError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

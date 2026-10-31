---
name: publish-app-bowei-style
description: Publish an app built in this workspace the way Bowei does it: a private repo under his GitHub account (boweiliu/<app>) with fresh history holding the code, tests, docs and runbooks, the skills and the memories that go with it, plus a public Studio template of the generalized app. Use when he says to publish, ship, or "boweiliu-style" publish an app, or asks for the app's private repo and its template.
compatibility: Requires latchkey with GitHub access approved in the Imbue Studio app (github-rest-api with github-read-user and github-write-all, and github-git with github-git-write), python3, and the publish-template skill for the public half.
metadata:
  author: boweiliu
---

# Publish an app, Bowei style

Bowei's apps do not stay as a folder in the workspace monorepo. Each one gets its own repo with its own fresh history
(see the `apps-in-external-repos` memory), and a finished one is also offered to other people as a Studio template. This
skill is that whole recipe, in the order he expects it:

1. **Documentation gate.** Everything someone needs to set the app up again from nothing is written down, above all the
   runbooks for any external connection (for LinkedIn: how the login is captured and how the connection is turned on).
2. **A private repo** `boweiliu/<app>` with fresh history: all the code and tests, the documents and runbooks, the
   skills that operate it, and the memories that carry what was learned. Cloned at `.external_worktrees/<app>/`.
3. **A public Studio template** of the generalized app, through the `publish-template` skill.

Do them in this order. The private repo is the complete record; the template is the shareable subset with every
personal detail generalized away.

## Hard rules

- **Never publish a secret or someone's private data**, in either repo. That means `data/`, anything under
  `data/.secrets/`, saved sessions, cookies, captured responses, raw message dumps, and the app's own stored data. Run
  `bash .agents/skills/publish-template/scripts/scan_secrets.sh <paths>` over the whole assembled tree before every
  push (it runs both scanners and fails closed), then grep for personal identifiers (see "Scrub list").
- **History is fresh.** Build the repo from a clean directory with `git init`. Never split or filter monorepo history,
  never push the workspace's own commits.
- **Everything goes through latchkey.** No `gh` CLI, no tokens in URLs, no tokens on disk.
- **The private repo is private, always.** Only the template is public, and only because Bowei asked for it.
- **A public template follows `publish-template` exactly** (bootable full tree, one snapshot commit on the template
  base, validator clean). Never push a hand-picked subset of files as "the template".
- **An explicit "preapproved" from Bowei for the public step stands in for the confirmation messages in
  `publish-template` sections 1 and 6.** It does not relax anything else in that skill: the generalization,
  the scans, the validator and the thumbnail all still apply. Say in the final message that the confirmation was
  skipped on his word, and list exactly what shipped so he can check it.
- Commands that mention the secrets folder are blocked by the workspace's secrets guard when typed in a shell. Write
  files that talk about it with the Write or Edit tool, and run helpers as
  `python3 system/scripts/with_secrets.py <file> -- <command>` with nothing in front of it.

## 0. GitHub access

Probe, and request what is missing (the exact calls are in `publish-template` section 7; each request is its own
tool call):

```bash
latchkey curl -sf https://api.github.com/user          # needs github-read-user
```

Creating a repo is `POST /user/repos`, which needs `github-write-all` (`github-write-repos` is not enough). The push
needs `github-git-write`. Bowei's account is `boweiliu`. If both are already granted, do not ask again.

## 1. Documentation gate

Before building anything, check the app has all of these, and write what is missing. Read from the code, the existing
guides, and the earlier chats that built it (`find-transcripts`; worker chats are stored locally even after they were
stopped). **Only write steps that were actually run or are visible in the code.** Mark anything unverified as
unverified. If a runbook cannot be reconstructed from what is on this machine, stop and ask Bowei for the earlier chat
logs rather than inventing it.

| Document | What it must answer |
| --- | --- |
| `README.md` | What the app is, who it is for, the one-paragraph architecture, how to run and test it, where each part lives. |
| Setup runbook | Starting from nothing, every step to get the app working with the real external service: accounts, grants, devices, secrets, in order, with the check that proves each step worked. |
| Operations runbook | Day-two work: renewing an expired login, what each error means, how to restart, where the logs and data are, safe limits. |
| Investigation notes | What was tried, what worked, what failed and why (so nobody repeats it), and any line that was deliberately not crossed. |
| Design notes | How the pieces fit, the safety rules (confirmation before sending, caps, records), and what the data on disk is. |
| Tests | How to run them from the workspace root, what is faked, how to keep them away from the real service. |
| Changelog | What changed, in plain words. |

For a service the user has to connect on their own machine (LinkedIn is the example), the setup runbook must name the
device, the folder grants, the launcher, and the exact check after each step.

## 2. The private repo

Work in `.external_worktrees/<app>/` (gitignored; create it fresh). The layout matches Bowei's other app repos: the
repo root is the app package, so a clone can sit in `.external_worktrees/` and be wired in by config alone.

```
README.md  pyproject.toml  app.toml  icon.svg  .gitignore
src/<package>/...            the app
test_*.py, conftest.py, ...  its tests and fixtures
changelog/  docs/            what the app already carries
workspace/
  scripts/                   helpers that live in system/scripts/ in a workspace, with their tests
  guides/                    workspace guides that belong to the app (docs/guides/...)
  supervisord/<app>.conf     the program entry for the workspace
docs/                        README-level docs: runbooks, investigation, design
skills/<name>/SKILL.md       every skill that operates the app, plus this publishing skill
memories/*.md                the memories about the app and the standing rules it relies on
deploy/                      sync and schedule scripts if the app is double-deployed
```

Copy files from the workspace; do not move them (the app keeps running from where it is until Bowei decides to wire it
to the clone, which is a separate change: install the clone with `uv tool install -e`, point the supervisord program at
it with `forward_port.py --manifest .external_worktrees/<app>/app.toml`, then `supervisorctl reread && update`).

Memories: copy the files in `data/memories/` that are about this app, and the ones holding rules it follows
(`apps-in-external-repos`, `test-sends-stub-the-sender`, and similar). They are private notes, so they belong only in
the private repo, never in the template.

### Scrub list

Before the first commit, grep the assembled tree and decide each hit (it stays in the private repo only if it is
Bowei's own working note, never in anything public): his name and email, device ids (`host-...`), IP addresses,
home-directory paths of his machines, real profile ids and urns, names of real people in fixtures or docs, real
message text, session cookies and tokens (`li_at`, `JSESSIONID`, `Cookie:` lines, `csrf-token` values), and the
contents of any `.env` in `data/.secrets/`.

### Create and push

Use the helper (it probes, creates the repo private, locks down issues/wiki/projects/discussions and
pull requests, pushes `main` through the gateway, and verifies):

```bash
python3 .agents/skills/publish-app-bowei-style/scripts/push_private_repo.py \
    --name <app> --description "<one line>" --source .external_worktrees/<app>
```

`--dry-run` prints what it would do and touches nothing. The helper refuses a source tree that has no commit, a
`.env` file, or a `data/` folder. After it succeeds, the clone's `origin` is the gateway URL (credentials are never
stored in it), so later fetches and pushes need the two headers the helper prints at the end.

Verify before saying it is done: the API lists the files you expect, `private` is `true`, and a fresh
`git ls-remote` shows `main` at your commit.

## 3. The public Studio template

Follow `publish-template` end to end. What to give it:

- **Include** the app package, its supervisord drop-in, the helper scripts and their tests, the generalized setup
  runbook (the version with placeholders, never the one with his device ids), and the skills that operate the app.
- **Do not include** the personal guides, the investigation notes that name real people, memories, `data/`, or
  anything from the private repo's `memories/`.
- **Modifications for the published version only** (write them as rules, never as the removed value): replace every
  real profile id, name and message in fixtures and tests with invented ones and update the assertions to match;
  make hard-coded device ids, folders and paths into settings with neutral defaults; remove his account names.
- **Requirements** (the activation lines in `template.md`): every external connection and grant the adopter must set
  up, each with its check. For LinkedIn that is the custom LinkedIn connection with "Proxy through my desktop", a
  read and write file-sharing grant for one folder on the adopter's Mac, and a Mac with a Chromium-based browser.
- **Visibility:** public, MIT license (say so in the final message).

When the user has preapproved the public step, skip the confirmation questions but not the verification: scan,
generalization grep over the assembled tree, validator, and a look at the rendered README and thumbnail.

Generalize in the **source** first (invented names and ids in fixtures and tests, settings instead of device ids), so
the template needs no published-version modifications and the private repo is clean too. Declare every script and the
skill the app needs in the app's `app.toml` `[[references]]`, then `uv run app-manifest footprint <app.toml>` gives the
include list.

Things that went wrong the first time (2026-10-31, the LinkedIn Inbox) and how they were handled:

- **`create_worker.py launch` refuses while other chats have uncommitted or untracked files in the workspace.** Do not
  commit or move their files. Make the assembly worktree yourself (`git worktree add -b mngr/<slug>
  /home/user/worktrees/<slug>-<id> HEAD`), run the worker's steps in it (the publish-template task body is the
  checklist), and remove it afterwards. Say in the final message that you did.
- **Validation exit 6 on stock programs (host-backup, share-gateway):** the validator's secret-reference check read
  comments in program configs. Fixed locally in `system/services/env_converge/src/env_converge/template_manifest.py`
  and reported to Imbue (one report). The later gates run inside the assembled tree, which has the base's older schema
  module and still fails; run them with the current `validate_template.py` and the fixed schema module copied side by
  side into a scratch folder, the way `build_template.sh` does.
- **The secret scanners are heavy and get stopped by the memory guard** when other chats are running. Retry when
  `/mngr-vol/.host-meminfo` shows more than about 1.5 GB available; never skip the scan.
- **A fixture can trip the scanner with a made-up value** (a base64-looking sync token). Replace it with an obviously
  invented string at the source; do not allowlist.
- **The public template has no LICENSE file** (the flow only states MIT in the confirmation). Tell the user.

## 4. Close out

- Record the publish in memory (private repo URL, template URL, what is where, what was left out and why), and add the
  one-line pointer in `MEMORY.md`.
- Tell Bowei both links, what the template leaves out, and anything he must still do (for example wiring the running
  app to the clone). Put the facts first and keep it short.
- Never report a step done that did not complete. If the template could not be published, say which gate failed.

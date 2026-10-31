---
title: "Subscription Bridge"
description: "Shared Claude subscription bridge and subscription manager for pi-dev chats"
thumbnail: "template.svg"
version: v1
format: v2
---

# Subscription Bridge

This file is the manifest for the **Subscription Bridge** template (slug:
`subscription-bridge`). It is the one document a future agent reads to understand,
present, and adapt this template. If you are an agent in a workspace that was
created from this template, this file is your script: read all of it, then
follow "How to adapt it" below.

## What it is

The Subscription Bridge template provides a shared local daemon and billing guard that connects coding agent sessions to an existing Claude subscription. Instead of spawning multiple helper processes that consume unconstrained memory, the bridge maintains a single local daemon on port 3456 with strict concurrency capping (maximum 3 concurrent Claude CLI processes) and idle memory reclamation (~75–105 MB). It ensures pi-dev and chat sessions can run keyless tool-calling workloads using an active Claude Pro or Max subscription without incurring unexpected API overages or exhaustion.

## How it works

The snapshot includes these paths (each is a repo-root-relative path copied
from the original agent onto a clean default-workspace-template base):

- `deploy/pi_subscriptions`: Deployment scripts and account configuration helpers (`setup_pi_subscriptions.py`) for registering pi chat agent accounts and configuring authentication to point to the local bridge.
- `system/supervisord.conf.d/claude_subscription_bridge.conf`: The supervisord drop-in configuration that manages the `claude_subscription_bridge` background daemon, ensuring it auto-starts on boot and runs continuously.
- `.agents/skills/publish-app-bowei-style`: The publication workflow skill used to package and synchronize workspace creations into private development repositories and public Studio templates.

At runtime, supervisord automatically starts the bridge daemon listening on localhost:3456. Agent sessions communicate with the daemon over local HTTP to coordinate model execution against the host's installed Claude CLI (`/root/.local/bin/claude`), enforcing concurrency limits and preventing overage charges.

## Recipe

This template is version `v1`. It is not a fork of the
workspace it came from -- it is DERIVED from it by a recipe: include these
paths, leave these out, apply these published-version rules. An update re-runs
the recipe against the current workspace and publishes the result as the next
version, so anything excluded stays excluded even though it still exists in the
source workspace.

The recipe is machine-read, so it lives in the sibling
[`template.toml`](template.toml) -- its `[recipe]` table -- along with
the structured requirements and the environment this template needs
installed. That file is authoritative for all of it; this one holds the prose.

## Requirements

Everything the adopting agent must deal with before this template is really
theirs. Two kinds of entry, handled at different times:

- **Activation** -- what must be SET UP before anything runs, in the
  machine-readable `requires_` forms below. The adopting agent acts on these
  ITSELF, first, before asking anything.
- **Adaptation** -- what must be DECIDED or REWIRED, in prose. Worked through
  interactively with the user, after activation.

- requires_llm: calls Claude through the local signed-in Claude Code CLI (/root/.local/bin/claude) using an existing Claude subscription

- Requires an active Claude subscription sign-in on the host machine: run claude or sign in with a Claude Pro or Max subscription in the chat app or CLI.

## Environment

What this template needs INSTALLED, beyond what the template already has.
Declared in `template.toml`'s `[environment]` table; an adopting agent
converges it at ITS OWN pinned apt snapshot timestamp, so package versions come
out consistent with the rest of that agent's environment rather than frozen to
whatever this publisher happened to have.

Nothing extra -- runs on the stock workspace environment.

## How to adapt it

Instructions for the NEXT agent -- the one adapting this template into a
new agent. This is the `use-template` skill's template path; in short:

1. Read this entire file first, especially "Requirements" below. It holds two
   kinds of entry and they are handled at different times: the machine-readable
   `requires_` lines are ACTIVATION (set them up before anything runs), and
   the prose bullets are ADAPTATION (decide or rewire them afterwards).
2. Present the template to the user in plain, non-technical language: what
   it is, what it does, and what it needs from them (name the activation
   requirements).
3. Ask whether they want to use the same connectors (e.g. their own Slack).
   If YES: ACTIVATE FIRST -- initiate every `requires_permission` line NOW
   via a latchkey permission request (see the `connect-external-service` skill; the request
   opens the approval/login flow in the Imbue Studio app), wire up any
   `requires_secret` values, start the services, and get the app showing
   THE USER'S OWN DATA. Done for a data-backed app means the user can open it
   and see their own data -- NOT that a service starts or an endpoint returns
   200. Then tell them it is live and to take a look.
4. Only AFTER that (or immediately, if they chose different connectors -- the
   swap is then the first adaptation) ask: "How do you want to adapt it?"
5. Work through each requirement interactively, one at a time. Translate each
   into plain language, ask for a decision only when you genuinely need one,
   and resolve the obvious ones yourself.
6. When done, append a dated entry to "Adaptation history" below (never
   rewrite earlier entries) and commit.

## Publication history

This template's changelog: what each published version changed. The PUBLISHER
appends one entry per version (newest last); earlier entries are never rewritten.
This is distinct from "Adaptation history" below, which is the ADOPTERS' log.

### v1 (2026-10-31) -- Initial release of the shared Claude subscription bridge for pi-dev

## Adaptation history

Each agent that adapts this template appends one dated entry below. Earlier
entries are never rewritten.

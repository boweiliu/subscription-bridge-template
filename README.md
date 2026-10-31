<p align="center">
  <img alt="Subscription Bridge" src="template.svg" width="480">
</p>

# Subscription Bridge

<p align="center">
  <a href="https://studio.imbue.com/open?git_url=https://github.com/boweiliu/subscription-bridge-template"><img alt="Open in Imbue Studio" height="64" src="https://img.shields.io/badge/Open%20in%20Imbue%20Studio-D8D1C0?style=for-the-badge"></a>
</p>

Didn't work? Create a Studio workspace and paste this to your agent:
` /use-template https://github.com/boweiliu/subscription-bridge-template`

## Why you care

Running coding agents with Claude often leads to runaway background processes or accidental API overage costs. Subscription Bridge gives your workspace a managed, shared bridge daemon that routes agent model calls through an existing Claude Pro or Max subscription with strict concurrency limits and automatic idle memory cleanup.

## How to use it

Once adopted, the bridge runs automatically via supervisord on port 3456:
- Check daemon status: `python3 deploy/pi_subscriptions/setup_pi_subscriptions.py status`
- Register an agent account: `python3 deploy/pi_subscriptions/setup_pi_subscriptions.py enable`
- The bridge throttles concurrency to a maximum of 3 concurrent Claude CLI workers and reclaims memory when idle.

## Ideas for making it yours

- Adjust the concurrency cap in the supervisor config to match your host machine's CPU and memory limits.
- Add alerts or notifications when subscription quotas approach usage thresholds.
- Wire custom model aliases into your agent configs to selectively route specific tasks through the bridge.

## What this is

This repository is a published **Imbue Studio template**: a clean, bootable
snapshot of what an agent built, ready to adapt into your own. It is NOT the
generic workspace template -- it is this specific project.

[`template.md`](template.md) is the full manifest -- what it is, how it
works, what it needs to run, and what to adapt -- with the
machine-readable half (recipe, requirements, and the environment it needs
installed) in [`template.toml`](template.toml).

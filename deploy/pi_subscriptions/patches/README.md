# Chat app patches for pi-dev subscriptions

Changes to the workspace's built-in chat app (`system/apps/chat`, a critical app) that pi-dev
subscriptions need. They are kept here as patch files so any workspace can take them, and so a
Studio template fork can carry them by default, until the same fixes land upstream (both were
reported to imbue on 2026-10-30 through the in-app bug report).

## `chat-pi-extension-models.patch`

Made against minds-v0.9.4 (workspace commit `18d8dcaaf`), as hardened and applied live on
fresh087 on 2026-10-30 (the chat app's full suite, 2510 tests, passed with it). It changes only
`imbue/chat/harnesses/pi_coding/model.py`; the rest is tests (`model_test.py`, a fixture trimmed
from a real saved store under `pi_coding/testdata/`, and a route test in `server_test.py`).

**1. The chat app offers models that pi extensions add.** The chat app builds pi's model catalog
from pi-ai's bundled data files only, and checks every model pick (at create and on the model
bar) against it. Models a pi extension registers, like the Claude Code add-on's
`claude-code/claude-opus-5-5`, were refused with "Unknown model", the picker left them out
(though `pi --list-models` lists them), and the chip showed no label. pi saves what an extension
discovers in `models-store.json` in each pi config dir (`{provider: {"models": [...]}}`, the same
model fields as the bundled data, efforts included). The patched catalog adds every saved model
whose provider pi-ai does not bundle, read from the host's pi agents
(`$MNGR_HOST_DIR/agents/*/plugin/pi_coding/models-store.json`), re-scanned at most every 30 seconds.
A model therefore appears once any pi agent on the machine has run with the extension; the
voice app's own path (create empty, set the model through pi) does not need it.

**2. A model-and-effort switch keeps the effort.** mngr's pi lifecycle extension
(`mngr_pi_lifecycle.ts`, `applySwitch`) sets the effort before the model, and pi then moves the
effort to the nearest one the new model has: a chat created on `opencode-go/glm-5.3` at "low"
(GLM-5.3 offers low, high, max) ended on "high". After writing a switch that changes the model,
the patched resolver waits for pi to take the model up and, if the effort did not land, writes
the same intent once more; with the model already in place pi changes only the effort. The real
fix belongs in mngr (apply the model first); this patch can be dropped once it ships.

### Applying it

The chat app is critical, so a workspace agent applies it through the update-app skill's careful
flow (worktree, preview, harden worker, atomic apply), never by editing the served tree:

```sh
git worktree add -b mngr/update-pi-extension-models data/.tasks/critical-live/update-pi-extension-models HEAD
git -C data/.tasks/critical-live/update-pi-extension-models apply \
    "$PWD/.external_worktrees/untitled-notes-voice/deploy/pi_subscriptions/patches/chat-pi-extension-models.patch"
```

then continue from the careful flow's preview step. `git apply --check` first: on an older chat
app (talker-086 is on minds-v0.8.6) the patch does not apply as is and needs porting by hand; the
logic is self-contained in the pi catalog module, so the port is small.

In a Studio template fork, apply it to the fork's tree once and commit it there, so every
workspace made from the fork starts with it.

### Checking it worked

- `GET /api/harnesses` lists `claude-code/...` ids under `pi-coding` once a Claude subscription
  pi chat has run on the machine.
- On such a chat, the model picker offers Opus 5.5, Sonnet 5.5, Fable 5.1 and Haiku 5.5, the chip
  names the model, and a switch to `claude-code/claude-sonnet-5-5` at "low" lands as that.
- A chat created through the chat app on `opencode-go/glm-5.3` at "low" stays on "low"
  (`model_state.json` in the chat's agent folder).

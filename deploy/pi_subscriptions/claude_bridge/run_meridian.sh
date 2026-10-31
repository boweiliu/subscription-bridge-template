#!/bin/bash
# The machine's shared Claude bridge for pi-dev chats on the Claude subscription: one Meridian server
# (github.com/rynfar/meridian) that every pi chat's "meridian" provider talks to on 127.0.0.1:3456.
# Each model step runs the real `claude` program on the signed-in Claude Code login, and that process
# exits when the step ends, so an idle pi chat holds no Claude in memory. At most
# MERIDIAN_MAX_CONCURRENT steps run at once; the rest wait their turn.
#
# setup_pi_subscriptions.py claude-shared copies this file to ~/.local/share/pi-subscriptions/meridian/run.sh,
# writes claude-login.env beside it, and points a supervisord program at it. Meridian itself is
# installed next to it on first start (and again after a restore, since backups skip node_modules).
set -euo pipefail
BRIDGE_HOME="$(cd "$(dirname "$0")" && pwd)"
VERSION=1.87.0
SCRUB_VERSION=0.2.3
installed="$(node -p "require('$BRIDGE_HOME/node_modules/@rynfar/meridian/package.json').version" 2>/dev/null || true)"
scrub_installed="$(node -p "require('$BRIDGE_HOME/node_modules/@rynfar/meridian-plugin-pi-scrub/package.json').version" 2>/dev/null || true)"
if [ "$installed" != "$VERSION" ] || [ "$scrub_installed" != "$SCRUB_VERSION" ]; then
  # --ignore-scripts: skip the bundled Claude Code download; turns run the machine's own claude.
  npm install --prefix "$BRIDGE_HOME" --ignore-scripts --no-audit --no-fund \
    "@rynfar/meridian@$VERSION" "@rynfar/meridian-plugin-pi-scrub@$SCRUB_VERSION"
fi
set -a
# CLAUDE_CONFIG_DIR (the signed-in Claude Code account folder) and MERIDIAN_CLAUDE_PATH.
. "$BRIDGE_HOME/claude-login.env"
set +a
export MERIDIAN_REAL_CLAUDE_PATH="$MERIDIAN_CLAUDE_PATH"
export MERIDIAN_CLAUDE_PATH="$BRIDGE_HOME/claude_subscription_only.py"
export MERIDIAN_BILLING_BLOCK_FILE="$BRIDGE_HOME/billing-block.json"
export MERIDIAN_CONFIG_DIR="$BRIDGE_HOME/config"
mkdir -p "$MERIDIAN_CONFIG_DIR"
# Explicitly enabled by the user: strips Pi's identifying boilerplate before Claude receives it.
# This can affect third-party classification; it does not guarantee subscription eligibility.
node --input-type=module - "$BRIDGE_HOME" <<'JS'
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
const root = process.argv[2];
writeFileSync(join(root, 'config', 'plugins.json'), JSON.stringify({ plugins: [{
  path: join(root, 'node_modules', '@rynfar', 'meridian-plugin-pi-scrub', 'dist', 'index.js'),
  enabled: true,
}] }, null, 2) + '\n');
JS
export MERIDIAN_HOST=127.0.0.1
export MERIDIAN_PORT=3456
export MERIDIAN_DEFAULT_AGENT=pi
export MERIDIAN_MAX_CONCURRENT="${MERIDIAN_MAX_CONCURRENT:-3}"
# Never refresh or rewrite the Claude login: the claude program (here and in Claude chats) does that,
# and refresh tokens are single-use, so a second refresher could sign the machine out.
export MERIDIAN_CREDENTIALS_READONLY=1
# Do not let inherited API credentials silently move turns off the subscription.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
exec "$BRIDGE_HOME/node_modules/.bin/meridian"

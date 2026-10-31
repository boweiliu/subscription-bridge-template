// Points the Claude Code add-on (extensions/pi-claude-code) at the Claude login a pi account names.
//
// A pi account that runs on a Claude subscription carries, in its auth.json:
//   "claude-code": {"type": "api_key", "key": "claude-code-login",
//                   "env": {"PI_CLAUDE_CODE_CONFIG_DIR": "<a Claude Code config dir that is signed in>"}}
// The add-on reads that dir from the environment when it discovers models, before pi hands it the
// stored credential, so it is copied into the environment here, at load. An account without the entry
// leaves the environment alone and the add-on stays hidden unless Claude Code is signed in by default.
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export default function () {
  if (process.env.PI_CLAUDE_CODE_CONFIG_DIR) return;
  const agentDir = process.env.PI_CODING_AGENT_DIR || join(homedir(), ".pi", "agent");
  try {
    const auth = JSON.parse(readFileSync(join(agentDir, "auth.json"), "utf8"));
    const configDir = auth?.["claude-code"]?.env?.PI_CLAUDE_CODE_CONFIG_DIR;
    if (typeof configDir === "string" && configDir) process.env.PI_CLAUDE_CODE_CONFIG_DIR = configDir;
  } catch {
    // No auth.json, or not JSON: nothing names a Claude login.
  }
}

// Signs a pi account folder in to a ChatGPT (Codex) subscription with OpenAI's device-code flow.
//
//   node codex_device_login.mjs <pi-coding-agent-module-dir> <auth.json path>
//
// Prints one JSON line {"verification_uri", "user_code"} as soon as OpenAI hands out a code, waits
// for the user to enter it, then writes {"openai-codex": <credential>} into the auth.json and
// prints {"ok": true}. pi refreshes the token itself from then on, so this runs once per account.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [moduleDir, authPath] = process.argv.slice(2);
const oauthFile = join(moduleDir, "node_modules/@earendil-works/pi-ai/dist/auth/oauth/openai-codex.js");
const { openaiCodexOAuth } = await import(pathToFileURL(oauthFile).href);
const controller = new AbortController();
const credential = await openaiCodexOAuth.login({
  signal: controller.signal,
  prompt: async () => "device_code",
  notify: (event) => {
    if (event.type === "device_code") {
      console.log(JSON.stringify({ verification_uri: event.verificationUri, user_code: event.userCode }));
    }
  },
});
let existing = {};
try {
  existing = JSON.parse(readFileSync(authPath, "utf8"));
} catch {
  // A new account folder has no auth.json yet.
}
writeFileSync(authPath, JSON.stringify({ ...existing, "openai-codex": credential }, null, 2) + "\n", { mode: 0o600 });
console.log(JSON.stringify({ ok: true }));

// Lets a pi account run pi's built-in ChatGPT (openai-codex) models on a Codex CLI login that already
// exists on the machine, instead of a second sign-in made inside pi.
//
// A pi account that does this carries, in its auth.json:
//   "openai-codex": {"type": "api_key", "key": "codex-login",
//                    "env": {"PI_CODEX_HOME": "<a Codex CLI home holding a ChatGPT auth.json>"}}
// Every request reads the access token from <PI_CODEX_HOME>/auth.json, so whatever Codex itself last
// refreshed is used. Only when that token is about to expire does this refresh it, under a lock, and it
// writes the new tokens back into the same file in Codex's own shape: the file stays the one source of
// truth, so the Codex CLI and pi never hold diverging refresh tokens (a refresh token works once).
// Accounts without the entry keep pi's own ChatGPT sign-in (/login) unchanged.
import { mkdir, readFile, rename, rmdir, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
// pi exposes only its provider list (not each provider module) to extensions.
import { builtinProviders } from "@earendil-works/pi-ai/providers/all";

const HOME_ENV = "PI_CODEX_HOME";
// PI_CODEX_TOKEN_URL exists so the refresh can be exercised against a stand-in server.
const TOKEN_URL = process.env.PI_CODEX_TOKEN_URL || "https://auth.openai.com/oauth/token";
// The Codex CLI's own OAuth client: the refresh token belongs to it.
const CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann";
// Refresh when less than this is left, so a turn never starts on a token that expires mid-request.
const REFRESH_MARGIN_MS = 5 * 60 * 1000;
const LOCK_STALE_MS = 60 * 1000;

interface CodexAuthFile {
  tokens?: { access_token?: string; refresh_token?: string; id_token?: string; account_id?: string };
  last_refresh?: string;
  [key: string]: unknown;
}

function expiresAt(token: string): number {
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString("utf8"));
    return typeof payload.exp === "number" ? payload.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

async function readAuth(path: string): Promise<CodexAuthFile> {
  return JSON.parse(await readFile(path, "utf8"));
}

async function withLock<T>(path: string, work: () => Promise<T>): Promise<T> {
  const lock = `${path}.pi-refresh.lock`;
  for (let attempt = 0; ; attempt++) {
    try {
      await mkdir(lock);
      break;
    } catch {
      const held = await stat(lock).catch(() => undefined);
      if (held && Date.now() - held.mtimeMs > LOCK_STALE_MS) await rmdir(lock).catch(() => {});
      if (attempt > 300) throw new Error(`Codex login is locked by another refresh (${lock})`);
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  try {
    return await work();
  } finally {
    await rmdir(lock).catch(() => {});
  }
}

async function refreshInPlace(path: string, signal: AbortSignal): Promise<string> {
  return withLock(path, async () => {
    // Codex (or another pi) may have refreshed while this waited for the lock.
    const current = await readAuth(path);
    const access = current.tokens?.access_token ?? "";
    if (expiresAt(access) - Date.now() > REFRESH_MARGIN_MS) return access;
    const refreshToken = current.tokens?.refresh_token;
    if (!refreshToken) throw new Error(`No ChatGPT refresh token in ${path}; sign in to Codex again`);
    const response = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: CLIENT_ID, grant_type: "refresh_token", refresh_token: refreshToken, scope: "openid profile email" }),
      signal,
    });
    if (!response.ok) {
      throw new Error(`ChatGPT token refresh failed (${response.status}): ${(await response.text().catch(() => "")).slice(0, 300)}`);
    }
    const fresh = (await response.json()) as { access_token?: string; refresh_token?: string; id_token?: string };
    if (!fresh.access_token) throw new Error("ChatGPT token refresh answered without an access token");
    const updated: CodexAuthFile = {
      ...current,
      tokens: {
        ...current.tokens,
        access_token: fresh.access_token,
        ...(fresh.refresh_token ? { refresh_token: fresh.refresh_token } : {}),
        ...(fresh.id_token ? { id_token: fresh.id_token } : {}),
      },
      last_refresh: new Date().toISOString(),
    };
    const scratch = `${path}.pi-refresh.tmp`;
    await writeFile(scratch, JSON.stringify(updated, null, 2), { mode: 0o600 });
    await rename(scratch, path);
    return fresh.access_token;
  });
}

async function accessToken(home: string, signal: AbortSignal): Promise<string> {
  const path = join(home, "auth.json");
  const access = (await readAuth(path)).tokens?.access_token ?? "";
  if (access && expiresAt(access) - Date.now() > REFRESH_MARGIN_MS) return access;
  return refreshInPlace(path, signal);
}

export default function codexSubscriptionLogin(pi: { registerProvider(provider: unknown): void }): void {
  const builtin = builtinProviders().find((provider: { id: string }) => provider.id === "openai-codex");
  if (!builtin) return;
  pi.registerProvider({
    ...builtin,
    auth: {
      ...builtin.auth,
      apiKey: {
        name: "Codex CLI login",
        async check({ credential }: { credential?: { env?: Record<string, string> } }) {
          const home = credential?.env?.[HOME_ENV];
          if (!home) return undefined;
          const exists = await stat(join(home, "auth.json")).catch(() => undefined);
          return exists ? { type: "oauth" as const, source: "Codex CLI login" } : undefined;
        },
        async resolve({ credential, signal }: { credential?: { env?: Record<string, string> }; signal: AbortSignal }) {
          const home = credential?.env?.[HOME_ENV];
          if (!home) return undefined;
          return { auth: { apiKey: await accessToken(home, signal) }, source: "Codex CLI login" };
        },
      },
    },
  });
}

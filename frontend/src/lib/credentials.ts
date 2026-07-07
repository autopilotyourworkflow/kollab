/** Bring-your-own-key storage.
 *
 * When the operator's shared credit runs low (or a reviewer just wants to run on
 * their own account), they paste their own Apify / Claude key in Settings. Those
 * keys live ONLY in this browser's localStorage and ride each API call as headers
 * (X-Apify-Token / X-Anthropic-Key). The backend uses them for that one request and
 * never stores, logs, or returns them — so no server ever holds someone else's key. */

export interface ByoKeys {
  apify: string
  anthropic: string
}

const APIFY_KEY = "kollab-apify-key"
const ANTHROPIC_KEY = "kollab-anthropic-key"

export function loadKeys(): ByoKeys {
  try {
    return {
      apify: localStorage.getItem(APIFY_KEY) ?? "",
      anthropic: localStorage.getItem(ANTHROPIC_KEY) ?? "",
    }
  } catch {
    return { apify: "", anthropic: "" }
  }
}

/** Persist non-empty keys; a blank field removes the stored key (an explicit clear). */
export function saveKeys(k: ByoKeys): void {
  try {
    const apify = k.apify.trim()
    const anthropic = k.anthropic.trim()
    if (apify) localStorage.setItem(APIFY_KEY, apify)
    else localStorage.removeItem(APIFY_KEY)
    if (anthropic) localStorage.setItem(ANTHROPIC_KEY, anthropic)
    else localStorage.removeItem(ANTHROPIC_KEY)
  } catch {
    /* storage unavailable — the in-memory value the caller holds still applies */
  }
}

export function clearKeys(): void {
  try {
    localStorage.removeItem(APIFY_KEY)
    localStorage.removeItem(ANTHROPIC_KEY)
  } catch {
    /* nothing to clear */
  }
}

/** Headers that carry whichever keys the user has stored (omitted when blank, so a
 *  request with no stored key transparently falls back to the operator's shared key). */
export function authHeaders(): Record<string, string> {
  const { apify, anthropic } = loadKeys()
  const h: Record<string, string> = {}
  if (apify) h["X-Apify-Token"] = apify
  if (anthropic) h["X-Anthropic-Key"] = anthropic
  // The account session token (read inline to avoid an import cycle with lib/auth ->
  // lib/credit -> lib/credentials). Authenticates every existing fetch site for free.
  try {
    const t = localStorage.getItem("kollab-auth")
    if (t) h["Authorization"] = `Bearer ${t}`
  } catch {
    /* storage unavailable */
  }
  return h
}

/** Tracked background runs — the client-side registry behind the Run dock.
 *
 * The actual run lives on the backend (persisted in Neon) and keeps going no matter
 * what the browser does. This just remembers which run ids belong to this user and
 * which shortlist each should merge into, so after a refresh — or reopening the tab —
 * the dock can resume polling them. localStorage, same pattern as the workspace. */

export type RunStatus = "running" | "done" | "error" | "cancelled"

export interface TrackedRun {
  id: string
  shortlistId: string
  brand: string
  preset: string
  startedAt: number
  status: RunStatus
  added?: number // creators merged in when done
  error?: string
}

const KEY = "kollab-runs"
export const RUNS_CHANGED = "kollab:runs-changed"
export const WORKSPACE_UPDATED = "kollab:workspace-updated"

function read(): TrackedRun[] {
  try {
    const raw = localStorage.getItem(KEY)
    const list = raw ? (JSON.parse(raw) as TrackedRun[]) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

function write(runs: TrackedRun[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(runs))
  } catch {
    /* storage unavailable */
  }
  try {
    window.dispatchEvent(new CustomEvent(RUNS_CHANGED))
  } catch {
    /* no window (SSR) — irrelevant here */
  }
}

export function listRuns(): TrackedRun[] {
  // newest first
  return read().sort((a, b) => b.startedAt - a.startedAt)
}

export function addRun(run: TrackedRun): void {
  write([...read().filter((r) => r.id !== run.id), run])
}

export function updateRun(id: string, patch: Partial<TrackedRun>): void {
  write(read().map((r) => (r.id === id ? { ...r, ...patch } : r)))
}

export function removeRun(id: string): void {
  write(read().filter((r) => r.id !== id))
}

/** Tell any open shortlist view that creators were merged into it, so it re-reads. */
export function announceWorkspaceUpdate(shortlistId: string): void {
  try {
    window.dispatchEvent(new CustomEvent(WORKSPACE_UPDATED, { detail: { shortlistId } }))
  } catch {
    /* ignore */
  }
}

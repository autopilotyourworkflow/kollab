/** Fair-rate estimate — client-side rescale of the backend's RateBasis.
 *
 * The backend ships each KOL a RateBasis (measured organic reach + authenticity) plus a
 * band computed at the default CPM. The user's CPM assumption lives in this browser; when
 * they change it, we recompute the band with the SAME linear formula as the backend
 * (app/pricing/rate.py) — so the number on screen is always their assumption applied to
 * this creator's measured reach, never a market rate. */

import type { Kol, RateBand, RateBasis } from "./types"

/** Mirrors backend DEFAULT_CPM_THB (config.py) — a neutral placeholder, not a benchmark. */
export const CPM_DEFAULT = 150
const CPM_KEY = "kollab-cpm-thb"
const SPREAD = 0.2 // mirrors RATE_BAND_SPREAD in app/pricing/rate.py

export function loadCpm(): number {
  try {
    const n = Number(localStorage.getItem(CPM_KEY))
    return Number.isFinite(n) && n > 0 ? n : CPM_DEFAULT
  } catch {
    return CPM_DEFAULT
  }
}

export function saveCpm(cpm: number): void {
  try {
    localStorage.setItem(CPM_KEY, String(cpm))
  } catch {
    /* storage unavailable */
  }
}

// ── Shared CPM store (useSyncExternalStore) ──────────────────────────────────
// Same-tab localStorage writes emit no 'storage' event, so a plain per-mount useState
// would let two open Economics panels drift. This tiny store keeps them all in sync.
let _cpm = loadCpm()
const _subs = new Set<() => void>()

export function getCpm(): number {
  return _cpm
}

export function subscribeCpm(cb: () => void): () => void {
  _subs.add(cb)
  return () => {
    _subs.delete(cb)
  }
}

export function setCpmShared(cpm: number): void {
  const c = Math.max(1, Math.round(cpm))
  if (c === _cpm) return
  _cpm = c
  saveCpm(c)
  _subs.forEach((cb) => cb())
}

/** Rescale the band for a new CPM — linear, identical to the backend fair_rate_band(). */
export function computeBand(basis: RateBasis, cpm: number): RateBand {
  const disc = Math.max(0, Math.min(1, basis.authenticity / 100))
  const point = ((basis.medianOrganicViews * disc) / 1000) * cpm
  return { low: Math.round(point * (1 - SPREAD)), high: Math.round(point * (1 + SPREAD)) }
}

/** Derive a RateBasis from a KOL's own displayed fields when the backend didn't ship one
 *  (e.g. creators sourced by an older run, before thin samples were priced). It reuses the
 *  EXACT inputs the backend would: `medianViews` IS median_organic_views, and the
 *  authenticity factor score IS the vet authenticity — so the derived band matches the
 *  backend's to the baht. `videosSampled` is unknown here (0), so the UI labels it "derived
 *  from median reach". Returns null when there's no reach or authenticity to price. */
export function deriveBasis(kol: Kol): RateBasis | null {
  const median = kol.medianViews
  if (!median || median <= 0) return null
  const auth = kol.factors?.find((f) => f.key === "authenticity")?.score
  if (typeof auth !== "number") return null
  return {
    medianOrganicViews: median,
    cpmThb: CPM_DEFAULT,
    authenticity: auth,
    videosSampled: 0, // unknown for a derived basis — the UI shows a "derived" caveat, not a count
    band: { low: 0, high: 0 }, // recomputed live by computeBand() with the current CPM
    method: "Derived from the creator's median reach × your CPM × authenticity — not a market rate card.",
  }
}

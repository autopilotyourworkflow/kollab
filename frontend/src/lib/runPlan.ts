import plansData from "../data/run-plans.json"

/** Run-depth plans, generated from backend/app/sources/plans.py (a backend test
    enforces byte-parity, so these numbers cannot drift from what the API
    actually charges against). */
export interface RunPlanPreset {
  key: string
  label: string
  maxCreators: number
  videosPerCreator: number
  commentsPerCreator: number
  resultsPerQuery: number
  estUsd: number
  capUsd: number
  note: string
}

interface PlansFile {
  prices: { per1kResults: number; per1kComments: number }
  searchQueries: number
  capHeadroom: number
  defaultPreset: string
  presets: RunPlanPreset[]
}

export const plans = plansData as PlansFile

/** The account manager's chosen depth for the next live run. */
export interface RunPlanChoice {
  key: string
  label: string
  maxCreators: number
  commentsPerCreator: number
  estUsd: number
  capUsd: number
}

const STORAGE_KEY = "kollab-run-plan"

export function fromPreset(p: RunPlanPreset): RunPlanChoice {
  return {
    key: p.key,
    label: p.label,
    maxCreators: p.maxCreators,
    commentsPerCreator: p.commentsPerCreator,
    estUsd: p.estUsd,
    capUsd: p.capUsd,
  }
}

export function defaultPlan(): RunPlanChoice {
  const preset = plans.presets.find((p) => p.key === plans.defaultPreset) ?? plans.presets[0]
  return fromPreset(preset)
}

/** Estimate for a custom depth — same arithmetic as the backend (standard
    preset's search width; videos come from the search, only comments add cost). */
export function estimateCustom(creators: number, comments: number): number {
  const base = plans.presets.find((p) => p.key === "standard") ?? plans.presets[0]
  const results = plans.searchQueries * base.resultsPerQuery
  const usd = (results / 1000) * plans.prices.per1kResults + ((creators * comments) / 1000) * plans.prices.per1kComments
  return Math.round(usd * 100) / 100
}

/** Default authorized ceiling: estimate + headroom, rounded up to $0.25. */
export function defaultCap(estUsd: number): number {
  return Math.ceil(estUsd * plans.capHeadroom * 4) / 4
}

export function loadRunPlan(): RunPlanChoice {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const p = JSON.parse(raw) as RunPlanChoice
      if (typeof p?.estUsd === "number" && typeof p?.capUsd === "number" && p.label) return p
    }
  } catch {
    /* storage unavailable — default below */
  }
  return defaultPlan()
}

export function saveRunPlan(p: RunPlanChoice): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p))
  } catch {
    /* storage unavailable; the in-page choice still applied */
  }
}

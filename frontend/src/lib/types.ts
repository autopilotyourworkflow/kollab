// Domain model for a KOL shortlist. Mirrors what the Python pipeline will emit,
// so the frontend contract is real, not throwaway.

export type Provenance = "measured" | "inferred" | "estimated"
export type RiskLevel = "high" | "medium" | "clear"
export type Tier = "nano" | "micro" | "mid" | "macro" | "mega"
export type HitlStatus = "pending" | "approved" | "rejected"
export type GateStatus = "clear" | "flag"

export interface FraudSignal {
  /** Short name, e.g. "Comment pod". */
  label: string
  /** Grounded detail, e.g. "41 accounts comment across 6 unrelated creators in 14 days". */
  detail: string
  level: RiskLevel
  /** What baseline it was measured against, e.g. "18 beauty-micro peers (n=18)". */
  measuredAgainst: string
}

export interface MatchFactor {
  key: "topic" | "authenticity" | "recency" | "audience"
  label: string
  score: number // 0-100
  /** Non-ranking factors (audience) carry weight 0 and render as advisory only. */
  weight: number
  provenance: Provenance
  /** One grounded line citing a real data point. */
  rationale: string
}

/** One line of the full vetting ledger (internal report) — every detector that ran,
    including the ones honestly WITHHELD (min-cohort rule). */
export interface VetCheck {
  name: string
  label: string
  status: "fired" | "clear" | "withheld"
  level: RiskLevel
  detail: string
  measuredAgainst: string
}

export interface RateBand {
  low: number
  high: number
}

/** The transparent arithmetic behind a fair-rate ESTIMATE — the creator's own measured
    organic reach × an editable CPM assumption × authenticity. Never a market rate card. */
export interface RateBasis {
  medianOrganicViews: number
  cpmThb: number
  authenticity: number
  videosSampled: number
  band: RateBand
  method: string
}

export interface Kol {
  id: string
  handle: string
  name: string
  avatar: { initials: string; hue: number }
  category: string
  categoryTh: string
  tier: Tier
  region: string
  // Core metrics (all measured from public data in the demo)
  followers: number
  medianViews: number
  engagementRate: number // %
  lastPostedDaysAgo: number
  // Outputs
  fitScore: number
  risk: { level: RiskLevel; signals: FraudSignal[] }
  brandSafety: { status: GateStatus; note?: string }
  conflict: { status: GateStatus; note?: string }
  factors: MatchFactor[]
  whyEn: string
  whyTh: string
  /** Estimated fair-rate band at the default CPM; null when the sample is too thin. */
  estRateThb: RateBand | null
  /** The inputs behind estRateThb, so the UI can rescale the band as the CPM changes. */
  rateBasis?: RateBasis | null
  /** Full vetting ledger for the internal report (fired / clear / withheld). */
  checks?: VetCheck[]
  /** Label for a logged-delivery fit adjustment, so the fit reconciles with the factors. */
  deliveryNote?: string | null
  hitl: HitlStatus
}

/** Two shortlisted creators sharing a meaningful commenter set — booking both
    double-serves that slice. Commenter overlap is measured; "audience" is an inferred proxy. */
export interface OverlapPair {
  aId: string
  aHandle: string
  bId: string
  bHandle: string
  shared: number
  jaccard: number
  aShare: number
  bShare: number
  note: string
}

/** Re-audit of a creator's delivered (paid) post vs the pre-booking vet. */
export interface DeliveryAudit {
  handle: string
  preAuthenticity: number | null
  postAuthenticity: number
  verdict: "consistent" | "degraded" | "cleared" | "inconclusive"
  newSignals: FraudSignal[]
  checks: VetCheck[]
  note: string
}

/** One logged campaign outcome (projected vs actual reach). */
export interface DeliveryRow {
  id: string
  brand: string
  handle: string
  projectedViews: number
  actualViews: number
  ratio: number
  note?: string | null
  createdAt?: string | null
}

/** Aggregate reliability for a creator from their logged deliveries (learning state at n=0). */
export interface DeliveryReliability {
  handle: string
  n: number
  meanRatio: number | null
  adjustment: number
  note: string
}

/** A grounded, citation-validated first-contact draft. */
export interface OutreachDraft {
  en: string
  th: string
  grounded: boolean
  source: "llm" | "template"
  note: string
}

export interface ClientBrief {
  brand: string
  brandTh: string
  category: string
  audience: string
  pillars: string[]
  region: string
  website: string
  /** Content-topic phrases used to search TikTok for creators (e.g. "thai skincare"),
      distinct from the display pillars (brand values). Populated by live Brand-DNA
      extraction; empty otherwise (the backend then falls back to category/pillars). */
  searchTerms?: string[]
}

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
  /** Only set when grounded in ≥2 cited Thai rate sources; otherwise null. */
  estRateThb: { low: number; high: number } | null
  hitl: HitlStatus
}

export interface ClientBrief {
  brand: string
  brandTh: string
  category: string
  audience: string
  pillars: string[]
  region: string
  website: string
}

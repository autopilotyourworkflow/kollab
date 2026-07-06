/** Delivery ledger (client) — backend Neon ledger first, localStorage mirror otherwise.
 *
 * Outcome data doesn't exist until the user logs it, so with nothing logged this returns
 * an explicit learning state (n=0, neutral adjustment) — never a fabricated number. The
 * client-side reliability math mirrors app/matching/delivery.py exactly (clamped ±6). */

import type { DeliveryReliability, DeliveryRow } from "./types"
import { getDeliveries, logDelivery } from "./api"
import { apiBase } from "./credit"

const KEY = "kollab-ledger"
const NUDGE_K = 12 // mirrors DELIVERY_NUDGE_K
const CLAMP = 6 // mirrors DELIVERY_NUDGE_CLAMP

const norm = (h: string) => h.trim().replace(/^@/, "").toLowerCase()

/** Same clamped, learning-state formula as the backend delivery_adjustment(). */
export function deliveryAdjustment(ratios: number[]): { adjustment: number; note: string } {
  if (!ratios.length)
    return {
      adjustment: 0,
      note: "No delivery outcomes logged yet — fit unchanged. Log a delivery to start the feedback loop.",
    }
  const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length
  const adj = Math.max(-CLAMP, Math.min(CLAMP, Math.round((mean - 1) * NUDGE_K)))
  const n = ratios.length
  return {
    adjustment: adj,
    note: `Estimated from your ${n} logged deliver${n === 1 ? "y" : "ies"}: delivered ${mean.toFixed(
      2,
    )}× projection on average → fit ${adj >= 0 ? "+" : ""}${adj}.`,
  }
}

function readLocal(): DeliveryRow[] {
  try {
    const raw = localStorage.getItem(KEY)
    const list = raw ? (JSON.parse(raw) as DeliveryRow[]) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

function writeLocal(rows: DeliveryRow[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(rows))
  } catch {
    /* storage unavailable */
  }
}

function reliabilityFrom(handle: string, rows: DeliveryRow[]): DeliveryReliability {
  const ratios = rows.map((r) => r.ratio)
  const { adjustment, note } = deliveryAdjustment(ratios)
  const mean = ratios.length ? ratios.reduce((a, b) => a + b, 0) / ratios.length : null
  return {
    handle: norm(handle),
    n: ratios.length,
    meanRatio: mean !== null ? Math.round(mean * 1000) / 1000 : null,
    adjustment,
    note,
  }
}

export interface LedgerState {
  deliveries: DeliveryRow[]
  reliability: DeliveryReliability
}

/** A creator's deliveries + reliability — backend ledger if reachable, else local mirror. */
export async function loadDeliveries(handle: string): Promise<LedgerState> {
  if (apiBase()) {
    const res = await getDeliveries(handle)
    if (res) return { deliveries: res.deliveries, reliability: res.reliability }
  }
  const rows = readLocal().filter((r) => norm(r.handle) === norm(handle))
  return { deliveries: rows, reliability: reliabilityFrom(handle, rows) }
}

/** Log a delivery outcome and return the updated state. */
export async function addDelivery(input: {
  brand: string
  handle: string
  projectedViews: number
  actualViews: number
  note?: string
}): Promise<LedgerState> {
  if (apiBase()) {
    const res = await logDelivery(input)
    if (res) return loadDeliveries(input.handle)
  }
  const proj = Math.max(1, Math.round(input.projectedViews))
  const act = Math.max(0, Math.round(input.actualViews))
  const row: DeliveryRow = {
    id: `d-${Date.now()}-${Math.floor(Math.random() * 1e6)}`,
    brand: input.brand,
    handle: norm(input.handle),
    projectedViews: proj,
    actualViews: act,
    ratio: Math.round((act / proj) * 1000) / 1000,
    note: input.note ?? null,
    createdAt: new Date().toISOString(),
  }
  writeLocal([row, ...readLocal()])
  return loadDeliveries(input.handle)
}

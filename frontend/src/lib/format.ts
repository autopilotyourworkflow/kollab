/** Compact number: 38200 → "38.2K", 486000 → "486K", 1_240_000 → "1.2M". */
export function compact(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + "M"
  if (n >= 1_000) return (n / 1_000).toFixed(n >= 100_000 ? 0 : 1) + "K"
  return String(n)
}

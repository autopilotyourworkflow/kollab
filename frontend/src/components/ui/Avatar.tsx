/** Initials avatar on a soft, hue-tinted disc. */
export function Avatar({
  initials,
  hue,
  size = 36,
}: {
  initials: string
  hue: number
  size?: number
}) {
  return (
    <div
      className="grid shrink-0 place-items-center rounded-full font-semibold"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        background: `hsl(${hue} 62% 93%)`,
        color: `hsl(${hue} 48% 34%)`,
      }}
      aria-hidden
    >
      {initials}
    </div>
  )
}

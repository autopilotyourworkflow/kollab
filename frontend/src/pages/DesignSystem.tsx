import { Search, Download, Plus, ArrowRight, ShieldCheck, Users } from "lucide-react"
import { Link } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { TintPill, StatCard, StatChip, Kicker } from "../components/ui/brand"
import ccLogo from "../assets/convertcake-logo.png"
import { RiskBadge } from "../components/ui/RiskBadge"
import { ProvenanceChip } from "../components/ui/ProvenanceChip"
import { ScoreBar } from "../components/ui/ScoreBar"
import { TierChip } from "../components/ui/TierChip"

/* Swatches — measured = straight from convertcake.com; derived = our AA-safe
   extension of their ramp. See DESIGN.md "Fidelity ledger". */
const swatches: { name: string; token: string; hex: string; src: "measured" | "derived"; ink?: boolean }[] = [
  { name: "brand", token: "bg-brand", hex: "#0536D2", src: "measured" },
  { name: "brand-hover", token: "bg-brand-hover", hex: "#0430BC", src: "derived" },
  { name: "brand-300", token: "bg-brand-300", hex: "#597EF3", src: "derived" },
  { name: "brand-100", token: "bg-brand-100", hex: "#C8D4FB", src: "measured", ink: true },
  { name: "brand-50", token: "bg-brand-50", hex: "#E6ECFD", src: "measured", ink: true },
  { name: "ink", token: "bg-ink", hex: "#2D303C", src: "measured" },
  { name: "ink-900 · navy", token: "bg-ink-900", hex: "#000E3F", src: "measured" },
  { name: "ink-500", token: "bg-ink-500", hex: "#5B6580", src: "derived" },
  { name: "ink-400", token: "bg-ink-400", hex: "#75809D", src: "measured" },
  { name: "verified", token: "bg-verified", hex: "#1D8102", src: "derived" },
  { name: "risk-high", token: "bg-risk-high", hex: "#D92D20", src: "derived" },
  { name: "risk-med", token: "bg-risk-med", hex: "#B54708", src: "derived" },
]

const typeScale: { label: string; cls: string; sample: string }[] = [
  { label: "page-title / 28", cls: "text-[28px] font-bold tracking-[-0.02em]", sample: "Beauty client shortlist" },
  { label: "view-title / 24", cls: "text-2xl font-semibold", sample: "42 KOLs screened · 12 recommended" },
  { label: "section / 20", cls: "text-xl font-semibold", sample: "Why this match" },
  { label: "subhead / 16", cls: "text-base font-medium", sample: "Engagement authenticity" },
  { label: "body / 14", cls: "text-sm", sample: "Ranked on brand fit, engagement authenticity, and recency — every score cites a real data point." },
  { label: "label / 13", cls: "text-[13px] font-medium text-ink-700", sample: "Followers · Median views · ER" },
  { label: "micro / 12", cls: "text-xs text-ink-500", sample: "Measured from 30 most-recent videos" },
]

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border py-10">
      <div className="mb-5 flex items-baseline gap-3">
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {note && <span className="text-xs text-ink-500">{note}</span>}
      </div>
      {children}
    </section>
  )
}

export function DesignSystem() {
  return (
    <div id="top" className="min-h-svh bg-white">
      <div className="mx-auto max-w-5xl px-8 py-14">
        <header className="mb-4">
          <div className="mb-3 flex items-center gap-2.5">
            <Link
              to="/"
              title="Back to the Kollab landing page"
              className="flex items-center gap-2.5 rounded-md transition-opacity duration-300 hover:opacity-80"
            >
              <img src={ccLogo} alt="Convert Cake" className="h-6 w-auto" />
              <span className="text-[15px] font-semibold text-ink">Kollab</span>
            </Link>
            <span className="text-ink-400">·</span>
            <span className="text-[15px] text-ink-500">Design system</span>
          </div>
          <h1 className="text-[32px] font-bold tracking-[-0.02em] text-ink">
            The <span className="text-brand">measured</span> Convert Cake system
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-500">
            Extracted from convertcake.com computed styles and their theme's own CSS variables — cobalt{" "}
            <code className="rounded bg-panel px-1 py-0.5 text-[12px] text-ink-700">#0536D2</code>, ink{" "}
            <code className="rounded bg-panel px-1 py-0.5 text-[12px] text-ink-700">#2D303C</code>, navy{" "}
            <code className="rounded bg-panel px-1 py-0.5 text-[12px] text-ink-700">#000E3F</code>, Manrope + Noto
            Sans Thai. Green means verified-authentic, red is reserved strictly for fraud risk. Nothing is
            signalled by colour alone. Every new page or section builds from these tokens.
          </p>
        </header>

        <Section title="Colour" note="measured = straight from their site · derived = our AA-safe extension">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {swatches.map((s) => (
              <div key={s.name} className="overflow-hidden rounded-lg border border-border bg-white shadow-xs">
                <div className={`${s.token} h-16`} />
                <div className="px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate text-[13px] font-medium text-ink">{s.name}</div>
                    <span
                      className={`rounded-full px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide ${
                        s.src === "measured" ? "bg-brand-50 text-brand" : "bg-panel text-ink-500"
                      }`}
                    >
                      {s.src}
                    </span>
                  </div>
                  <div className="tnum text-[11px] text-ink-500">{s.hex}</div>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-ink-500">
            Their body text <code className="tnum">#75809D</code> measures ~3.7:1 on white — kept as{" "}
            <code>ink-400</code> for large text only; body runs the AA-safe <code>ink-500</code>.
          </p>
        </Section>

        <Section title="Signature elements" note="their marketing grammar, componentized">
          <div className="space-y-8">
            <div className="flex flex-wrap items-center gap-4">
              <TintPill icon={<Users size={14} />}>Built for Convert Cake's influencer team</TintPill>
              <TintPill icon={<ShieldCheck size={14} />}>Fraud-vetted</TintPill>
              <Kicker>How it works</Kicker>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard value="42" label="KOLs screened per brief" />
              <StatCard value="8" label="structural fraud signals" />
              <StatCard value="15" unit="min" label="to a defensible shortlist" />
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <StatChip value="92" label="fit score" />
              <StatChip value="3" label="flagged for review" />
              <StatChip value="$1.02" label="per live run" />
            </div>
            <div>
              <a
                href="#top"
                className="group inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-[15px] font-semibold text-white shadow-sm transition-colors duration-300 hover:bg-brand-hover"
              >
                Grow your shortlist
                <ArrowRight size={17} className="transition-transform duration-300 group-hover:translate-x-0.5" />
              </a>
              <span className="ml-4 align-middle text-xs text-ink-500">
                CTA anatomy: cobalt fill · 8px radius · 600 · arrow nudges on hover
              </span>
            </div>
          </div>
        </Section>

        <Section title="Typography" note="Manrope · headline keyword in cobalt · tabular numerals">
          <div className="space-y-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-6">
              <div className="w-40 shrink-0 text-[11px] text-ink-400">display / 48 · 700</div>
              <div className="text-[clamp(2rem,4vw,3rem)] font-bold leading-[1.15] tracking-[-0.02em] text-ink">
                The <span className="text-brand">fraud-vetted</span> shortlist.
              </div>
            </div>
            {typeScale.map((t) => (
              <div key={t.label} className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-6">
                <div className="w-40 shrink-0 text-[11px] text-ink-400">{t.label}</div>
                <div className={`${t.cls} text-ink`}>{t.sample}</div>
              </div>
            ))}
            <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-6">
              <div className="w-40 shrink-0 text-[11px] text-ink-400">thai / rationale</div>
              <div className="font-thai text-sm text-ink">
                เหมาะกับแบรนด์บิวตี้สายผิว รีวิวสกินแคร์จริงจัง คนดูเป็นผู้หญิงไทยวัย 22–34
              </div>
            </div>
          </div>
        </Section>

        <Section title="Buttons" note="default · hover · disabled — 8px radius per their CTA">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" leadingIcon={<Plus size={16} />}>New shortlist</Button>
            <Button variant="secondary" leadingIcon={<Download size={16} />}>Export</Button>
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Reject KOL</Button>
            <Button variant="primary" disabled>Disabled</Button>
            <Button variant="secondary" size="sm" trailingIcon={<ArrowRight size={15} />}>
              Open
            </Button>
            <div className="relative">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
              <input
                className="h-10 w-64 rounded-md border border-border-strong bg-white pl-9 pr-3 text-sm text-ink shadow-xs placeholder:text-ink-500 focus:border-brand-300"
                placeholder="Search KOLs…"
              />
            </div>
          </div>
        </Section>

        <Section title="Trust badges" note="the hero language — icon + label, never colour alone">
          <div className="flex flex-wrap items-center gap-3">
            <RiskBadge level="clear" />
            <RiskBadge level="high" signal="Comment pod · 41 shared accounts" />
            <RiskBadge level="medium" signal="View spike · 6.2× baseline" />
            <RiskBadge level="high" signal="Bought followers · ER 0.4%" />
          </div>
        </Section>

        <Section title="Provenance chips" note="measured / inferred / estimated — on every derived value">
          <div className="flex flex-wrap items-center gap-3">
            <ProvenanceChip kind="measured" />
            <ProvenanceChip kind="inferred" />
            <ProvenanceChip kind="estimated" />
          </div>
        </Section>

        <Section title="Fit score + tier">
          <div className="max-w-md space-y-4">
            <div className="flex items-center gap-4">
              <ScoreBar value={92} className="flex-1" />
              <TierChip tier="micro" />
            </div>
            <div className="flex items-center gap-4">
              <ScoreBar value={74} className="flex-1" />
              <TierChip tier="mid" />
            </div>
            <div className="flex items-center gap-4">
              <ScoreBar value={38} className="flex-1" />
              <TierChip tier="nano" />
            </div>
          </div>
        </Section>

        <Section title="Elevation & radius" note="soft cool shadows — rgba(73,104,126) family, never harsh black">
          <div className="flex flex-wrap items-end gap-6">
            {(["shadow-xs", "shadow-sm", "shadow-md", "shadow-lg"] as const).map((s) => (
              <div key={s} className={`grid h-24 w-32 place-items-center rounded-xl bg-white text-[12px] text-ink-500 ${s}`}>
                {s}
              </div>
            ))}
            <div className="flex items-end gap-3">
              {[
                ["rounded-md", "8"],
                ["rounded-lg", "12"],
                ["rounded-xl", "16"],
                ["rounded-2xl", "24"],
                ["rounded-full", "pill"],
              ].map(([cls, px]) => (
                <div key={cls} className={`grid h-16 w-16 place-items-center border-[1.5px] border-brand bg-brand-50 text-[11px] font-medium text-brand ${cls}`}>
                  {px}
                </div>
              ))}
            </div>
          </div>
        </Section>

        <Section title="Motion" note="0.3s ease interactions · 0.5s ease-out-cubic reveals (measured) · reduced-motion always">
          <div className="flex flex-wrap gap-3 text-[13px]">
            <span className="rounded-lg border border-border bg-white px-3 py-2 text-ink-700 shadow-xs transition-shadow duration-300 hover:shadow-md">
              hover: shadow 300ms ease
            </span>
            <span className="group inline-flex items-center gap-2 rounded-lg border border-border bg-white px-3 py-2 text-ink-700 shadow-xs">
              arrow nudge
              <ArrowRight size={15} className="transition-transform duration-300 group-hover:translate-x-1" />
            </span>
            <span className="rounded-lg bg-brand px-3 py-2 font-medium text-white transition-colors duration-300 hover:bg-brand-hover">
              color 300ms ease
            </span>
          </div>
        </Section>
      </div>
    </div>
  )
}

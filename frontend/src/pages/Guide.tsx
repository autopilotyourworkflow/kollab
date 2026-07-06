import { useState } from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, ClipboardCopy, Check, LifeBuoy } from "lucide-react"
import { Button } from "../components/ui/Button"

/** In-app SOP / operating guide. One typed source of truth renders to the screen AND to a
    one-click Markdown copy, so the guide and the doc can never drift. */

interface GuideSection {
  id: string
  title: string
  steps: string[]
}

const INTRO =
  "Kollab turns a client's brand into a fraud-screened, ROI-justified shortlist of Thai TikTok creators you can defend to a client. This guide walks the whole workflow — no coding required."

const GUIDE: GuideSection[] = [
  {
    id: "what",
    title: "1. What Kollab is",
    steps: [
      "Not a scraper and not a database — the judgment layer that sits on top of KOL data and decides who is a real, on-brand, fraud-free fit.",
      "The one hard differentiator is authenticity vetting: catching bought engagement (comment pods, bought followers, boosted posts) before a client's budget bleeds into it.",
      "Every number on screen is tagged measured, inferred, or estimated — and Kollab flags for a human rather than auto-deciding.",
    ],
  },
  {
    id: "new",
    title: "2. Start a new shortlist",
    steps: [
      "Click New shortlist and paste the client's website. Kollab reads the brand into a structured brief (audience, pillars, tone, no-go list).",
      "Review and edit the Brand DNA — every field is yours to correct before sourcing.",
      "Pick a run depth (Scan / Standard / Deep). Each shows a live cost estimate and an editable hard cap the run stops before crossing — a too-tight cap yields a labeled partial pull, never a surprise bill.",
      "Click Find matching KOLs. Live sourcing takes a few minutes, so it runs in the background — follow it in the run dock (bottom-right); it survives a refresh or closing the tab.",
    ],
  },
  {
    id: "read",
    title: "3. Read the shortlist",
    steps: [
      "Each row shows the creator, tier, followers, median views, engagement rate, an authenticity badge, and a fit score.",
      "Filter by Recommended (clear risk + fit ≥ 70) or Flagged; sort by fit, followers, engagement, or risk-first.",
      "Search matches handle, name, category, tier, and fraud-signal labels (e.g. type 'comment pod').",
      "The red banner surfaces creators that look strong but failed authenticity vetting — review these before they reach the client.",
    ],
  },
  {
    id: "evidence",
    title: "4. Open a creator — the three tabs",
    steps: [
      "Click any row to expand its evidence panel, which has three tabs.",
      "Evidence: the fit-score breakdown, the fraud signals with the exact baseline each was measured against, a separate brand-safety review, and your approve/reject decision.",
      "Economics: the fair-rate estimate (see section 6).",
      "After booking: unlocks once you approve the creator — the post-decision toolkit (see section 7).",
    ],
  },
  {
    id: "fraud",
    title: "5. Understand the fraud flags",
    steps: [
      "Comment pod: a cluster of accounts commenting across many unrelated creators — the hardest-to-fake signal, tracked in a cross-run graph that gets stronger every campaign.",
      "Bought followers: reach collapses far below what the follower count implies.",
      "Templated / burst comments, thin commenters, view spikes: bot and boosted-post signatures.",
      "Withheld checks (in the internal report) mean the peer sample was too small to judge honestly (the n≥15 rule) — Kollab says so rather than guessing.",
      "Commenter overlap: two shortlisted creators sharing a big slice of the same commenters — booking both double-serves that audience. Shown above the table.",
    ],
  },
  {
    id: "rate",
    title: "6. Set the fair-rate estimate",
    steps: [
      "The Economics tab estimates a per-post rate band from the creator's own measured organic reach × your CPM assumption × authenticity.",
      "Drag the CPM slider — it is YOUR assumption (anchor it to your own closed-deal data), not a market rate card. The band rescales live.",
      "A flagged creator reads 'not reach-priceable' because Kollab assesses the reach as non-organic — the fraud finding flows straight into the price.",
    ],
  },
  {
    id: "after",
    title: "7. After you approve a creator",
    steps: [
      "Approve/reject in the Evidence tab (overriding a flag asks for a reason — it's on the record).",
      "Re-audit delivered post: after the paid post goes live, re-run the same detectors on it to catch a creator who was clean when vetted but bought engagement for the sponsored content.",
      "Delivery ledger: log what the post actually delivered vs the projection. Nothing is estimated until you log a delivery; once you do, it nudges the creator's fit (bounded) so future shortlists learn from real outcomes.",
      "Outreach draft: a grounded, bilingual first-contact message. Internal fraud signals are never included — review before sending.",
    ],
  },
  {
    id: "export",
    title: "8. Export",
    steps: [
      "Export → Client shortlist: a clean, presentable view for the client with the fraud internals hidden.",
      "Export → Internal report: the full evidence dossier — every check per creator, including the withheld ones. Save either as PDF from the print dialog.",
    ],
  },
  {
    id: "moat",
    title: "9. The fraud-recall moat",
    steps: [
      "Every run records its shared-commenter edges to a persistent graph (see the Fraud graph card on the Dashboard and in Settings).",
      "A pod that only touched a couple of this run's creators but hits many across your history gets caught — recall provably improves every campaign.",
      "That accumulating, cross-brand graph is the proprietary asset a competitor can't fork.",
    ],
  },
  {
    id: "keys",
    title: "10. Run on your own credit (optional)",
    steps: [
      "Settings → paste your own Apify / Claude keys. They stay in your browser, ride each request as headers, and are never stored on the server.",
      "The live credit meter shows what's left; the demo shortlist always runs free.",
    ],
  },
]

function toMarkdown(): string {
  const lines: string[] = ["# Kollab — Operating Guide", "", INTRO, ""]
  for (const s of GUIDE) {
    lines.push(`## ${s.title}`, "")
    for (const step of s.steps) lines.push(`- ${step}`)
    lines.push("")
  }
  return lines.join("\n")
}

export function Guide() {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(toMarkdown())
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      /* clipboard blocked — the on-screen guide is still fully readable */
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link
        to="/app"
        className="mb-4 inline-flex min-h-[32px] items-center gap-1.5 text-[13px] font-medium text-ink-500 transition-colors duration-200 hover:text-brand"
      >
        <ArrowLeft size={15} /> Back to shortlist
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-[26px] font-bold tracking-[-0.02em] text-ink">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-50 text-brand">
              <LifeBuoy size={17} />
            </span>
            Operating guide
          </h1>
          <p className="mt-1.5 max-w-xl text-[14px] text-ink-500">{INTRO}</p>
        </div>
        <Button onClick={copy} leadingIcon={copied ? <Check size={16} /> : <ClipboardCopy size={16} />}>
          {copied ? "Copied" : "Copy as Markdown"}
        </Button>
      </div>

      <div className="mt-7 space-y-4">
        {GUIDE.map((s) => (
          <section key={s.id} className="rounded-2xl border border-border bg-white p-6 shadow-sm">
            <h2 className="text-[16px] font-semibold text-ink">{s.title}</h2>
            <ul className="mt-3 space-y-2">
              {s.steps.map((st, i) => (
                <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-700">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
                  <span>{st}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}

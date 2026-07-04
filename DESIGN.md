# Design

> **v2 — measured, not assumed.** This system was extracted from convertcake.com on 2026-07-02 via a Playwright crawl of 6 pages: computed styles, their theme's own CSS variables, logo, and 12 stylesheets (reference material in `frontend/.impeccable/reference/convertcake/`, gitignored). Values marked **(measured)** come straight from their site; everything else is our extension of their language into product UI. Live reference: the `/design-system` route.

## Theme

Light, white-dominant, **cobalt-forward** — Convert Cake's actual marketing language extended into a data-dense internal tool.

**Physical scene:** an account manager at a desk in a bright Bangkok office, mid-task, scanning a KOL shortlist they'll show a client within the hour. → Light mode. **Color strategy: Restrained** in the tool (white surfaces, cobalt for brand/primary/selection only; green = verified/growth; red/amber = fraud/risk only). The **landing mirrors their marketing site** (near-1:1), where cobalt is more present: highlighted headline words, kickers, stat numbers.

## Color (measured CI)

Their theme's own root variables: `--theme-main-color: #0536D2` · `--theme-sub-color: #2D303C` · `--text-default-color: #75809D`.

| Token | Hex | Source | Role |
|---|---|---|---|
| `--brand` | `#0536D2` | **(measured — their main color)** | primary actions, links, selection, highlighted headline words, kickers |
| `--brand-hover` | `#0430BC` | derived | primary hover |
| `--brand-active` | `#032795` | derived | primary active |
| `--brand-300` | `#597EF3` | derived | focus ring, secondary accent |
| `--brand-100` | `#C8D4FB` | **(measured — their pill tint)** | brand pills: tint bg + cobalt text |
| `--brand-50` | `#E6ECFD` | **(measured — their panel tint)** | stat chips, selected rows, soft panels |
| `--ink` | `#2D303C` | **(measured — their sub color)** | headings, primary text |
| `--ink-900` | `#000E3F` | **(measured — their navy)** | sidebar, footer, dark sections |
| `--ink-800` | `#122252` | derived | hover surfaces on navy |
| `--ink-700` | `#41465A` | derived | secondary text |
| `--ink-500` | `#5B6580` | derived (their `#75809D` **darkened to hold AA ≥4.5:1**) | muted body text |
| `--ink-400` | `#75809D` | **(measured — their default text; ~3.7:1, fails AA small)** | large/secondary text ≥18px only |
| `--bg` / `--surface` / `--panel` | `#FFF` / `#F8F9FB` / `#F1F3F7` | aligned to their `#F9FAFB`/`#F7F7F7` | surfaces |
| `--verified` | `#1D8102` | derived (their growth green `#38B900` darkened for AA) | authentic/verified text & badges; `#38B900` allowed for icons/large numerals |
| `--risk-high` / `--risk-med` | `#D92D20` / `#B54708` | ours (their CI has no alert colors) | fraud / caution — reserved strictly for risk |

**Deliberate deviation (documented):** their body text `#75809D` fails WCAG AA on white. We keep the hue but ship `#5B6580` for body-size text — the reference look survives, the accessibility doesn't regress.

**State vocabulary:** default, hover, focus (2px `--brand-300` ring, 2px offset), active, disabled (40% + not-allowed), selected (`--brand-50` bg — full-cell tint, never a side-stripe), loading (skeleton), error (`--risk-high`).

## Typography (measured)

**Manrope everything** — their site runs one family at multiple weights; body text at **weight 500** is part of their voice. Thai: **Noto Sans Thai**.

| Role | Spec (measured from their site) |
|---|---|
| H1 / display | 48px · 700 · lh 1.2 · **−0.02em** · ink — with **one keyword in cobalt** (their signature move) |
| H2 / section | 40px · 700 · lh 1.4 · −0.025em · ink |
| Kicker | 16px · 500 · uppercase · cobalt — **their actual section grammar**, used in a left margin column on marketing surfaces; sparingly-to-never inside the tool |
| H4 / card title | 18px · 600 · lh 1.4 |
| Body | 16px · **500** · lh 1.4 on marketing; the tool runs 14px body for density |
| Nav / labels | 16px · 500 (marketing) · 13px · 500 (tool) |

Tool scale stays: 12 micro · 13 label · 14 body · 16 subhead · 20 section · 24 view-title · 28 page-title. **Tabular numerals** on all metrics. `text-wrap: balance` on headings.

## Signature elements (their grammar, adopted)

1. **Cobalt keyword in an ink headline** — one phrase per headline, never more.
2. **Tint pill** — `#C8D4FB` bg, cobalt text, fully rounded, 14px/500, optional leading icon.
3. **Outlined stat card** — white, 1.5px cobalt border, `--radius-2xl`, huge tabular number (40–48px/700 ink), small muted label.
4. **Floating stat chip** — `#E6ECFD` tint, rounded-xl, big cobalt number + 10–11px label; floats over imagery/cards.
5. **Left-margin kicker sections** — cobalt uppercase kicker in a narrow left column, content right (marketing surfaces only).
6. **Flow diagram** — outlined boxes + connector lines + small labeled chips (their "brand → services → channels" pattern; ours maps Brand → pipeline → shortlist).
7. **Soft cool elevation** — `rgba(73,104,126,.16)` / `rgba(147,178,199,.15)` shadows, never harsh black.
8. **Deep navy dark sections** — `#000E3F` footer/sidebar; white text, muted `rgba(255,255,255,.5–.85)`.
9. **CTA anatomy** — cobalt fill, **8px radius**, 600 weight, arrow-right that nudges on hover.

## Radius & elevation (measured)

Radii: 4 · 6 · **8 (buttons)** · 12 · **16 (cards)** · **24 (panels)** · pills `rounded-full`. Shadows: see tokens — `--shadow-md` is their measured `0 16px 24px rgba(73,104,126,.16)`.

## Components

App shell (navy sidebar + top bar + content), primary/secondary/ghost/danger buttons (8px), tint pills, outlined stat cards, floating stat chips, KOL shortlist row + expandable evidence panel, score bar (tabular), **fraud-risk badge** (icon + label + triggered signal), **verified badge**, **provenance chip** (measured/inferred/estimated), tier chip, HITL controls, pipeline step indicator, skeleton loaders, teaching empty states, cost/latency meter, export modal. Icons: **Lucide only** in the product (their site's FontAwesome is a WordPress artifact, not CI). The shortlist stays a dense table, never a card grid; no nested cards.

## Layout

Fixed left sidebar (**`--ink-900` navy**) + top bar + content on `--bg`/`--surface`. Landing: white sticky nav, max-w-7xl, left-margin-kicker sections, navy footer. Sidebar collapses to drawer < `lg`; shortlist → stacked cards < `sm`. Semantic z-index scale: `base(0) < sticky(10) < dropdown(20) < popover(30) < backdrop(40) < modal(50) < toast(60) < tooltip(70)`.

## Motion

Their measured baseline: **0.3s ease** on interactions, **0.5s `cubic-bezier(.215,.61,.355,1)`** (`--ease-out-cubic`) for reveals, fade-up entrances on scroll. Ours: tool interactions 150–250ms ease-out (quart/expo), state-conveying only — no page-load choreography inside the tool; the landing may use scroll reveals and staggered entrances per their site. Every animation has a `prefers-reduced-motion: reduce` alternative. Library: `motion` + CSS transitions.

## Fidelity ledger (theirs vs. ours)

- **Theirs (measured):** cobalt `#0536D2`, ink `#2D303C`, navy `#000E3F`, tints `#C8D4FB`/`#E6ECFD`, muted `#75809D`, growth green `#38B900`, Manrope + weights, 8/16/24 radii + pills, cool shadows, 0.3s/0.5s ease-out motion, kickers, keyword-highlight headlines, stat cards/chips, flow diagrams, navy footer.
- **Ours (extension/deviation):** risk red/amber (they ship no alert palette), AA-darkened `#5B6580` body + `#1D8102` verified, 14px tool density scale, Lucide icons, provenance/fraud/HITL component family, semantic z-index, reduced-motion policy.

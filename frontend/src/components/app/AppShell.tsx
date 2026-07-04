import { useEffect, useRef, useState } from "react"
import { Outlet, useLocation } from "react-router-dom"
import { motion } from "motion/react"
import { Sidebar } from "./Sidebar"
import { Topbar } from "./Topbar"

export type Density = "comfortable" | "spacious"

const DENSITY_KEY = "kollab-density"

/** Shared with in-app views via Outlet context (see useOutletContext in Shortlist). */
export interface AppContext {
  search: string
  setSearch: (q: string) => void
}

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false)
  const [search, setSearch] = useState("")
  const { pathname } = useLocation()
  const firstPaint = useRef(true)
  useEffect(() => {
    firstPaint.current = false
  }, [])
  const [density, setDensity] = useState<Density>(() => {
    const saved = localStorage.getItem(DENSITY_KEY)
    return saved === "spacious" ? "spacious" : "comfortable"
  })
  useEffect(() => {
    localStorage.setItem(DENSITY_KEY, density)
  }, [density])

  return (
    <div className="flex min-h-svh bg-surface" data-density={density}>
      {/* keyboard users bypass the sidebar + topbar (~10 tab stops) */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-brand focus:px-4 focus:py-2 focus:text-[13px] focus:font-semibold focus:text-white"
      >
        Skip to content
      </a>
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          onMenu={() => setNavOpen(true)}
          density={density}
          onDensity={setDensity}
          search={search}
          onSearch={setSearch}
        />
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 outline-none">
          {/* In-app view transition: ENTER-ONLY fade-rise on route change.
              No AnimatePresence/exit choreography — "wait"-mode can wedge to a
              blank outlet when navigation interrupts an in-flight transition.
              First paint renders settled (no entrance into a task). */}
          <motion.div
            key={pathname}
            initial={firstPaint.current ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
          >
            <Outlet context={{ search, setSearch } satisfies AppContext} />
          </motion.div>
        </main>
      </div>
    </div>
  )
}

import { useEffect, useRef } from "react"
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom"
import { MotionConfig, motion } from "motion/react"
import { Landing } from "./pages/Landing"
import { AppShell } from "./components/app/AppShell"
import { Shortlist } from "./pages/Shortlist"
import { NewShortlist } from "./pages/NewShortlist"
import { PipelineRun } from "./pages/PipelineRun"
import { DesignSystem } from "./pages/DesignSystem"

const EASE_OUT_QUART = [0.25, 1, 0.5, 1] as const

/** Fade-in between top-level surfaces (landing ↔ app ↔ design-system).
    ENTER-ONLY on purpose: exit choreography via AnimatePresence mode="wait"
    can wedge to a blank screen when navigation interrupts an in-flight
    transition. In-app navigation animates at the Outlet level in AppShell.
    First paint renders settled. Reduced motion: global MotionConfig. */
function AnimatedRoutes() {
  const location = useLocation()
  const segment = location.pathname.split("/")[1] || "home"
  const firstPaint = useRef(true)
  useEffect(() => {
    firstPaint.current = false
  }, [])
  return (
    <motion.div
      key={segment}
      initial={firstPaint.current ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15, ease: EASE_OUT_QUART }}
    >
      <Routes location={location}>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Shortlist />} />
          <Route path="shortlist" element={<Shortlist />} />
          <Route path="new" element={<NewShortlist />} />
          <Route path="run" element={<PipelineRun />} />
        </Route>
        <Route path="/design-system" element={<DesignSystem />} />
        <Route path="/system" element={<Navigate to="/design-system" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </motion.div>
  )
}

export function App() {
  return (
    <BrowserRouter>
      {/* reducedMotion="user": every motion/react animation respects the OS setting */}
      <MotionConfig reducedMotion="user">
        <AnimatedRoutes />
      </MotionConfig>
    </BrowserRouter>
  )
}

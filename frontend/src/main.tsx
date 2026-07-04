import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@fontsource-variable/manrope"
import "@fontsource/noto-sans-thai/400.css"
import "@fontsource/noto-sans-thai/500.css"
import "@fontsource/noto-sans-thai/600.css"
import "@fontsource/noto-sans-thai/700.css"
import "./index.css"
import { App } from "./App"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

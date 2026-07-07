import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Drop the `crossorigin` attribute Vite stamps on the emitted <link>/<script>
 * asset tags. Our assets are same-origin, so CORS mode buys nothing — but it
 * makes the browser send an `Origin` header, and Cloudflare caches the CORS
 * response under a SEPARATE variant. During a deploy's edge-propagation gap a
 * browser's CORS request for a not-yet-live hashed asset can be answered with
 * the SPA-fallback index.html (200 text/html) and cached hard under the
 * `_headers` `immutable` rule — poisoning the Origin variant so every real
 * browser (which sends Origin) gets HTML for a .css and renders unstyled, while
 * curl (no Origin) sees the clean copy. Without crossorigin the stylesheet is a
 * plain (non-CORS) fetch that hits the reliable default variant. See
 * docs/GO-LIVE.md §6.
 */
function stripCrossorigin(): Plugin {
  return {
    name: 'strip-crossorigin-attrs',
    enforce: 'post',
    transformIndexHtml: {
      order: 'post',
      handler(html) {
        return html.replace(/\s+crossorigin(?:=(?:"[^"]*"|'[^']*'|\S+))?/g, '')
      },
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), stripCrossorigin()],
  // Pinned so the README's documented dev URL and the backend's primary CORS
  // origin (backend/app/main.py) are true on any machine.
  server: { port: 5178 },
})

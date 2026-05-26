import { watch } from 'vue'
import { useViewport } from './useViewport'

// Map viewport width → uniform UI scale applied to every `calc(Xvmin * var(--app-scale))`
// token in global.css. This lets fluid sizing adapt across iPhone SE, Pixel, iPad, desktop
// without per-page media queries.
function scaleFor(w: number): number {
  if (w < 380) return 0.85   // iPhone SE / very narrow
  if (w < 430) return 0.95   // standard mobile (Pixel 10 ~393)
  if (w < 768) return 1.0    // large phones / phablet
  if (w < 1024) return 1.15  // tablet
  return 1.3                  // desktop letterbox
}

let installed = false

export function useAppScale() {
  if (installed) return
  installed = true

  const vp = useViewport()
  const apply = () => {
    document.documentElement.style.setProperty('--app-scale', String(scaleFor(vp.w)))
  }
  apply()
  watch(() => vp.w, apply, { flush: 'post' })
}

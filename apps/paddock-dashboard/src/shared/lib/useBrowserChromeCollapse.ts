import { onMounted, onUnmounted, watch } from 'vue'
import { useViewport } from './useViewport'

function isStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  )
}

function syncViewportVars() {
  const vv = window.visualViewport
  const h = vv?.height ?? window.innerHeight
  const w = vv?.width ?? window.innerWidth
  document.documentElement.style.setProperty('--app-vh', `${h}px`)
  document.documentElement.style.setProperty('--app-vw', `${w}px`)
}

function collapseBrowserChrome() {
  const root = document.documentElement
  const body = document.body
  const wasImmersive = root.classList.contains('landscape-immersive')

  // Briefly allow scroll so Chrome collapses the URL / tab bar.
  if (wasImmersive) root.classList.remove('landscape-immersive')
  body.style.minHeight = `${window.innerHeight + 2}px`
  body.style.overflow = 'auto'

  window.scrollTo(0, 1)

  requestAnimationFrame(() => {
    window.scrollTo(0, 0)
    body.style.minHeight = ''
    body.style.overflow = ''
    if (wasImmersive && window.innerWidth > window.innerHeight) {
      root.classList.add('landscape-immersive')
    }
    syncViewportVars()
  })
}

async function tryFullscreen() {
  if (isStandalone() || document.fullscreenElement) return
  try {
    await document.documentElement.requestFullscreen({ navigationUI: 'hide' })
  } catch {
    // Blocked without user gesture or by policy — expected in browser tab.
  }
}

async function exitFullscreenIfNeeded() {
  if (document.fullscreenElement && !isStandalone()) {
    try {
      await document.exitFullscreen()
    } catch {
      // Ignore
    }
  }
}

export function useBrowserChromeCollapse() {
  const viewport = useViewport()
  let retryTimers: number[] = []
  let touchCleanup: (() => void) | undefined

  const clearRetries = () => {
    retryTimers.forEach(clearTimeout)
    retryTimers = []
  }

  const enterLandscapeImmersive = () => {
    document.documentElement.classList.add('landscape-immersive')
    syncViewportVars()
    collapseBrowserChrome()
    void tryFullscreen()

    // Toolbar can reappear briefly after orientation settles.
    retryTimers.push(window.setTimeout(collapseBrowserChrome, 100))
    retryTimers.push(window.setTimeout(collapseBrowserChrome, 350))
  }

  const leaveLandscapeImmersive = () => {
    clearRetries()
    document.documentElement.classList.remove('landscape-immersive')
    void exitFullscreenIfNeeded()
    syncViewportVars()
  }

  const onOrientationChange = () => {
    if (viewport.isPortrait) leaveLandscapeImmersive()
    else enterLandscapeImmersive()
  }

  const onViewportChange = () => syncViewportVars()

  const bindFirstTouchFullscreen = () => {
    touchCleanup?.()
    const onFirstTouch = () => {
      if (!viewport.isPortrait) void tryFullscreen()
      window.removeEventListener('touchstart', onFirstTouch, true)
      touchCleanup = undefined
    }
    window.addEventListener('touchstart', onFirstTouch, { capture: true, passive: true })
    touchCleanup = () => window.removeEventListener('touchstart', onFirstTouch, true)
  }

  watch(
    () => viewport.isPortrait,
    (portrait) => {
      if (portrait) leaveLandscapeImmersive()
      else {
        enterLandscapeImmersive()
        bindFirstTouchFullscreen()
      }
    },
    { immediate: true },
  )

  onMounted(() => {
    syncViewportVars()
    window.visualViewport?.addEventListener('resize', onViewportChange)
    window.visualViewport?.addEventListener('scroll', onViewportChange)
    window.addEventListener('orientationchange', onOrientationChange)
    if (!viewport.isPortrait) bindFirstTouchFullscreen()
  })

  onUnmounted(() => {
    clearRetries()
    touchCleanup?.()
    window.visualViewport?.removeEventListener('resize', onViewportChange)
    window.visualViewport?.removeEventListener('scroll', onViewportChange)
    window.removeEventListener('orientationchange', onOrientationChange)
    leaveLandscapeImmersive()
  })
}

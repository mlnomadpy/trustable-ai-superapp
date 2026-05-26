import { onMounted, onUnmounted, reactive, readonly } from 'vue'

export type Breakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

const BREAKPOINTS: { name: Breakpoint; minWidth: number }[] = [
  { name: 'xs', minWidth: 0 },     // iPhone SE landscape ≤ 568
  { name: 'sm', minWidth: 568 },   // small phones landscape
  { name: 'md', minWidth: 768 },   // Pixel / iPhone Pro landscape, tablet portrait
  { name: 'lg', minWidth: 1024 },  // tablet landscape / small desktop
  { name: 'xl', minWidth: 1440 },  // desktop
]

function breakpointFor(w: number): Breakpoint {
  let bp: Breakpoint = 'xs'
  for (const b of BREAKPOINTS) if (w >= b.minWidth) bp = b.name
  return bp
}

interface ViewportState {
  w: number
  h: number
  isPortrait: boolean
  isMobile: boolean
  isTablet: boolean
  isDesktop: boolean
  breakpoint: Breakpoint
}

const state = reactive<ViewportState>({
  w: typeof window !== 'undefined' ? window.innerWidth : 1024,
  h: typeof window !== 'undefined' ? window.innerHeight : 768,
  isPortrait: false,
  isMobile: false,
  isTablet: false,
  isDesktop: true,
  breakpoint: 'lg',
})

function refresh() {
  const w = window.innerWidth
  const h = window.innerHeight
  state.w = w
  state.h = h
  state.isPortrait = h > w
  state.breakpoint = breakpointFor(w)
  state.isMobile = state.breakpoint === 'xs' || state.breakpoint === 'sm'
  state.isTablet = state.breakpoint === 'md'
  state.isDesktop = state.breakpoint === 'lg' || state.breakpoint === 'xl'
}

let listenerCount = 0
let installed = false
function install() {
  if (installed || typeof window === 'undefined') return
  installed = true
  refresh()
  window.addEventListener('resize', refresh, { passive: true })
  window.addEventListener('orientationchange', refresh, { passive: true })
}

export function useViewport() {
  onMounted(() => {
    if (listenerCount === 0) install()
    listenerCount++
  })
  onUnmounted(() => {
    listenerCount = Math.max(0, listenerCount - 1)
  })
  if (!installed && typeof window !== 'undefined') install()
  return readonly(state)
}

// Eager singleton accessor for use outside component setup (e.g. router guards, stores)
export function getViewport() {
  if (!installed && typeof window !== 'undefined') install()
  return readonly(state)
}

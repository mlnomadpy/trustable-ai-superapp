import { onMounted, onUnmounted } from 'vue'

// On mobile, when the soft keyboard appears, focused inputs and the action
// buttons beneath them can be hidden behind the keyboard. Vue's normal scroll
// behavior doesn't help — we listen for focus events and scroll the active
// input into view with a safe-area-aware offset.
//
// Uses `visualViewport` when available (modern iOS/Android) for accurate
// keyboard height; falls back to scrollIntoView otherwise.

const SCROLL_DELAY = 250   // wait for keyboard animation
const PADDING = 16          // gap between input bottom and keyboard top

function isEditable(el: EventTarget | null): el is HTMLElement {
  if (!(el instanceof HTMLElement)) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable
}

function scrollFocusedIntoView() {
  const el = document.activeElement
  if (!isEditable(el)) return

  const vv = window.visualViewport
  if (vv && vv.height < window.innerHeight - 100) {
    // Soft keyboard likely open; scroll precisely above its top edge
    const rect = el.getBoundingClientRect()
    const keyboardTop = vv.height + vv.offsetTop
    const overlap = rect.bottom - keyboardTop + PADDING
    if (overlap > 0) {
      window.scrollBy({ top: overlap, behavior: 'smooth' })
    }
  } else {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

export function useKeyboardAvoidance() {
  let focusTimer: number | undefined
  let vvTimer: number | undefined

  const onFocusIn = (e: FocusEvent) => {
    if (!isEditable(e.target)) return
    window.clearTimeout(focusTimer)
    focusTimer = window.setTimeout(scrollFocusedIntoView, SCROLL_DELAY)
  }

  const onViewportResize = () => {
    window.clearTimeout(vvTimer)
    vvTimer = window.setTimeout(scrollFocusedIntoView, 100)
  }

  onMounted(() => {
    document.addEventListener('focusin', onFocusIn)
    window.visualViewport?.addEventListener('resize', onViewportResize)
  })

  onUnmounted(() => {
    document.removeEventListener('focusin', onFocusIn)
    window.visualViewport?.removeEventListener('resize', onViewportResize)
    window.clearTimeout(focusTimer)
    window.clearTimeout(vvTimer)
  })
}

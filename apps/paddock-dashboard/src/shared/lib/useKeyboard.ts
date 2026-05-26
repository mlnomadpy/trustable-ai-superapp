import { onMounted, onUnmounted } from 'vue'

const keyboardStack: ((e: KeyboardEvent) => void)[] = []

const globalKeyboardHandler = (e: KeyboardEvent) => {
  if (keyboardStack.length > 0) {
    const topHandler = keyboardStack[keyboardStack.length - 1]
    topHandler(e)
  }
}

// Only register the global listener once
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', globalKeyboardHandler, { capture: true })
}

/**
 * Composable that pushes a handler to the exclusivity stack on mount,
 * and pops it on unmount. Only the top-most handler fires.
 */
export function useKeyboard(handler: (e: KeyboardEvent) => void) {
  onMounted(() => {
    keyboardStack.push(handler)
  })

  onUnmounted(() => {
    const idx = keyboardStack.indexOf(handler)
    if (idx !== -1) {
      keyboardStack.splice(idx, 1)
    }
  })
}

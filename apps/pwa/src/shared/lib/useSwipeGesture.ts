import { onMounted, onUnmounted, type Ref } from 'vue'

export interface SwipeHandlers {
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
  onSwipeUp?: () => void
  onSwipeDown?: () => void
}

interface SwipeOptions {
  /** Minimum distance in px to trigger a swipe (default: 50) */
  threshold?: number
  /** Maximum time in ms for the gesture (default: 400) */
  maxTime?: number
}

/**
 * Composable to detect swipe gestures on a target element.
 * If no target ref is provided, listens on the entire document.
 * 
 * @example
 * ```ts
 * useSwipeGesture(containerRef, {
 *   onSwipeLeft: () => nextTab(),
 *   onSwipeRight: () => prevTab(),
 * })
 * ```
 */
export function useSwipeGesture(
  target: Ref<HTMLElement | null> | null,
  handlers: SwipeHandlers,
  options: SwipeOptions = {}
) {
  const threshold = options.threshold ?? 50
  const maxTime = options.maxTime ?? 400

  let startX = 0
  let startY = 0
  let startTime = 0

  const handleTouchStart = (e: TouchEvent) => {
    const touch = e.touches[0]
    startX = touch.clientX
    startY = touch.clientY
    startTime = Date.now()
  }

  const handleTouchEnd = (e: TouchEvent) => {
    const touch = e.changedTouches[0]
    const dx = touch.clientX - startX
    const dy = touch.clientY - startY
    const dt = Date.now() - startTime

    if (dt > maxTime) return

    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)

    // Must exceed threshold and be clearly directional
    if (absDx < threshold && absDy < threshold) return

    if (absDx > absDy) {
      // Horizontal swipe
      if (dx > 0 && handlers.onSwipeRight) {
        handlers.onSwipeRight()
      } else if (dx < 0 && handlers.onSwipeLeft) {
        handlers.onSwipeLeft()
      }
    } else {
      // Vertical swipe
      if (dy > 0 && handlers.onSwipeDown) {
        handlers.onSwipeDown()
      } else if (dy < 0 && handlers.onSwipeUp) {
        handlers.onSwipeUp()
      }
    }
  }

  onMounted(() => {
    const el = target?.value ?? document
    el.addEventListener('touchstart', handleTouchStart as EventListener, { passive: true })
    el.addEventListener('touchend', handleTouchEnd as EventListener, { passive: true })
  })

  onUnmounted(() => {
    const el = target?.value ?? document
    el.removeEventListener('touchstart', handleTouchStart as EventListener)
    el.removeEventListener('touchend', handleTouchEnd as EventListener)
  })
}

import { onMounted, onUnmounted } from 'vue'

export function useTouchNavigation(threshold = 40) {
  let touchStartX = 0
  let touchStartY = 0
  let touchLastX = 0
  let touchLastY = 0

  const onGlobalTouchStart = (e: TouchEvent) => {
    if (e.touches.length > 0) {
      touchStartX = e.touches[0].clientX
      touchStartY = e.touches[0].clientY
      touchLastX = touchStartX
      touchLastY = touchStartY
    }
  }

  const onGlobalTouchMove = (e: TouchEvent) => {
    if (e.touches.length > 0) {
      const currentX = e.touches[0].clientX
      const currentY = e.touches[0].clientY
      const deltaX = currentX - touchLastX
      const deltaY = currentY - touchLastY
      
      // Dispatch the dominant axis if it exceeds the threshold
      if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > threshold) {
        const key = deltaX > 0 ? 'ArrowRight' : 'ArrowLeft'
        window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
        touchLastX = currentX
        touchLastY = currentY
      } else if (Math.abs(deltaY) > threshold) {
        const key = deltaY > 0 ? 'ArrowDown' : 'ArrowUp'
        window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
        touchLastX = currentX
        touchLastY = currentY
      }
    }
  }

  onMounted(() => {
    window.addEventListener('touchstart', onGlobalTouchStart, { passive: true })
    window.addEventListener('touchmove', onGlobalTouchMove, { passive: true })
  })

  onUnmounted(() => {
    window.removeEventListener('touchstart', onGlobalTouchStart)
    window.removeEventListener('touchmove', onGlobalTouchMove)
  })
}

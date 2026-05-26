<script setup lang="ts">
import { ref, onMounted } from 'vue'

const showUpdate = ref(false)

onMounted(() => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      showUpdate.value = true
    })
    
    // Also check for waiting service worker on load
    navigator.serviceWorker.getRegistration().then((reg) => {
      if (reg?.waiting) {
        showUpdate.value = true
      }
      reg?.addEventListener('updatefound', () => {
        const newSW = reg.installing
        newSW?.addEventListener('statechange', () => {
          if (newSW.state === 'installed' && navigator.serviceWorker.controller) {
            showUpdate.value = true
          }
        })
      })
    })
  }
})

const reload = () => {
  window.location.reload()
}
</script>

<template>
  <Transition name="toast-slide">
    <div v-if="showUpdate" class="update-toast" @click="reload">
      <span class="update-icon">⟳</span>
      <span class="update-text">UPDATE READY — TAP TO RELOAD</span>
    </div>
  </Transition>
</template>

<style scoped>
.update-toast {
  position: fixed;
  bottom: clamp(12px, 3vh, 24px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: clamp(6px, 1.5vmin, 12px) clamp(12px, 3vmin, 24px);
  background: var(--color-ui-good, #4ecdc4);
  color: var(--color-ink, #0d0d12);
  font-family: var(--font-ui, monospace);
  font-size: clamp(10px, 2.5vmin, 16px);
  font-weight: 700;
  letter-spacing: 0.05em;
  border-radius: 4px;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(78, 205, 196, 0.4);
  animation: toast-pulse 2s infinite ease-in-out;
}

.update-icon {
  font-size: 1.2em;
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes toast-pulse {
  0%, 100% { box-shadow: 0 4px 20px rgba(78, 205, 196, 0.4); }
  50% { box-shadow: 0 4px 30px rgba(78, 205, 196, 0.7); }
}

.toast-slide-enter-active {
  transition: all 0.4s cubic-bezier(0.22, 0.68, 0, 1.71);
}

.toast-slide-leave-active {
  transition: all 0.3s ease-in;
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(20px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(20px);
}
</style>

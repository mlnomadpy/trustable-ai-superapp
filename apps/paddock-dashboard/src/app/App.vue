<script setup lang="ts">
import { onMounted, onUnmounted, watch, computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { usePauseStore } from '@/shared/lib/pauseStore'
import { useCoachSpeaksStore } from '@/features/coach-interaction/model/coachSpeaksStore'
import BridgeOfflineBanner from '@/widgets/bridge-offline/BridgeOfflineBanner.vue'
import PauseMenu from '@/widgets/pause-menu/PauseMenu.vue'
import CoachSpeaksModal from '@/widgets/dialogue-box/CoachSpeaksModal.vue'
import ParticleBackground from '@/shared/ui/ParticleBackground.vue'
import UpdateToast from '@/widgets/update-toast/UpdateToast.vue'
import TransitionWipe from '@/widgets/transition-wipe/TransitionWipe.vue'
import FullscreenToggle from '@/widgets/fullscreen-toggle/FullscreenToggle.vue'
import DiagnosticBar from '@/widgets/diagnostic-bar/DiagnosticBar.vue'
import InstallPrompt from '@/widgets/install-prompt/InstallPrompt.vue'
import { useTouchNavigation } from '@/shared/lib/useTouchNavigation'
import { useViewport } from '@/shared/lib/useViewport'
import { useAppScale } from '@/shared/lib/useAppScale'
import { useKeyboardAvoidance } from '@/shared/lib/useKeyboardAvoidance'
import { useBrowserChromeCollapse } from '@/shared/lib/useBrowserChromeCollapse'

const saveStore = useSaveStore()
const audioStore = useAudioStore()
const bridgeStore = useBridgeStore()
const pauseStore = usePauseStore()
const coachSpeaksStore = useCoachSpeaksStore()
const route = useRoute()
const router = useRouter()

useAppScale()
useKeyboardAvoidance()
useBrowserChromeCollapse()
const viewport = useViewport()
const isPortrait = computed(() => viewport.isPortrait)

const handleGlobalKey = (e: KeyboardEvent) => {
  if ((e as KeyboardEvent & { __pitwallHintTap?: boolean }).__pitwallHintTap) return
  if (isPortrait.value) return // Block input in portrait

  // Unified key contract:
  //   ESC  -> router.back() on every page except the title screen
  //   P    -> opens the pause overlay, but only on routes that opt in
  //           via meta.allowPause (typically in-session pages like /hud)
  //
  // If the pause overlay is currently visible, ESC dismisses it instead of
  // popping the route, so the user can return to the page they were on.
  if (e.key === 'Escape') {
    if (pauseStore.isVisible) {
      audioStore.playSfx('cancel')
      pauseStore.closePause()
      return
    }
    if (route.path !== '/') {
      audioStore.playSfx('transition_wipe')
      router.back()
    }
    return
  }

  if ((e.key === 'p' || e.key === 'P') && route.meta?.allowPause === true) {
    audioStore.playSfx('transition_wipe')
    pauseStore.togglePause()
  }
}

useTouchNavigation()

watch(() => saveStore.activeSlot?.settings?.display?.reducedMotion, (reduce) => {
  if (reduce) {
    document.body.classList.add('reduced-motion')
  } else {
    document.body.classList.remove('reduced-motion')
  }
}, { immediate: true })

onMounted(async () => {
  await saveStore.hydrate()
  bridgeStore.startPolling()
  window.addEventListener('keydown', handleGlobalKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKey)
})
</script>

<template>
  <div class="app-root">
    <!-- Component-level orientation lock prevents interaction bypass -->
    <div v-if="!isPortrait" class="app-container relative">
      <div class="crt-overlay" v-if="!route.meta.performance"></div>
  
      <RouterView v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
  
      <ParticleBackground v-if="!route.meta.performance" />
      <BridgeOfflineBanner />
      <PauseMenu />
      <CoachSpeaksModal 
        v-if="coachSpeaksStore.isVisible"
        :coach-id="coachSpeaksStore.coachId"
        :emotion="coachSpeaksStore.emotion"
        :title="coachSpeaksStore.title"
        :text="coachSpeaksStore.text"
        @close="coachSpeaksStore.dismiss()"
      />
      <UpdateToast />
      <TransitionWipe />
    </div>

    <!-- Persistent Portrait Warning -->
    <div v-else class="portrait-warning">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-16 h-16 mb-4 animate-bounce text-ui-warn" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect>
        <line x1="12" y1="18" x2="12.01" y2="18"></line>
        <path d="M19 8l-4-4-4 4"></path>
        <path d="M15 4v10"></path>
      </svg>
      <span class="text-white relative z-10 p-2 bg-ink/80 border-l-4 border-ui-good">PLEASE ROTATE YOUR DEVICE</span>
    </div>

    <!-- Global, always-visible overlays (work in both portrait + landscape) -->
    <DiagnosticBar />
    <FullscreenToggle />
    <InstallPrompt />
  </div>
</template>

<style scoped>
.app-root {
  width: var(--app-vw, 100dvw);
  height: var(--app-vh, 100dvh);
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #050505;
  overflow: hidden;
  background-image: url('data:image/svg+xml;utf8,<svg width="40" height="40" xmlns="http://www.w3.org/2000/svg"><path d="M0 0h40v40H0z" fill="none"/><path d="M0 0h1v1H0zm39 39h1v1h-1z" fill="rgba(255,255,255,0.02)"/></svg>');
}

.app-container {
  width: var(--app-vw, 100dvw);
  height: var(--app-vh, 100dvh);
  background-color: var(--color-ink);
  overflow: hidden;
  position: relative;
  padding: 0;
}

.app-container::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 150%;
  height: 150%;
  background: linear-gradient(
    135deg,
    rgba(255,255,255,0.05) 0%,
    rgba(255,255,255,0) 40%,
    rgba(255,255,255,0) 100%
  );
  pointer-events: none;
  z-index: 200;
  transform: translateY(-20%) translateX(-20%);
}

@media screen and (min-width: 1024px) {
  .app-container {
    width: min(var(--app-vw, 100dvw), 1600px);
    height: min(var(--app-vh, 100dvh), 900px);
    aspect-ratio: 16 / 9;
    border-radius: 24px;
    box-shadow: 
      0 0 0 4px #1a1a1a,
      0 0 0 12px #0a0a0a,
      inset 0 0 20px rgba(0,0,0,0.8),
      0 20px 40px rgba(0,0,0,0.9);
  }
}

.portrait-warning {
  position: absolute;
  inset: 0;
  background-color: var(--color-ink);
  color: white;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-family: var(--font-title);
  font-size: clamp(14px, 3.5vmin, 28px);
  text-align: center;
  padding: clamp(16px, 4vmin, 32px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

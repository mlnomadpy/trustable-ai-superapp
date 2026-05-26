<!--
  MOUNT IN App.vue:
    import InstallPrompt from '@/widgets/install-prompt/InstallPrompt.vue'
    <InstallPrompt />  <!-- place once near other top-level widgets (e.g. UpdateToast) -->

  Surfaces Chrome's `beforeinstallprompt` event as a small sticky bottom-
  banner so users don't have to dig in the kebab menu to install the PWA.
  No-ops on iOS Safari (no BIP event), in already-installed standalone
  contexts, and for 7 days after the user dismisses.
-->
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'

// Chrome's BeforeInstallPromptEvent isn't in the standard DOM lib types.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

const DISMISS_KEY = 'installDismissed'
const DISMISS_COOLDOWN_DAYS = 7

const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)
const dismissed = ref<boolean>(false)
const installed = ref<boolean>(false)

const todayIso = (): string => {
  // YYYY-MM-DD in local time — date precision is enough for a cooldown.
  const d = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const daysSince = (iso: string): number => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return Number.POSITIVE_INFINITY
  const then = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getTime()
  const diffMs = Date.now() - then
  return diffMs / (1000 * 60 * 60 * 24)
}

const isStandalone = (): boolean => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  // `standalone` covers Android Chrome WebAPK + desktop installs; iOS
  // Safari exposes `navigator.standalone` separately.
  const nav = window.navigator as Navigator & { standalone?: boolean }
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    nav.standalone === true
  )
}

const isCoolingDown = (): boolean => {
  try {
    const last = localStorage.getItem(DISMISS_KEY)
    if (!last) return false
    return daysSince(last) < DISMISS_COOLDOWN_DAYS
  } catch {
    return false
  }
}

const show = computed<boolean>(() =>
  !installed.value && !dismissed.value && deferredPrompt.value !== null,
)

const onBeforeInstallPrompt = (e: Event) => {
  // Suppress Chrome's mini-infobar; we render our own banner.
  e.preventDefault()
  if (isCoolingDown()) return
  deferredPrompt.value = e as BeforeInstallPromptEvent
}

const onAppInstalled = () => {
  installed.value = true
  deferredPrompt.value = null
}

const install = async () => {
  const evt = deferredPrompt.value
  if (!evt) return
  try {
    await evt.prompt()
    await evt.userChoice
  } catch {
    /* prompt may throw if already consumed — treat as dismissed */
  }
  // BIP events are single-use; clear regardless of outcome.
  deferredPrompt.value = null
}

const dismiss = () => {
  dismissed.value = true
  try {
    localStorage.setItem(DISMISS_KEY, todayIso())
  } catch {
    /* storage may be disabled — banner still hidden for this session */
  }
}

onMounted(() => {
  if (isStandalone()) {
    installed.value = true
    return
  }
  if (isCoolingDown()) {
    dismissed.value = true
  }
  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.addEventListener('appinstalled', onAppInstalled)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.removeEventListener('appinstalled', onAppInstalled)
})
</script>

<template>
  <Transition name="install-slide">
    <div v-if="show" class="install-banner" role="dialog" aria-label="Install Pitwall">
      <span class="install-label">Install Pitwall as an app</span>
      <div class="install-actions">
        <CyberButton size="sm" variant="primary" @click="install">INSTALL</CyberButton>
        <button
          type="button"
          class="install-dismiss"
          aria-label="Dismiss install prompt"
          @click="dismiss"
        >
          ×
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.install-banner {
  position: fixed;
  left: 50%;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 54px); /* sit above HintBar */
  transform: translateX(-50%);
  z-index: 9998;
  display: flex;
  align-items: center;
  gap: clamp(8px, 2vmin, 16px);
  padding: clamp(6px, 1.5vmin, 12px) clamp(12px, 3vmin, 20px);
  background: rgba(13, 13, 18, 0.92);
  border: 1px solid color-mix(in srgb, var(--color-ui-good, #4ecdc4) 40%, transparent);
  border-radius: 6px;
  color: var(--color-silver, #d6d8df);
  font-family: var(--font-ui, monospace);
  font-size: clamp(11px, 2.4vmin, 14px);
  letter-spacing: 0.04em;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  max-width: calc(100vw - 32px);
}

.install-label {
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.install-actions {
  display: flex;
  align-items: center;
  gap: clamp(4px, 1vmin, 10px);
  flex-shrink: 0;
}

.install-dismiss {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid color-mix(in srgb, var(--color-slate, #6c7080) 50%, transparent);
  border-radius: 4px;
  color: var(--color-slate, #6c7080);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  -webkit-tap-highlight-color: transparent;
}

.install-dismiss:hover,
.install-dismiss:focus-visible {
  color: var(--color-silver, #d6d8df);
  border-color: var(--color-silver, #d6d8df);
  outline: none;
}

.install-slide-enter-active {
  transition: all 0.35s cubic-bezier(0.22, 0.68, 0, 1.71);
}
.install-slide-leave-active {
  transition: all 0.25s ease-in;
}
.install-slide-enter-from,
.install-slide-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(16px);
}
</style>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'

// Vendor-prefixed fullscreen surface (Safari / iOS / legacy WebKit)
interface VendorDocument extends Document {
  webkitFullscreenElement?: Element | null
  webkitExitFullscreen?: () => Promise<void>
}
interface VendorElement extends HTMLElement {
  webkitRequestFullscreen?: () => Promise<void>
}

const doc = document as VendorDocument
const docEl = document.documentElement as VendorElement

// Feature-detect: hide the button entirely when the browser exposes neither
// the standard nor the webkit-prefixed Fullscreen API. (Chrome on Android 16
// has both; iOS Safari has neither at the element level on iPhone.)
const supported = ref<boolean>(
  typeof docEl.requestFullscreen === 'function' ||
  typeof docEl.webkitRequestFullscreen === 'function'
)

const isFs = ref<boolean>(false)

// ─────────────────────────────────────────────────────────────────────────────
// Preference persistence
//
// The Web Fullscreen API drops fullscreen on every SPA route change (browser
// security: only same-document navigations preserve it). Without persistence
// the user has to tap the toggle on every page. We remember the user's
// last explicit choice in localStorage and try to re-enter fullscreen on
// mount. Re-entry requires a user gesture per spec, so the auto-request will
// often reject silently — that's expected, not an error.
// ─────────────────────────────────────────────────────────────────────────────
const STORAGE_KEY = 'fullscreenPreferred'

const readPref = (): boolean => {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

const writePref = (v: boolean) => {
  try {
    localStorage.setItem(STORAGE_KEY, v ? 'true' : 'false')
  } catch {
    /* storage may be disabled (private mode, etc.) — silently ignore */
  }
}

// Installed-PWA detection: when the manifest's display mode is `fullscreen`
// (or `standalone`) the WebAPK is already in fullscreen and the JS
// Fullscreen API is irrelevant. Skip auto-request in that case.
const isStandaloneOrManifestFullscreen = (): boolean => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return (
    window.matchMedia('(display-mode: fullscreen)').matches ||
    window.matchMedia('(display-mode: standalone)').matches
  )
}

const refresh = () => {
  isFs.value = Boolean(doc.fullscreenElement || doc.webkitFullscreenElement)
}

const enterFs = async (): Promise<void> => {
  if (typeof docEl.requestFullscreen === 'function') {
    await docEl.requestFullscreen()
  } else if (typeof docEl.webkitRequestFullscreen === 'function') {
    await docEl.webkitRequestFullscreen()
  }
}

const exitFs = async (): Promise<void> => {
  if (typeof doc.exitFullscreen === 'function') {
    await doc.exitFullscreen()
  } else if (typeof doc.webkitExitFullscreen === 'function') {
    await doc.webkitExitFullscreen()
  }
}

const toggle = async () => {
  const goingFullscreen = !isFs.value
  try {
    if (isFs.value) {
      await exitFs()
    } else {
      await enterFs()
    }
    // Only persist on success — a rejected request shouldn't lock us into
    // an auto-retry loop on every page.
    writePref(goingFullscreen)
  } catch {
    /* user denied or transient — silently ignore */
  }
  refresh()
}

const icon = computed(() => (isFs.value ? '✕' : '⛶'))
const label = computed(() => (isFs.value ? 'Exit fullscreen' : 'Enter fullscreen'))

onMounted(() => {
  refresh()
  document.addEventListener('fullscreenchange', refresh)
  document.addEventListener('webkitfullscreenchange', refresh)

  // Re-enter fullscreen across SPA route changes when the user has
  // previously opted in. The spec requires a user gesture; outside of
  // one (e.g. a router-driven mount) the promise will reject and we
  // silently fall back to the toggle button.
  if (
    supported.value &&
    readPref() &&
    !doc.fullscreenElement &&
    !doc.webkitFullscreenElement &&
    !isStandaloneOrManifestFullscreen()
  ) {
    enterFs().catch(() => {
      /* expected: requestFullscreen without a fresh user gesture rejects */
    }).finally(refresh)
  }
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', refresh)
  document.removeEventListener('webkitfullscreenchange', refresh)
})
</script>

<template>
  <button
    v-if="supported"
    class="fs-toggle"
    type="button"
    :aria-label="label"
    :title="label"
    @click="toggle"
  >
    {{ icon }}
  </button>
</template>

<style scoped>
.fs-toggle {
  position: fixed;
  top: calc(env(safe-area-inset-top, 0px) + 6px);
  right: calc(env(safe-area-inset-right, 0px) + 6px);
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid rgba(124, 197, 255, 0.35);
  background: rgba(13, 13, 18, 0.75);
  color: #7cc5ff;
  font-size: 18px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  z-index: 9999;
  -webkit-tap-highlight-color: transparent;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
  transition: background-color 120ms ease, transform 120ms ease, opacity 120ms ease;
}

.fs-toggle:hover {
  background: rgba(20, 22, 30, 0.85);
}

.fs-toggle:active {
  transform: scale(0.94);
  background: rgba(124, 197, 255, 0.18);
}
</style>

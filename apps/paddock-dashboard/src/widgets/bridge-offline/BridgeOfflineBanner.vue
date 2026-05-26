<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { API_BASE } from '@/shared/config/api'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'
import CyberTag from '@/shared/ui/core/CyberTag.vue'
import HintBar from '@/widgets/hint-bar/HintBar.vue'

const bridge = useBridgeStore()
const audio = useAudioStore()

const state = ref<'silent' | 'banner' | 'expanded'>('silent')
const isReconnected = ref(false)

// Drive a re-render so "Xs ago" stays current while the panel is open.
const nowTick = ref(Date.now())
let _tickId: number | null = null
onMounted(() => {
  _tickId = window.setInterval(() => { nowTick.value = Date.now() }, 1000)
})
onBeforeUnmount(() => {
  if (_tickId !== null) clearInterval(_tickId)
})

const lastOkLabel = computed(() => {
  const ts = bridge.healthFetchedAt
  if (!ts) return '—'
  const deltaMs = Math.max(0, nowTick.value - ts)
  const s = Math.floor(deltaMs / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return `${h}h ago`
})

watch(() => bridge.consecutiveFailures, (n, old) => {
  if (n >= 3 && state.value === 'silent') {
    state.value = 'banner'
    audio.playSfx('error_quiet') // once, not repeated
  } else if (n === 0 && (old !== undefined && old > 0) && state.value !== 'silent') {
    // Recovering
    isReconnected.value = true
    audio.playSfx('goal_complete')
    setTimeout(() => {
      isReconnected.value = false
      state.value = 'silent'
    }, 1500)
  }
})

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'O' && e.shiftKey) {
    // Dev mock toggle
    bridge.toggleMockOffline()
    return
  }
  
  if (state.value === 'expanded') {
    e.stopPropagation() // Prevent other screens from handling keys while modal is open
    e.preventDefault()
    
    if (e.key === 'Enter' || e.key === 'a') {
      audio.playSfx('cursor_select')
      bridge.pollHealth() // immediate retry
    } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
      audio.playSfx('cancel')
      state.value = 'banner'
    } else if (e.key === 'c' || e.key === 'C') {
      // copy diag
      navigator.clipboard.writeText(JSON.stringify({ 
        url: API_BASE, 
        error: bridge.healthError,
        retries: bridge.consecutiveFailures
      }, null, 2))
      audio.playSfx('cursor_select')
    }
  }
})
</script>

<template>
  <Teleport to="body">
    <!-- Banner State -->
    <div v-if="state === 'banner' && !isReconnected" 
         class="fixed top-0 left-0 w-full h-[clamp(24px,4vmin,36px)] bg-ui-bad z-50 flex items-center px-2 cursor-pointer font-ui text-body justify-between text-white border-b border-charcoal shadow-md"
         @click="state = 'expanded'; audio.playSfx('cursor_select')">
      <div class="flex items-center gap-2">
        <span class="animate-spin text-ink leading-none">⚙</span>
        <span class="font-bold">BRIDGE OFFLINE — RECONNECTING…</span>
      </div>
      <span class="text-silver animate-pulse">⚠ tap for details</span>
    </div>

    <!-- Reconnected Flash -->
    <div v-if="isReconnected" 
         class="fixed top-0 left-0 w-full h-[clamp(24px,4vmin,36px)] bg-ui-good z-50 flex items-center px-2 font-ui text-body justify-center text-ink border-b border-charcoal shadow-md transition-all">
      <span class="font-bold">BRIDGE RECONNECTED</span>
    </div>

    <!-- Expanded State Modal -->
    <div v-if="state === 'expanded'" class="fixed inset-0 bg-black/80 z-[100] flex items-center justify-center font-ui text-silver">
      <CyberBox variant="ink" class="w-[min(480px,90vw)] max-h-[80vh] shadow-xl flex flex-col pt-4 pixelated overflow-y-auto">
        
        <h1 class="text-title text-silver font-bold px-4 mb-2">BRIDGE DIAGNOSTIC</h1>
        <div class="h-[1px] bg-slate mx-4 mb-4"></div>
        
        <div class="px-4 flex gap-4">
          <!-- Status Block (plain, no coach quote — pause is a UI affordance, not a coach moment) -->
          <CyberPanel class="p-2 w-1/3 text-body bg-charcoal">
            <div class="font-bold text-ui-warn mb-1">STATUS</div>
            <div class="text-silver">Bridge unreachable. Reconnecting…</div>
          </CyberPanel>

          <!-- Data Block -->
          <CyberPanel class="p-2 flex-grow text-body border-ui-bad border">
            <table class="w-full text-left">
              <tr><td class="text-slate font-bold w-1/3 pb-1">URL</td><td class="text-white pb-1">{{ API_BASE }}</td></tr>
              <tr><td class="text-slate font-bold pb-1">LAST OK</td><td class="text-white pb-1">{{ lastOkLabel }}</td></tr>
              <tr><td class="text-slate font-bold align-top pb-1">ERROR</td><td class="text-ui-warn break-all pb-1">{{ bridge.healthError || 'Unknown' }}</td></tr>
              <tr><td class="text-slate font-bold">RETRIES</td><td class="text-white">{{ bridge.consecutiveFailures }} (every 5 s)</td></tr>
            </table>
          </CyberPanel>
        </div>
        
        <div class="px-4 mt-4 text-body">
          <h2 class="font-bold text-white mb-2">TROUBLESHOOTING</h2>
          <ul class="flex flex-col gap-2">
            <li class="flex flex-col">
              <span class="text-ui-info font-bold flex items-center gap-1"><span class="text-ui-good">▶</span> Is the bridge running?</span>
              <CyberTag class="ml-3 mt-1 w-max">python3 -m pitwall</CyberTag>
            </li>
            <li class="flex flex-col mt-2">
              <span class="text-ui-info font-bold flex items-center gap-1"><span class="text-ui-good">▶</span> Is the port forwarded?</span>
              <span class="text-slate ml-3 mt-1">If running on Android, check <CyberTag>adb reverse tcp:8765 tcp:8765</CyberTag></span>
            </li>
          </ul>
        </div>
        
        <div class="absolute bottom-0 w-full">
          <HintBar :hints="['A · RETRY NOW', 'C · COPY DIAG', 'B · BACK']" />
        </div>
      </CyberBox>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * SETTINGS — tabbed layout for Pixel 10 landscape.
 *
 * Four tabs: DISPLAY · AUDIO · CONTROLS · DATA. The previous flat
 * stacked layout (5 tabs: AUDIO/DISPLAY/CONTROLS/CAR/DRIVER) folded
 * driver/car identity into the trainer-card / car-setup pages where
 * they belong; here we keep the system-side knobs.
 *
 * Keyboard 1-4 switches tabs. ESC backs out via router. Settings
 * mutate the save store (real persistence) with a 500ms debounce.
 * The DATA tab surfaces bridge URL + health honestly — there is no
 * cache-clear endpoint on the bridge, so the button only clears
 * local PWA caches.
 */
import { ref, computed, watch } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { API_BASE } from '@/shared/config/api'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberCheckbox from '@/shared/ui/core/CyberCheckbox.vue'
import CyberValuePicker from '@/shared/ui/core/CyberValuePicker.vue'
import CyberProgressBar from '@/shared/ui/core/CyberProgressBar.vue'
import CyberConfirmDialog from '@/shared/ui/core/CyberConfirmDialog.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const bridgeStore = useBridgeStore()

const TAB_LABELS = ['DISPLAY', 'AUDIO', 'CONTROLS', 'DATA'] as const
const activeTab = ref(0)

const slot = save.activeSlot
const savedSettings = slot?.settings

const settings = ref({
  audio: {
    master: savedSettings?.audio.masterVolume ?? 80,
    music: savedSettings?.audio.musicVolume ?? 50,
    sfx: savedSettings?.audio.sfxVolume ?? 100,
    coach: savedSettings?.audio.voiceVolume ?? 100,
    muteAll: false,
    muteCoach: savedSettings?.audio.coachMute ?? false,
  },
  display: {
    reducedMotion: savedSettings?.display.reducedMotion ?? false,
    nightMode: savedSettings?.display.nightMode ?? false,
    fpsCounter: savedSettings?.display.showFps ?? false,
    scale: 'Auto' as 'Auto' | '1x' | '2x' | '3x' | '4x' | '5x',
  },
  controls: {
    layout: (savedSettings?.controls.keyboardLayout === 'wasd' ? 'WASD'
           : savedSettings?.controls.keyboardLayout === 'igdk' ? 'IJKL'
           : 'Arrows') as 'Arrows' | 'WASD' | 'IJKL',
    swapAB: savedSettings?.controls.swapAB ?? false,
    touchGestures: true,
  },
})

let syncTimeout: number | null = null
watch(settings, () => {
  if (!save.activeSlotId) return
  const s = save.slots[save.activeSlotId - 1]
  if (!s) return

  const layoutMap: Record<string, 'arrows' | 'wasd' | 'igdk'> = {
    Arrows: 'arrows', WASD: 'wasd', IJKL: 'igdk',
  }

  s.settings = {
    audio: {
      masterVolume: settings.value.audio.master,
      musicVolume: settings.value.audio.music,
      sfxVolume: settings.value.audio.sfx,
      voiceVolume: settings.value.audio.coach,
      coachMute: settings.value.audio.muteCoach,
    },
    display: {
      nightMode: settings.value.display.nightMode,
      reducedMotion: settings.value.display.reducedMotion,
      showFps: settings.value.display.fpsCounter,
    },
    controls: {
      keyboardLayout: layoutMap[settings.value.controls.layout] ?? 'arrows',
      swapAB: settings.value.controls.swapAB,
    },
  }

  if (syncTimeout) clearTimeout(syncTimeout)
  syncTimeout = window.setTimeout(() => save.save(), 500)
}, { deep: true })

const confirmingDestructive = ref(false)

const bridgeOk = computed(() => bridgeStore.health !== null && bridgeStore.healthError === null)
const bridgeUrl = API_BASE
const sessionCount = computed(() => save.activeSlot ? 1 : 0)

const requestFullscreen = async () => {
  audio.playSfx('cursor_select')
  const el = document.documentElement as HTMLElement & {
    webkitRequestFullscreen?: () => Promise<void>
  }
  try {
    if (el.requestFullscreen) await el.requestFullscreen()
    else if (el.webkitRequestFullscreen) await el.webkitRequestFullscreen()
  } catch { /* user-cancelled or unsupported */ }
}

const testSfx = () => {
  audio.playSfx('goal_complete')
}

const clearLocalCache = async () => {
  audio.playSfx('cancel')
  // Clears browser caches — bridge has no cache-clear endpoint.
  if ('caches' in window) {
    const keys = await caches.keys()
    await Promise.all(keys.map(k => caches.delete(k)))
  }
  try { localStorage.clear() } catch { /* private mode */ }
}

const cycleScale = (dir: number) => {
  const scales: Array<typeof settings.value.display.scale> =
    ['Auto', '1x', '2x', '3x', '4x', '5x']
  const cur = scales.indexOf(settings.value.display.scale)
  const next = Math.max(0, Math.min(scales.length - 1, cur + dir))
  settings.value.display.scale = scales[next]
  audio.playSfx('cursor_move')
}

const cycleLayout = (dir: number) => {
  const layouts: Array<typeof settings.value.controls.layout> = ['Arrows', 'WASD', 'IJKL']
  const cur = layouts.indexOf(settings.value.controls.layout)
  const next = (cur + dir + layouts.length) % layouts.length
  settings.value.controls.layout = layouts[next]
  audio.playSfx('cursor_move')
}

useKeyboard((e: KeyboardEvent) => {
  if (confirmingDestructive.value) {
    if (e.key === 'y' || e.key === 'Y' || e.key === 'Enter') {
      audio.playSfx('cancel')
      if (save.activeSlotId) save.deleteSlot(save.activeSlotId)
      router.push('/')
    } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'n' || e.key === 'N') {
      confirmingDestructive.value = false
      audio.playSfx('cursor_move')
    }
    return
  }

  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }
  if (e.key === '4') { audio.playSfx('cursor_move'); activeTab.value = 3; return }

  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  }
})
</script>

<template>
  <PageShell
    title="SETTINGS"
    :hints="['1-4 · TAB', 'B · BACK']"
    bg="neutral"
    :show-heading="false"
  >
    <div class="settings-root flex flex-col h-full w-full gap-[1vmin]">

      <CyberTabs
        v-model="activeTab"
        :tabs="[...TAB_LABELS]"
        class="mx-2 shrink-0"
      />

      <div class="flex-1 min-h-0 mx-2 overflow-hidden">

        <!-- DISPLAY -->
        <CyberPanel v-show="activeTab === 0" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            VISUAL
          </div>
          <CyberCheckbox
            label="REDUCED MOTION"
            sub-label="DISABLES SCANLINES, STAGGER, AND PULSE EFFECTS"
            :checked="settings.display.reducedMotion"
            :focused="false"
            @change="(v: boolean) => { settings.display.reducedMotion = v; audio.playSfx('cursor_select') }"
          />
          <CyberCheckbox
            label="NIGHT MODE"
            sub-label="DARKER PALETTE FOR NIGHT DRIVING"
            :checked="settings.display.nightMode"
            :focused="false"
            @change="(v: boolean) => { settings.display.nightMode = v; audio.playSfx('cursor_select') }"
          />
          <CyberCheckbox
            label="SHOW FPS COUNTER"
            :checked="settings.display.fpsCounter"
            :focused="false"
            @change="(v: boolean) => { settings.display.fpsCounter = v; audio.playSfx('cursor_select') }"
          />

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            SCALE
          </div>
          <div class="flex items-center gap-3">
            <CyberValuePicker
              label="UI SCALE"
              :value="settings.display.scale"
              :focused="false"
              :editing="true"
              label-width="clamp(70px,18vw,140px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2" @click="cycleScale(-1)">◀</CyberBox>
            <CyberBox interactive class="p-2" @click="cycleScale(1)">▶</CyberBox>
          </div>

          <div class="mt-[1vmin] shrink-0">
            <CyberBox interactive class="p-2 w-max" @click="requestFullscreen">
              REQUEST FULLSCREEN
            </CyberBox>
          </div>
        </CyberPanel>

        <!-- AUDIO -->
        <CyberPanel v-show="activeTab === 1" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            VOLUMES
          </div>
          <CyberProgressBar
            label="MASTER"
            :value="settings.audio.master"
            :focused="false"
            :editing="true"
            @click="settings.audio.master = (settings.audio.master + 10) % 110; audio.playSfx('cursor_move')"
          />
          <CyberProgressBar
            label="MUSIC"
            :value="settings.audio.music"
            :focused="false"
            :editing="true"
            @click="settings.audio.music = (settings.audio.music + 10) % 110; audio.playSfx('cursor_move')"
          />
          <CyberProgressBar
            label="SFX"
            :value="settings.audio.sfx"
            :focused="false"
            :editing="true"
            @click="settings.audio.sfx = (settings.audio.sfx + 10) % 110; audio.playSfx('cursor_move')"
          />
          <CyberProgressBar
            label="COACH VOICE"
            :value="settings.audio.coach"
            :focused="false"
            :editing="true"
            @click="settings.audio.coach = (settings.audio.coach + 10) % 110; audio.playSfx('cursor_move')"
          />

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            MUTE
          </div>
          <CyberCheckbox
            label="MUTE ALL"
            :checked="settings.audio.muteAll"
            :focused="false"
            @change="(v: boolean) => { settings.audio.muteAll = v; audio.playSfx('cursor_select') }"
          />
          <CyberCheckbox
            label="MUTE COACH VOICE"
            sub-label="(SILENCE MODE)"
            :checked="settings.audio.muteCoach"
            :focused="false"
            @change="(v: boolean) => { settings.audio.muteCoach = v; audio.playSfx('cursor_select') }"
          />

          <div class="mt-[1vmin] shrink-0">
            <CyberBox interactive class="p-2 w-max" @click="testSfx">
              TEST SFX
            </CyberBox>
          </div>
        </CyberPanel>

        <!-- CONTROLS -->
        <CyberPanel v-show="activeTab === 2" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            KEYBOARD
          </div>
          <div class="flex items-center gap-3">
            <CyberValuePicker
              label="LAYOUT"
              :value="settings.controls.layout"
              :focused="false"
              :editing="true"
              label-width="clamp(70px,18vw,140px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2" @click="cycleLayout(-1)">◀</CyberBox>
            <CyberBox interactive class="p-2" @click="cycleLayout(1)">▶</CyberBox>
          </div>
          <CyberCheckbox
            label="SWAP A/B (LEFT-HANDED)"
            :checked="settings.controls.swapAB"
            :focused="false"
            @change="(v: boolean) => { settings.controls.swapAB = v; audio.playSfx('cursor_select') }"
          />

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            TOUCH
          </div>
          <CyberCheckbox
            label="TOUCH GESTURES (SWIPE)"
            sub-label="ENABLE SWIPE-TO-TAB NAVIGATION"
            :checked="settings.controls.touchGestures"
            :focused="false"
            @change="(v: boolean) => { settings.controls.touchGestures = v; audio.playSfx('cursor_select') }"
          />

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            KEYBINDS (READ-ONLY)
          </div>
          <div class="font-mono text-small text-silver/90 grid grid-cols-2 gap-x-6 gap-y-1">
            <span><span class="text-ui-good">A / Enter</span> · select</span>
            <span><span class="text-ui-good">B / Esc</span> · back</span>
            <span><span class="text-ui-good">1-N</span> · switch tab</span>
            <span><span class="text-ui-good">◀ ▶ ▲ ▼</span> · navigate</span>
            <span><span class="text-ui-good">S</span> · start session</span>
            <span><span class="text-ui-good">W</span> · track walk</span>
          </div>
        </CyberPanel>

        <!-- DATA -->
        <CyberPanel v-show="activeTab === 3" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            BRIDGE
          </div>
          <div class="font-mono text-small text-silver/90 flex flex-col gap-1">
            <div>
              <span class="text-slate uppercase tracking-widest mr-2">URL</span>
              <span class="text-white">{{ bridgeUrl }}</span>
            </div>
            <div>
              <span class="text-slate uppercase tracking-widest mr-2">STATUS</span>
              <span :class="bridgeOk ? 'text-ui-good' : 'text-ui-bad'">
                {{ bridgeOk ? '✓ ONLINE' : '✗ OFFLINE' }}
              </span>
            </div>
            <div v-if="bridgeStore.health">
              <span class="text-slate uppercase tracking-widest mr-2">ENGINE</span>
              <span class="text-white">{{ bridgeStore.health.engine ?? '—' }}</span>
            </div>
            <div v-if="bridgeStore.healthError" class="text-ui-bad text-small">
              {{ bridgeStore.healthError }}
            </div>
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            SESSION STORAGE
          </div>
          <div class="font-mono text-small text-silver/90">
            <span class="text-slate uppercase tracking-widest mr-2">LOCAL SLOTS</span>
            <span class="text-white">{{ sessionCount }}</span>
            <span class="text-slate ml-2">(saved to IndexedDB on this device)</span>
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            CACHE
          </div>
          <div class="text-small text-slate uppercase tracking-widest leading-relaxed">
            BRIDGE HAS NO CACHE-CLEAR ENDPOINT. THIS CLEARS THE PWA'S OWN
            CACHESTORAGE AND LOCALSTORAGE.
          </div>
          <div class="flex gap-3 mt-[1vmin] shrink-0">
            <CyberBox interactive class="p-2 w-max" @click="clearLocalCache">
              CLEAR LOCAL CACHE
            </CyberBox>
            <CyberBox
              variant="charcoal"
              border="warn"
              interactive
              class="p-2 w-max text-ui-warn"
              @click="confirmingDestructive = true"
            >
              DELETE SAVE DATA
            </CyberBox>
          </div>
        </CyberPanel>

      </div>
    </div>

    <CyberConfirmDialog
      :open="confirmingDestructive"
      title="DELETE SAVE"
      message="This will permanently erase all your progress. Are you sure?"
      confirm-label="DELETE"
      cancel-label="KEEP"
      variant="danger"
      @confirm="audio.playSfx('cancel'); save.activeSlotId && save.deleteSlot(save.activeSlotId); router.push('/')"
      @cancel="confirmingDestructive = false; audio.playSfx('cursor_move')"
    />
  </PageShell>
</template>

<style scoped>
.settings-root {
  min-height: 0;
}
</style>

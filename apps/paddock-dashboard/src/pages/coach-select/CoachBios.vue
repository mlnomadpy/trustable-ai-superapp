<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import type { CoachPrefs } from '@/shared/types/save'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberValuePicker from '@/shared/ui/core/CyberValuePicker.vue'
import CyberCheckbox from '@/shared/ui/core/CyberCheckbox.vue'

const router = useRouter()
const audio = useAudioStore()
const save = useSaveStore()

const verbosityOptions = [
  { id: 'min', label: 'MINIMAL' },
  { id: 'std', label: 'STANDARD' },
  { id: 'max', label: 'MAXIMUM' }
] as const

const focusOptions = [
  { id: 'brake', label: 'BRAKING' },
  { id: 'line', label: 'RACING LINE' },
  { id: 'accel', label: 'THROTTLE' }
] as const

const toneOptions = [
  { id: 'aggro', label: 'AGGRESSIVE' },
  { id: 'supp', label: 'SUPPORTIVE' },
  { id: 'clin', label: 'CLINICAL' }
] as const

const DEFAULT_PREFS: CoachPrefs = {
  verbosity: 'std',
  focus: 'brake',
  tone: 'clin',
  autoMute: false,
}

// Hydrated from save.activeSlot?.coachPrefs on mount so the UI shows the
// persisted values rather than defaults on every visit.
const verbosity = ref<CoachPrefs['verbosity']>(DEFAULT_PREFS.verbosity)
const focus = ref<CoachPrefs['focus']>(DEFAULT_PREFS.focus)
const tone = ref<CoachPrefs['tone']>(DEFAULT_PREFS.tone)
const autoMute = ref<boolean>(DEFAULT_PREFS.autoMute)

onMounted(() => {
  const prefs = save.activeSlot?.coachPrefs
  if (prefs) {
    verbosity.value = prefs.verbosity ?? DEFAULT_PREFS.verbosity
    focus.value = prefs.focus ?? DEFAULT_PREFS.focus
    tone.value = prefs.tone ?? DEFAULT_PREFS.tone
    autoMute.value = prefs.autoMute ?? DEFAULT_PREFS.autoMute
  }
})

const cursorIndex = ref(0)
const totalFields = 5

const applyAndReturn = async () => {
  audio.playSfx('cursor_select')
  const slot = save.activeSlot
  if (slot) {
    slot.coachPrefs = {
      verbosity: verbosity.value,
      focus: focus.value,
      tone: tone.value,
      autoMute: autoMute.value,
    }
    try {
      await save.save()
    } catch (e) {
      // Don't block navigation on storage failure — surface in console.
      // eslint-disable-next-line no-console
      console.error('CoachBios: failed to persist coachPrefs', e)
    }
  }
  router.back()
}

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    cursorIndex.value = (cursorIndex.value + 1) % totalFields
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursorIndex.value = (cursorIndex.value - 1 + totalFields) % totalFields
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowLeft') {
    if (cursorIndex.value === 0) rotateValue(verbosity, verbosityOptions, -1)
    else if (cursorIndex.value === 1) rotateValue(focus, focusOptions, -1)
    else if (cursorIndex.value === 2) rotateValue(tone, toneOptions, -1)
  } else if (e.key === 'ArrowRight') {
    if (cursorIndex.value === 0) rotateValue(verbosity, verbosityOptions, 1)
    else if (cursorIndex.value === 1) rotateValue(focus, focusOptions, 1)
    else if (cursorIndex.value === 2) rotateValue(tone, toneOptions, 1)
  } else if (e.key === 'Enter' || e.key === 'a') {
    if (cursorIndex.value === 3) {
      autoMute.value = !autoMute.value
      audio.playSfx('cursor_select')
    } else if (cursorIndex.value === 4) {
      void applyAndReturn()
    }
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  }
})

const rotateValue = (
  model: { value: string },
  options: ReadonlyArray<{ id: string; label: string }>,
  dir: number,
) => {
  const currentIdx = options.findIndex(o => o.id === model.value)
  let nextIdx = currentIdx + dir
  if (nextIdx < 0) nextIdx = options.length - 1
  if (nextIdx >= options.length) nextIdx = 0
  model.value = options[nextIdx].id
  audio.playSfx('cursor_move')
}
</script>

<template>
  <PageShell title="COACH BIOS" :hints="['A · TOGGLE/APPLY', 'B · CANCEL', '▲ ▼ ◀ ▶ NAVIGATE']" bg="neutral">
    <!-- BIOS aesthetic wrapper -->
    <div class="bios-overlay absolute inset-0 z-0 pointer-events-none opacity-20 mix-blend-screen bg-[#0a2e1f]"></div>
    
    <template #heading>
      <div class="heading-block mb-[1.5vh]">
        <h1 class="text-title font-title text-bios-green tracking-[0.2em]">COACH BIOS v1.4.2</h1>
        <div class="heading-rule bg-bios-green h-[2px] w-full"></div>
      </div>
    </template>

    <CyberPanel class="flex-grow flex flex-col p-4 bg-ink/90 border-bios-green overflow-hidden mx-2 pb-6 text-bios-green font-mono bios-text shadow-[0_0_15px_rgba(74, 222, 128,0.3)]">
      
      <div class="mb-6 border-b border-bios-green/30 pb-2">
        <div>> INITIALIZING NEURAL LINK... OK</div>
        <div>> ESTABLISHING PARAMETERS FOR: <span class="font-bold text-white">{{ save.activeSlot?.preferredCoach?.toUpperCase() || 'UNKNOWN' }}</span></div>
      </div>

      <div class="flex flex-col gap-4 pl-4">
        <div class="flex items-center p-1 cursor-pointer" :class="{ 'bg-bios-green/20 text-white': cursorIndex === 0 }" @click="cursorIndex = 0; rotateValue(verbosity, verbosityOptions, 1)">
          <CyberValuePicker 
            label="VERBOSITY"
            :value="verbosityOptions.find(o => o.id === verbosity)?.label || ''"
            :focused="cursorIndex === 0"
            :editing="true"
            class="flex-grow pointer-events-none"
          />
        </div>

        <div class="flex items-center p-1 cursor-pointer" :class="{ 'bg-bios-green/20 text-white': cursorIndex === 1 }" @click="cursorIndex = 1; rotateValue(focus, focusOptions, 1)">
          <CyberValuePicker 
            label="FOCUS PRIORITY"
            :value="focusOptions.find(o => o.id === focus)?.label || ''"
            :focused="cursorIndex === 1"
            :editing="true"
            class="flex-grow pointer-events-none"
          />
        </div>

        <div class="flex items-center p-1 cursor-pointer" :class="{ 'bg-bios-green/20 text-white': cursorIndex === 2 }" @click="cursorIndex = 2; rotateValue(tone, toneOptions, 1)">
          <CyberValuePicker 
            label="COACH TONE"
            :value="toneOptions.find(o => o.id === tone)?.label || ''"
            :focused="cursorIndex === 2"
            :editing="true"
            class="flex-grow pointer-events-none"
          />
        </div>

        <div class="flex items-center mt-4 p-1 cursor-pointer" :class="{ 'bg-bios-green/20 text-white': cursorIndex === 3 }" @click="cursorIndex = 3; autoMute = !autoMute; audio.playSfx('cursor_select')">
          <CyberCheckbox 
            label="AUTO-MUTE ON HOT LAPS" 
            :checked="autoMute" 
            :focused="cursorIndex === 3"
          />
        </div>

        <div class="flex items-center mt-6 p-2 border-t border-bios-green/30 cursor-pointer" :class="{ 'bg-bios-green/20 text-white': cursorIndex === 4 }" @click="cursorIndex = 4; applyAndReturn()">
          <span class="w-6 shrink-0 font-bold text-center" v-if="cursorIndex === 4">▶</span>
          <span class="w-6 shrink-0" v-else></span>
          <span class="font-bold cursor-pointer uppercase tracking-widest text-title-sm">APPLY & REBOOT</span>
        </div>
      </div>
    </CyberPanel>
  </PageShell>
</template>

<style scoped>
.bios-text {
  text-shadow: 0 0 2px rgba(74, 222, 128, 0.8);
}
</style>

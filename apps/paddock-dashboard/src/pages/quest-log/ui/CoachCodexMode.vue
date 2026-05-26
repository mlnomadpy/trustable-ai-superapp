<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'

import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { bridge } from '@/shared/api/bridge'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberSplitView from '@/shared/ui/core/CyberSplitView.vue'
import Sprite from '@/entities/coach/Sprite.vue'

const props = defineProps<{
  active: boolean
}>()

const emit = defineEmits<{
  (e: 'play', phrase: any): void
}>()


const audio = useAudioStore()

const coaches = [
  { id: 'trod', name: 'T-ROD', tab: 'T-RD' },
  { id: 'bentley', name: 'BENTLEY', tab: 'BNTLY' },
  { id: 'drill', name: 'DRILL', tab: 'DRILL' },
  { id: 'calm', name: 'CALM', tab: 'CALM' },
  { id: 'buddy', name: 'BUDDY', tab: 'BUDDY' }
]

const activeCoachIndex = ref(0)
const activeCoach = computed(() => coaches[activeCoachIndex.value])

interface Concept {
  id: string
  key: string
  text: string
  /** Emotion glyph — only set when /coach/concepts ships one. */
  emotion: string | null
  unlocked: boolean
}

// Phrases populated from backend. Empty until the fetch lands; on
// failure we surface `phrasesError` instead of shipping a hardcoded
// catalogue of Bentley pedagogy strings that may not match what the
// active coach actually knows.
const phrases = ref<Concept[]>([])
const phrasesLoading = ref(true)
const phrasesError = ref<string | null>(null)

onMounted(async () => {
  phrasesLoading.value = true
  phrasesError.value = null
  try {
    const res = await bridge.get<{ concepts: { id: string; description: string; fires_when: string; emotion?: string }[] }>('/coach/concepts')
    phrases.value = (res.concepts ?? []).map((c) => ({
      id: c.id,
      key: c.id,
      text: c.description,
      // Only render the emotion glyph when the bridge actually ships one
      // on the concept. The previous `i % 3` synthesis was unrelated to
      // the concept's pedagogy — drop it entirely when absent.
      emotion: typeof c.emotion === 'string' && c.emotion.trim() ? c.emotion : null,
      unlocked: true,
    }))
  } catch (e: any) {
    phrasesError.value = e?.message ?? String(e)
    phrases.value = []
  } finally {
    phrasesLoading.value = false
  }
})

const cursorIndex = ref(0)

useKeyboard((e: KeyboardEvent) => {
  if (!props.active) return

  if (e.key === 'ArrowRight') {
    if (e.shiftKey) {
      activeCoachIndex.value = (activeCoachIndex.value + 1) % coaches.length
      cursorIndex.value = 0
      audio.playSfx('cursor_select')
    }
  } else if (e.key === 'ArrowLeft') {
    if (e.shiftKey) {
      activeCoachIndex.value = (activeCoachIndex.value - 1 + coaches.length) % coaches.length
      cursorIndex.value = 0
      audio.playSfx('cursor_select')
    }
  } else if (e.key === 'ArrowDown') {
    if (!e.shiftKey) {
      cursorIndex.value = (cursorIndex.value + 1) % phrases.value.length
      audio.playSfx('cursor_move')
      // auto scroll logic would normally go here if not native
      const el = document.getElementById(`phrase-${cursorIndex.value}`)
      el?.scrollIntoView({ block: 'nearest' })
    }
  } else if (e.key === 'ArrowUp') {
    if (!e.shiftKey) {
      cursorIndex.value = (cursorIndex.value - 1 + phrases.value.length) % phrases.value.length
      audio.playSfx('cursor_move')
      const el = document.getElementById(`phrase-${cursorIndex.value}`)
      el?.scrollIntoView({ block: 'nearest' })
    }
  } else if (e.key === 'Enter' || e.key === 'a') {
    const p = phrases.value[cursorIndex.value]
    if (p.unlocked) {
      audio.playSfx('cursor_select')
      emit('play', { coachId: activeCoach.value.id, text: p.text })
    } else {
      audio.playSfx('cancel')
    }
  }
})

</script>

<template>
  <CyberSplitView split="40-60" gap="sm" class="h-full" v-if="active">
    
    <!-- Left Column: Coach Portrait and Stats -->
    <template #left>
      <div class="flex flex-col h-full gap-4">
        <CyberTabs :tabs="coaches.map(c => c.tab)" v-model="activeCoachIndex" class="flex-shrink-0" />
        
        <CyberPanel variant="solid" border="secondary" class="flex-1 flex flex-col justify-center items-center overflow-hidden relative p-0 bg-ink">
          <!-- Big Sprite Portrait -->
          <div class="flex-1 flex items-center justify-center w-full relative">
            <Sprite :sheet="activeCoach.id" animation="idle" class="scale-[2] origin-bottom drop-shadow-[4px_4px_0_#000]" />
          </div>
          
          <div class="w-full bg-charcoal border-t border-slate p-3 text-center z-10">
            <h2 class="text-[clamp(16px,4vmin,24px)] text-silver tracking-[0.2em] font-bold">{{ activeCoach.name }}</h2>
            <div class="text-small text-ui-good mt-1 font-bold">{{ phrases.length }} CONCEPTS LOADED</div>
          </div>
        </CyberPanel>
      </div>
    </template>

    <!-- Right Column: Phrase List -->
    <template #right>
      <CyberPanel variant="glass" border="secondary" class="flex flex-col h-full overflow-hidden p-3 min-h-0">
        <div class="flex justify-between items-end mb-3 border-b border-slate pb-2 flex-shrink-0">
          <h2 class="text-title text-silver tracking-[0.1em] text-[clamp(12px,3vmin,20px)] m-0">AUDIO LOGS</h2>
        </div>
        
        <div v-if="phrasesLoading" class="text-small text-slate tracking-widest uppercase py-4 px-2">
          LOADING CONCEPTS…
        </div>
        <div v-else-if="phrasesError" class="text-small text-ui-bad tracking-widest uppercase py-4 px-2">
          <div class="font-bold mb-1">CONCEPTS UNAVAILABLE</div>
          <div class="text-ui-bad/80 normal-case tracking-normal">{{ phrasesError }}</div>
        </div>
        <div v-else-if="phrases.length === 0" class="text-small text-slate tracking-widest uppercase py-4 px-2">
          — NO CONCEPTS REGISTERED ON BRIDGE —
        </div>
        <div v-else class="overflow-y-auto flex-grow flex flex-col gap-1 pr-2 min-h-0 h-full" id="phrase-list">
          <div
            v-for="(p, i) in phrases"
            :key="p.id"
            class="flex items-center text-body py-[6px] px-2 border border-transparent"
            :class="[
              cursorIndex === i ? 'bg-charcoal border-slate text-white' : 'text-silver',
              !p.unlocked ? 'opacity-50 text-slate' : ''
            ]"
            :id="`phrase-${i}`"
          >
            <span class="w-4 flex-shrink-0 text-ui-good" v-if="cursorIndex === i">▶</span>
            <span class="w-4 flex-shrink-0" v-else></span>
            
            <span class="w-4 flex-shrink-0 text-ui-good" v-if="p.unlocked">✓</span>
            <span class="w-4 flex-shrink-0 text-charcoal-light" v-else>▒</span>

            <span class="w-4 flex-shrink-0 text-ui-info mr-1" v-if="p.unlocked && p.emotion">{{ p.emotion }}</span>
            <span class="w-4 flex-shrink-0 text-slate mr-1" v-else-if="!p.unlocked">??</span>
            <span class="w-4 flex-shrink-0 mr-1" v-else></span>

            <span class="w-[clamp(80px,20vw,160px)] flex-shrink-0 font-mono text-[clamp(10px,2vmin,14px)]">{{ p.unlocked ? p.key : '???' }}</span>
            <span class="truncate ml-2 italic text-[clamp(10px,2vmin,14px)]">"{{ p.unlocked ? p.text : '──────' }}"</span>
          </div>
        </div>
      </CyberPanel>
    </template>
    
  </CyberSplitView>
</template>

<style scoped>
/* Hide scrollbar */
::-webkit-scrollbar {
  display: none;
}
</style>

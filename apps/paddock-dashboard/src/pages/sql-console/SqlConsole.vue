<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useDuckDBStore } from '@/shared/lib/duckdb/duckdbStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'
import Sprite from '@/entities/coach/Sprite.vue'

const router = useRouter()
const audio = useAudioStore()
const save = useSaveStore()
const session = useSessionStore()
const duckdb = useDuckDBStore()

const state = ref<'editor' | 'running' | 'result' | 'error' | 'examples'>('editor')

const editorText = ref(`-- Top 10 speeds in the session
SELECT distance_m, speed_ms * 3.6 AS speed_kmh,
       brake_bar, throttle_pct
FROM telemetry
ORDER BY speed_ms DESC LIMIT 10;`)

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const resultData = ref<any[] | null>(null)
const errorMsg = ref<string | null>(null)
const resultTime = ref('0.0')

const examples = [
  { title: 'Top Speeds', query: `-- Top 10 speeds in the session\nSELECT distance_m, speed_ms * 3.6 AS speed_kmh,\n       brake_bar, throttle_pct\nFROM telemetry\nORDER BY speed_ms DESC LIMIT 10;` },
  { title: 'Hard Braking Zones', query: `-- Find the hardest braking points\nSELECT distance_m, brake_bar, g_long, speed_ms * 3.6 as speed_kmh\nFROM telemetry\nWHERE brake_bar > 10 AND g_long < -1.0\nORDER BY brake_bar DESC\nLIMIT 10;` },
  { title: 'High G-Force Corners', query: `-- Find highest lateral G-forces\nSELECT distance_m, g_lat, speed_ms * 3.6 as speed_kmh, throttle_pct\nFROM telemetry\nWHERE abs(g_lat) > 1.2\nORDER BY abs(g_lat) DESC\nLIMIT 10;` }
]
const exampleIndex = ref(0)

const coachEmotion = computed(() => {
  if (state.value === 'running') return 'analyzing'
  if (state.value === 'error') return 'concerned'
  if (state.value === 'result') return 'encouraging'
  return 'intense'
})

const hints = computed(() => {
  if (state.value === 'editor') return ['◆ EXAMPLES', 'ENTER · RUN', 'ESC · BLUR']
  if (state.value === 'examples') return ['▲ ▼ SELECT', 'A · LOAD', 'B · CANCEL']
  return ['A · RUN', 'B · BACK', '◆ EXAMPLES']
})

const WRITE_KEYWORDS = /^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|COPY)\b/im

const runQuery = async () => {
  state.value = 'running'
  errorMsg.value = null
  resultData.value = null
  audio.playSfx('cursor_select')
  textareaRef.value?.blur()
  
  // Read-only guard — block write operations
  if (WRITE_KEYWORDS.test(editorText.value)) {
    state.value = 'error'
    errorMsg.value = 'WRITE OPERATIONS BLOCKED — SQL Console is read-only.\nOnly SELECT and WITH statements are permitted.'
    audio.playSfx('error_quiet')
    return
  }
  
  try {
    const t0 = performance.now()
    // No more 'demo-session' magic — queries require an actual session so
    // they target real data. Bail with a clear error otherwise.
    const sid = session.activeSessionId
    if (!sid) {
      state.value = 'error'
      errorMsg.value = 'NO ACTIVE SESSION — start or load a session before running SQL.'
      audio.playSfx('error_quiet')
      return
    }
    await duckdb.init()
    await duckdb.ensureSession(sid)

    // Execute read-only SQL
    const result = await duckdb.query(editorText.value)
    
    // DuckDB returns an Apache Arrow table; convert to JSON array
    resultData.value = result.toArray().map((r: any) => r.toJSON())
    const t1 = performance.now()
    resultTime.value = ((t1 - t0) / 1000).toFixed(2)
    state.value = 'result'
    audio.playSfx('goal_complete')
  } catch (err) {
    state.value = 'error'
    errorMsg.value = String(err)
    audio.playSfx('error_quiet')
  }
}

useKeyboard((e: KeyboardEvent) => {
  if (state.value === 'examples') {
    e.preventDefault()
    if (e.key === 'ArrowDown') {
      exampleIndex.value = (exampleIndex.value + 1) % examples.length
      audio.playSfx('cursor_move')
    } else if (e.key === 'ArrowUp') {
      exampleIndex.value = (exampleIndex.value - 1 + examples.length) % examples.length
      audio.playSfx('cursor_move')
    } else if (e.key === 'Enter' || e.key === 'a') {
      editorText.value = examples[exampleIndex.value].query
      state.value = 'editor'
      audio.playSfx('cursor_select')
      nextTick(() => textareaRef.value?.focus())
    } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
      state.value = 'editor'
      audio.playSfx('cancel')
      nextTick(() => textareaRef.value?.focus())
    }
    return
  }
  
  if (state.value === 'editor' && document.activeElement === textareaRef.value) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      runQuery()
    } else if (e.key === 'Escape') {
      textareaRef.value?.blur()
      // manually update state if they just hit escape to blur
      // let it stay 'editor' conceptually, but UI shows hints for blurred state
    } else if (e.key === 'Tab') {
      e.preventDefault() // prevent tabbing out
      const start = textareaRef.value!.selectionStart
      const end = textareaRef.value!.selectionEnd
      editorText.value = editorText.value.substring(0, start) + '  ' + editorText.value.substring(end)
      nextTick(() => {
        textareaRef.value!.selectionStart = textareaRef.value!.selectionEnd = start + 2
      })
    }
    return
  }

  // Not focused or not in editor state
  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  } else if (e.key === 'Enter' || e.key === 'a') {
    runQuery()
  } else if (e.key === 'Shift') {
    state.value = 'examples'
    audio.playSfx('cursor_select')
  }
})

const handleEditorClick = () => {
  if (state.value !== 'editor') {
    state.value = 'editor'
  }
}

onMounted(() => {
  nextTick(() => textareaRef.value?.focus())
})

</script>

<template>
  <PageShell title="SQL CONSOLE" :hints="hints" :statusExtra="`░ DUCKDB ${state === 'running' ? 'EXECUTING' : 'ON'}`">
    <div class="flex flex-col gap-2 flex-grow min-h-0 mx-2 pb-6 relative">
      
      <!-- Editor -->
      <CyberPanel variant="glass" :border="state === 'editor' ? 'primary' : 'secondary'" class="flex flex-col text-body p-2 relative h-[clamp(60px,15vh,120px)] shrink-0 transition-colors">
        <textarea
          ref="textareaRef"
          v-model="editorText"
          class="w-full h-full bg-transparent text-white font-mono resize-none focus:outline-none placeholder-slate/50 selection:bg-ui-good selection:text-ink leading-tight"
          spellcheck="false"
          @click="handleEditorClick"
          @focus="state = 'editor'"
        ></textarea>
      </CyberPanel>

      <!-- Toolbar -->
      <div class="flex gap-4 text-body font-bold mt-2">
        <CyberButton @click="runQuery" size="sm" variant="info">
          <template #icon>
            <span class="mr-1" :class="{'animate-spin': state === 'running'}">
              {{ state === 'running' ? '⚙' : '▶' }}
            </span>
          </template>
          {{ state === 'running' ? 'RUNNING' : 'RUN' }}
        </CyberButton>
        <CyberButton size="sm" variant="dark">☆ SAVE</CyberButton>
        <CyberButton size="sm" variant="dark">📂 LOAD</CyberButton>
        <CyberButton @click="editorText = ''" size="sm" variant="primary">🗑 CLEAR</CyberButton>
      </div>

      <!-- Result/Error Panel -->
      <CyberPanel v-if="state === 'result' || state === 'error' || state === 'running'" variant="glass" border="none" class="flex flex-col text-body p-2 flex-grow overflow-hidden relative">
        <div v-if="state === 'running'" class="absolute inset-0 flex items-center justify-center">
          <span class="animate-spin text-title-lg text-ui-good">⚙</span>
        </div>
        
        <template v-else-if="state === 'result' && resultData">
          <div class="text-slate mb-2 shrink-0">RESULT {{ resultData.length }} rows · {{ resultTime }} s</div>
          <div class="overflow-x-auto overflow-y-auto flex-grow w-full no-scrollbar">
            <table class="w-full text-left font-mono min-w-max">
              <thead>
                <tr class="text-ui-info border-b border-charcoal">
                  <th v-for="key in Object.keys(resultData[0])" :key="key" class="pb-1 pr-4 whitespace-nowrap">{{ key }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in resultData" :key="`row-${i}-${JSON.stringify(row)}`" class="text-silver hover:bg-charcoal/50 transition-colors">
                  <td v-for="key in Object.keys(row)" :key="key" class="pr-4 py-1 whitespace-nowrap">{{ row[key] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-else-if="state === 'error'">
          <div class="text-ui-warn font-bold mb-2">EXECUTION FAILED</div>
          <div class="font-mono text-ui-warn whitespace-pre-wrap">{{ errorMsg }}</div>
        </template>
      </CyberPanel>
      
      <!-- Examples Modal -->
      <div v-if="state === 'examples'" class="absolute inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
        <CyberPanel variant="solid" border="primary" class="w-full bg-ink p-2 text-body flex flex-col">
          <div class="text-ui-info font-bold mb-2 border-b border-charcoal pb-1">EXAMPLE QUERIES</div>
          <div class="flex flex-col gap-1">
            <div v-for="(ex, i) in examples" :key="ex.title"
                 class="px-2 py-1 flex justify-between items-center"
                 :class="exampleIndex === i ? 'bg-charcoal text-white font-bold' : 'text-slate'">
              <span>{{ exampleIndex === i ? '▶ ' : '' }}{{ ex.title }}</span>
            </div>
          </div>
        </CyberPanel>
      </div>

    </div>
    
    <template #floating>
      <!-- Coach -->
      <div class="absolute bottom-[6vh] right-2 flex flex-col items-end gap-1">
        <CyberBox variant="charcoal" border="slate" class="text-small px-2 py-1 text-slate">{{ save.activeSlot?.preferredCoach?.toUpperCase() ?? 'T-ROD' }}</CyberBox>
        <CyberBox variant="charcoal" border="slate" class="w-[clamp(36px,8vmin,64px)] h-[clamp(36px,8vmin,64px)] overflow-hidden relative">
           <!-- Coach Sprite -->
           <Sprite 
             :sheet="save.activeSlot?.preferredCoach ?? 'trod'" 
             :animation="coachEmotion" 
             class="absolute inset-0 m-auto" 
           />
        </CyberBox>
      </div>
    </template>
  </PageShell>
</template>

<style scoped>
/* No hardcoded viewport dimensions — fullscreen is enforced by global.css */
</style>

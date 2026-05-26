<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { bridge } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberSplitView from '@/shared/ui/core/CyberSplitView.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import TrackMap from '@/shared/ui/core/TrackMap.vue'

/**
 * Wired to /session/<sid>/straight_line_speed (bp_analysis.session_straight_line_speed).
 * Backend returns one row per named straight from sonoma.STRAIGHTS with the
 * top speed reached and the lap that recorded it. We compute deltas against
 * the FIRST straight in the session (proxy for "session #1") so the screen
 * shows real change since the start of the day rather than a hardcoded
 * benchmark.
 */
const router = useRouter()
const audio = useAudioStore()
const session = useSessionStore()

interface StraightRow {
  name: string
  start_m: number
  end_m: number
  top_speed_kmh: number | null
  from_lap: number | null
}

interface StraightDisplay {
  id: string
  name: string
  speed: number
  lap: number | null
  delta: string
  deltaType: 'up' | 'down' | 'flat' | 'none'
  note: string
}

const rows = ref<StraightRow[]>([])
const loading = ref(false)
// `pageError` surfaces fetch failures + missing-session in a prominent
// "STRAIGHTS UNAVAILABLE" panel (PreBrief.vue pattern), instead of the old
// tiny italic line that was easy to miss.
const pageError = ref<string | null>(null)
const cursorIndex = ref(0)

onMounted(async () => {
  const sid = session.activeSessionId ?? session.sessions[0]?.session_id
  if (!sid) {
    pageError.value = 'No active session — start or load a session to see straight-line speeds.'
    return
  }
  loading.value = true
  try {
    const res = await bridge.get<{ session_id: string; straights: StraightRow[] }>(
      `/session/${sid}/straight_line_speed`,
    )
    rows.value = Array.isArray(res?.straights) ? res.straights : []
  } catch (e: any) {
    pageError.value = e?.message ?? String(e)
    rows.value = []
  } finally {
    loading.value = false
  }
})

const straights = computed<StraightDisplay[]>(() => {
  // Compute delta against the first straight that produced a real top speed.
  // We keep the actual row reference (not just the speed value) so the
  // "is this the baseline?" check below uses real identity comparison —
  // the previous version did `r !== rows.value.find(x => x === r)`, which
  // is always false (find returns r itself), so every row showed as 'flat'
  // / 'baseline'. Audit fix 2026-05-13.
  const baselineRow = rows.value.find(r => r.top_speed_kmh != null) ?? null
  const baseline = baselineRow?.top_speed_kmh ?? null
  return rows.value.map((r) => {
    const speed = r.top_speed_kmh ?? 0
    let deltaType: StraightDisplay['deltaType'] = 'none'
    let deltaTxt = '—'
    if (r.top_speed_kmh == null) {
      // no data — leave deltaType='none', note explains why
    } else if (r === baselineRow) {
      deltaType = 'flat'
      deltaTxt = 'baseline'
    } else if (baseline != null) {
      const d = r.top_speed_kmh - baseline
      if (Math.abs(d) < 0.5) { deltaType = 'flat'; deltaTxt = '0.0' }
      else if (d > 0) { deltaType = 'up'; deltaTxt = `+${d.toFixed(1)}` }
      else { deltaType = 'down'; deltaTxt = d.toFixed(1) }
    }
    return {
      id: r.name.toLowerCase().replace(/\s+/g, '-'),
      name: r.name,
      speed,
      lap: r.from_lap,
      delta: deltaTxt,
      deltaType,
      note: r.top_speed_kmh == null ? '(no telemetry in this segment)' : '',
    }
  })
})

const cur = computed(() => straights.value[cursorIndex.value])

const getCoachLine = () => {
  if (!cur.value) return ''
  if (cur.value.deltaType === 'up') {
    return `You carried more speed on the ${cur.value.name} than the baseline run.`
  }
  if (cur.value.deltaType === 'down') {
    return `${cur.value.name} dropped ${Math.abs(parseFloat(cur.value.delta) || 0).toFixed(1)} km/h — usually a corner-exit problem one turn back.`
  }
  if (cur.value.deltaType === 'flat') {
    return `Flat on the ${cur.value.name}. Consistent — same speed as the baseline.`
  }
  return `No top speed recorded for the ${cur.value.name} yet.`
}

const getEmotion = () => {
  if (!cur.value) return 'idle'
  if (cur.value.deltaType === 'up') return 'victory'
  if (cur.value.deltaType === 'down') return 'talk'
  return 'idle'
}

useKeyboard((e: KeyboardEvent) => {
  const max = straights.value.length
  if (!max) return
  if (e.key === 'ArrowDown') {
    cursorIndex.value = Math.min(cursorIndex.value + 1, max - 1)
    audio.playSfx(straights.value[cursorIndex.value].deltaType === 'down' ? 'error_quiet' : 'cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursorIndex.value = Math.max(cursorIndex.value - 1, 0)
    audio.playSfx(straights.value[cursorIndex.value].deltaType === 'down' ? 'error_quiet' : 'cursor_move')
  } else if (e.key === 'Enter' || e.key === 'a') {
    audio.playSfx('cursor_select')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage/analysis')
  }
})
</script>

<template>
  <PageShell title="STRAIGHTS & SPEED" :hints="['A · OPEN REPLAY (SOON)', '▲ ▼ MOVE', 'B · BACK']" bg="cool">
    <CyberSplitView split="60-40" gap="sm" class="flex-grow min-h-0">
      <template #left>
        <CyberPanel class="h-full flex flex-col text-body p-2 gap-2">
          <div v-if="loading" class="text-small text-slate italic p-2">Loading straight-line stats...</div>
          <div v-else-if="pageError" class="m-2 p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">STRAIGHTS UNAVAILABLE</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ pageError }}</div>
          </div>
          <div v-else-if="!straights.length" class="text-small text-slate italic p-2">
            No telemetry on the named straights yet. Drive a flying lap to populate this view.
          </div>

          <div
            v-for="(s, i) in straights"
            :key="s.id"
            class="p-2 border transition-colors flex flex-col gap-1 cursor-pointer"
            :class="cursorIndex === i ? 'border-ui-good bg-charcoal' : 'border-slate bg-ink'"
            @click="cursorIndex = i; audio.playSfx('cursor_move')"
          >
            <div class="flex justify-between items-end">
              <div class="font-bold">
                <span v-if="cursorIndex === i" class="text-ui-good mr-1">▶</span>
                <span :class="cursorIndex === i ? 'text-white' : 'text-silver'">░░ {{ s.name }} ░░</span>
              </div>
              <div class="text-body text-silver">
                <span v-if="s.lap != null">LAP {{ s.lap }}</span>
                <span v-else class="text-slate/60">no lap</span>
              </div>
            </div>

            <div class="flex gap-4 items-center pl-4">
              <span class="text-title font-nums font-bold text-white">
                <span v-if="s.speed">{{ s.speed.toFixed(1) }}</span><span v-else class="text-slate/60">—</span>
                <span class="text-body text-slate ml-1">km/h</span>
              </span>

              <span
                class="text-body flex items-center gap-1 flex-shrink-0 ml-auto"
                :class="{
                  'text-ui-good': s.deltaType === 'up',
                  'text-ui-warn': s.deltaType === 'down',
                  'text-silver': s.deltaType === 'flat',
                  'text-slate/40': s.deltaType === 'none',
                }"
              >
                <span v-if="s.deltaType === 'up'">▲</span>
                <span v-else-if="s.deltaType === 'down'">▼</span>
                <span v-else-if="s.deltaType === 'flat'">=</span>
                <span v-else>—</span>
                {{ s.delta }}<span v-if="s.deltaType !== 'none' && s.deltaType !== 'flat'"> km/h vs baseline</span>
              </span>
            </div>

            <div v-if="s.note" class="text-body text-slate italic pl-4">{{ s.note }}</div>
          </div>
        </CyberPanel>
      </template>

      <template #right>
        <CyberPanel class="h-full relative flex items-center justify-center bg-[#1A252C] overflow-hidden p-0 border-b border-slate">
          <TrackMap class="absolute inset-[-10%] w-[120%] h-[120%] opacity-80" />
          <div class="absolute top-2 left-2 text-small text-silver font-bold z-10">TRACK MAP</div>
        </CyberPanel>
      </template>
    </CyberSplitView>

    <template #floating>
      <CoachFloat
        v-if="cur"
        :emotion="getEmotion()"
        :text="getCoachLine()"
        :key="cur.id"
      />
    </template>
  </PageShell>
</template>

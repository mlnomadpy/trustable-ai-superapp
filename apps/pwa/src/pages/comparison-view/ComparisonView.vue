<script setup lang="ts">
/**
 * Side-by-side session comparison.
 *
 * Honest data only: the bridge exposes per-session aggregates
 * (`/session/<sid>/pedal_behavior`, `/session/<sid>/sector_times`,
 * `/session/<sid>/lap_time_table`) but NOT scrubable per-frame telemetry
 * for two sessions in one go. The previous version generated sine waves
 * with `Math.sin() + Math.random()` and pretended they were lap shapes.
 * Removed.
 *
 * This view now compares two sessions on:
 *   • Best-lap time + delta
 *   • Pedal-state distribution (throttle / brake / trail / coast)
 *   • Per-sector times (S1 / S2 / S3 if Sonoma)
 *
 * Per-frame replay is a future feature — it'll land when we have a
 * `/session/<sid>/export.parquet` consumer that streams two sessions
 * into a client-side DuckDB-Wasm and renders synced charts.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { bridge } from '@/shared/api/bridge'
import { formatLapTime } from '@/shared/lib/lap'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'
import Sprite from '@/entities/coach/Sprite.vue'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const sessionStore = useSessionStore()

interface PedalStates {
  throttle_only: { pct: number; time_s: number }
  brake_only:    { pct: number; time_s: number }
  trail_brake:   { pct: number; time_s: number }
  coast:         { pct: number; time_s: number }
}
interface SectorRow { lap_number: number; s1: number; s2: number; s3: number }

interface Side {
  sid: string
  label: string
  bestLapS: number | null
  pedal: PedalStates | null
  sectors: SectorRow[]
  loading: boolean
  error: string | null
}

const left = ref<Side>(blankSide())
const right = ref<Side>(blankSide())

function blankSide(): Side {
  return {
    sid: '',
    label: '—',
    bestLapS: null,
    pedal: null,
    sectors: [],
    loading: false,
    error: null,
  }
}

// Session picker: which slot is the user editing (left / right / closed).
const activePicker = ref<'none' | 'left' | 'right'>('none')
const pickerIndex = ref(0)

const knownSessions = computed(() => sessionStore.sessions)

onMounted(async () => {
  // Initial selection: latest two sessions with best-lap data. Falls back
  // to a single session for both slots so the user can still drive the UI.
  await sessionStore.fetchSessions()
  const withBest = sessionStore.sessions.filter(s => s.best_lap_s != null)
  if (withBest.length >= 2) {
    selectSide('left', withBest[0].session_id)
    selectSide('right', withBest[1].session_id)
  } else if (withBest.length === 1) {
    selectSide('left', withBest[0].session_id)
  } else if (sessionStore.sessions.length) {
    selectSide('left', sessionStore.sessions[0].session_id)
  }
})

async function selectSide(which: 'left' | 'right', sid: string) {
  const target = which === 'left' ? left : right
  const summary = sessionStore.sessions.find(s => s.session_id === sid)
  target.value = {
    sid,
    label: summary ? formatLabel(summary) : sid,
    bestLapS: summary?.best_lap_s ?? null,
    pedal: null,
    sectors: [],
    loading: true,
    error: null,
  }
  try {
    const [pedal, sectorRes] = await Promise.all([
      bridge.get<{ states: PedalStates }>(`/session/${sid}/pedal_behavior`),
      bridge.get<{ laps: SectorRow[] }>(`/session/${sid}/sector_times`),
    ])
    target.value.pedal = pedal?.states ?? null
    target.value.sectors = Array.isArray(sectorRes?.laps) ? sectorRes.laps : []
  } catch (e: any) {
    target.value.error = e?.message ?? String(e)
  } finally {
    target.value.loading = false
  }
}

function formatLabel(s: { session_id: string; track: string; best_lap_s: number | null; started_at: string | null }): string {
  const t = s.started_at?.slice(0, 10) ?? s.session_id.slice(0, 10)
  // 1-decimal precision matches HUD / Stage Clear so the same lap reads
  // the same way across the app.
  const best = s.best_lap_s != null ? formatLapTime(s.best_lap_s, 1) : '—'
  return `${t} · ${s.track} · ${best}`
}

// ── Best-lap delta -----------------------------------------------------------

const deltaDisplay = computed(() => {
  const a = left.value.bestLapS
  const b = right.value.bestLapS
  if (a == null || b == null) return { text: '—', faster: null as 'L' | 'R' | null }
  const d = Math.abs(a - b).toFixed(3)
  return { text: `${d}s`, faster: a < b ? 'L' : 'R' as 'L' | 'R' }
})

// ── Pedal-state bar widths --------------------------------------------------

function statePct(side: Side, key: keyof PedalStates): number {
  return side.pedal?.[key]?.pct ?? 0
}

// ── Sector comparison (best of each side, per sector) -----------------------

const sectorCompare = computed(() => {
  const ls = bestSectors(left.value)
  const rs = bestSectors(right.value)
  return (['s1', 's2', 's3'] as const).map(k => ({
    name: k.toUpperCase(),
    leftBest: ls[k],
    rightBest: rs[k],
    delta: ls[k] != null && rs[k] != null ? ls[k]! - rs[k]! : null,
  }))
})

function bestSectors(side: Side): { s1: number | null; s2: number | null; s3: number | null } {
  if (!side.sectors.length) return { s1: null, s2: null, s3: null }
  const out = { s1: Infinity, s2: Infinity, s3: Infinity }
  for (const row of side.sectors) {
    if (row.s1 > 0 && row.s1 < out.s1) out.s1 = row.s1
    if (row.s2 > 0 && row.s2 < out.s2) out.s2 = row.s2
    if (row.s3 > 0 && row.s3 < out.s3) out.s3 = row.s3
  }
  return {
    s1: Number.isFinite(out.s1) ? out.s1 : null,
    s2: Number.isFinite(out.s2) ? out.s2 : null,
    s3: Number.isFinite(out.s3) ? out.s3 : null,
  }
}

// ── Keyboard handler --------------------------------------------------------

useKeyboard((e: KeyboardEvent) => {
  if (activePicker.value !== 'none') {
    const list = knownSessions.value
    if (!list.length) {
      if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
        activePicker.value = 'none'
      }
      return
    }
    if (e.key === 'ArrowDown') {
      pickerIndex.value = Math.min(list.length - 1, pickerIndex.value + 1)
      audio.playSfx('cursor_move')
    } else if (e.key === 'ArrowUp') {
      pickerIndex.value = Math.max(0, pickerIndex.value - 1)
      audio.playSfx('cursor_move')
    } else if (e.key === 'Enter' || e.key === 'a') {
      selectSide(activePicker.value, list[pickerIndex.value].session_id)
      audio.playSfx('cursor_select')
      activePicker.value = 'none'
    } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
      activePicker.value = 'none'
      audio.playSfx('cancel')
    }
    return
  }
  // (the new picker handler above is the only Math.random()-free entry point;
  // the legacy cursorPos scrub keys were retired with the synthetic curves.)
  if (e.key === 'l' || e.key === 'L') {
    activePicker.value = 'left'
    pickerIndex.value = 0
    audio.playSfx('cursor_select')
  } else if (e.key === 'r' || e.key === 'R') {
    activePicker.value = 'right'
    pickerIndex.value = 0
    audio.playSfx('cursor_select')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  }
})

watch(activePicker, (v) => { if (v !== 'none') pickerIndex.value = 0 })
</script>

<template>
  <PageShell title="COMPARE" :hints="['L · PICK LEFT', 'R · PICK RIGHT', 'B · BACK']" bg="cool" :show-heading="false">
    <div class="flex justify-between items-end border-b border-slate pb-1 mb-2 mx-2">
      <h1 class="text-title font-title text-silver tracking-[0.2em]">COMPARE</h1>
    </div>

    <!-- Side selectors -->
    <div class="px-2 mb-3 text-body flex flex-col gap-1">
      <div
        class="flex items-center gap-2 cursor-pointer"
        @click="activePicker = activePicker === 'left' ? 'none' : 'left'"
      >
        <span class="w-[clamp(24px,6vw,48px)] text-slate">LEFT</span>
        <span :class="activePicker === 'left' ? 'text-ui-info' : 'text-slate'">▼</span>
        <CyberPanel
          class="px-2 py-0.5 bg-ink flex-grow border"
          :class="activePicker === 'left' ? 'border-ui-good text-white' : 'border-slate text-silver'"
        >
          [ {{ left.label }} ]
        </CyberPanel>
      </div>
      <div
        class="flex items-center gap-2 cursor-pointer"
        @click="activePicker = activePicker === 'right' ? 'none' : 'right'"
      >
        <span class="w-[clamp(24px,6vw,48px)] text-slate">RIGHT</span>
        <span :class="activePicker === 'right' ? 'text-ui-info' : 'text-slate'">▼</span>
        <CyberPanel
          class="px-2 py-0.5 bg-ink flex-grow border"
          :class="activePicker === 'right' ? 'border-ui-good text-white' : 'border-slate text-silver'"
        >
          [ {{ right.label }} ]
        </CyberPanel>
      </div>
    </div>

    <!-- Inline picker list -->
    <CyberPanel
      v-if="activePicker !== 'none'"
      class="mx-2 mb-3 border-ui-info p-2 max-h-[28%] overflow-y-auto"
    >
      <div class="text-small text-slate mb-1 tracking-widest">
        SELECT SESSION FOR {{ activePicker.toUpperCase() }}
      </div>
      <div v-if="!knownSessions.length" class="text-small text-slate italic">
        No sessions loaded yet.
      </div>
      <div
        v-for="(s, i) in knownSessions"
        :key="s.session_id"
        class="text-small font-mono px-2 py-1 cursor-pointer"
        :class="pickerIndex === i ? 'bg-charcoal text-white' : 'text-silver'"
        @click="selectSide(activePicker as 'left' | 'right', s.session_id); activePicker = 'none'"
      >
        <span v-if="pickerIndex === i" class="text-ui-good mr-1">▶</span>
        {{ formatLabel(s) }}
      </div>
    </CyberPanel>

    <!-- Best-lap delta -->
    <div class="px-2 mb-3 text-body flex items-center gap-2 font-bold">
      <span class="text-slate font-normal">BEST-LAP Δ</span>
      <span :class="deltaDisplay.faster === null ? 'text-slate/50' : 'text-ui-good'">{{ deltaDisplay.text }}</span>
      <div class="h-[1px] bg-slate/40 flex-grow mx-2"></div>
      <span v-if="deltaDisplay.faster">{{ deltaDisplay.faster }} FASTER</span>
      <span v-else class="text-slate/50">—</span>
    </div>

    <!-- Pedal-state comparison -->
    <div class="px-2 mb-3">
      <div class="text-small text-slate mb-1 tracking-widest">PEDAL STATE %</div>
      <div class="flex flex-col gap-1">
        <div
          v-for="key in ['throttle_only', 'brake_only', 'trail_brake', 'coast'] as const"
          :key="key"
          class="flex items-center text-small"
        >
          <span class="w-[clamp(80px,18vw,140px)] text-silver uppercase">
            {{ key.replace('_', ' ') }}
          </span>

          <!-- Left side bar -->
          <div class="flex-1 h-3 bg-ink border border-slate/40 relative mx-1">
            <div
              class="absolute inset-y-0 left-0 bg-ui-info"
              :style="{ width: `${Math.min(100, statePct(left, key))}%` }"
            ></div>
            <span class="absolute right-1 top-1/2 -translate-y-1/2 text-[10px] text-white">
              {{ statePct(left, key).toFixed(0) }}%
            </span>
          </div>

          <!-- Right side bar -->
          <div class="flex-1 h-3 bg-ink border border-slate/40 relative mx-1">
            <div
              class="absolute inset-y-0 left-0 bg-ui-warn"
              :style="{ width: `${Math.min(100, statePct(right, key))}%` }"
            ></div>
            <span class="absolute right-1 top-1/2 -translate-y-1/2 text-[10px] text-white">
              {{ statePct(right, key).toFixed(0) }}%
            </span>
          </div>
        </div>
      </div>
      <div v-if="!left.pedal && !right.pedal && !left.loading && !right.loading"
           class="text-small text-slate italic mt-2">
        Pedal-state data unavailable for both sessions.
      </div>
    </div>

    <!-- Sector compare -->
    <div class="px-2">
      <div class="text-small text-slate mb-1 tracking-widest">BEST SECTOR TIMES (S)</div>
      <table class="w-full font-mono text-small">
        <thead>
          <tr class="text-slate border-b border-slate/40">
            <th class="text-left pb-1">SECTOR</th>
            <th class="text-right pb-1 text-ui-info">LEFT</th>
            <th class="text-right pb-1 text-ui-warn">RIGHT</th>
            <th class="text-right pb-1">Δ</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sectorCompare" :key="row.name" class="text-silver">
            <td class="py-0.5">{{ row.name }}</td>
            <td class="py-0.5 text-right text-ui-info">
              {{ row.leftBest != null ? row.leftBest.toFixed(3) : '—' }}
            </td>
            <td class="py-0.5 text-right text-ui-warn">
              {{ row.rightBest != null ? row.rightBest.toFixed(3) : '—' }}
            </td>
            <td
              class="py-0.5 text-right font-bold"
              :class="row.delta == null ? 'text-slate/50' : row.delta < 0 ? 'text-ui-good' : 'text-ui-bad'"
            >
              {{ row.delta == null ? '—' : (row.delta < 0 ? '' : '+') + row.delta.toFixed(3) }}
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!sectorCompare.some(r => r.leftBest != null || r.rightBest != null)"
           class="text-small text-slate italic mt-1">
        Sector-time data unavailable. Drive at least one flying lap on each session.
      </div>
    </div>

    <!-- Loading / error pills -->
    <div v-if="left.loading || right.loading" class="px-2 mt-2 text-small text-ui-info">
      Loading…
    </div>
    <div v-if="left.error || right.error" class="px-2 mt-2 text-small text-ui-bad">
      {{ left.error ?? right.error }}
    </div>

    <!-- Coach -->
    <div class="absolute bottom-[6vh] right-2 flex flex-col items-end gap-1">
      <CyberBox variant="charcoal" border="slate" class="text-small px-2 py-1 text-slate">
        {{ save.activeSlot?.preferredCoach?.toUpperCase() ?? 'T-ROD' }}
      </CyberBox>
      <CyberBox variant="charcoal" border="slate" class="w-[clamp(36px,8vmin,64px)] h-[clamp(36px,8vmin,64px)] overflow-hidden relative">
        <Sprite :sheet="save.activeSlot?.preferredCoach ?? 'trod'" animation="idle" class="scale-150 origin-center opacity-80 mix-blend-screen" style="filter: grayscale(1) sepia(1) hue-rotate(180deg) saturate(3);" />
      </CyberBox>
    </div>
  </PageShell>
</template>

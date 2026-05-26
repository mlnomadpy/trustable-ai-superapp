<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useTelemetryStore } from '@/entities/session/model/telemetryStore'
import { useLapTimeStore } from '@/entities/lap-time/model/lapTimeStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import TrackMap from '@/shared/ui/core/TrackMap.vue'

const router = useRouter()
const audio = useAudioStore()
const telemetry = useTelemetryStore()
const lapTimes = useLapTimeStore()
const session = useSessionStore()

// ── Tabs ────────────────────────────────────────────────────────────────────
const TABS = ['TRACK', 'LAP TIMES', 'TELEMETRY'] as const
const activeTab = ref(0)

const switchTab = (i: number) => {
  if (i === activeTab.value) return
  audio.playSfx('cursor_move')
  activeTab.value = i
}

interface SectorRow {
  id: number
  lap: number
  s1: string
  s2: string
  s3: string
  total: string
  state: string   // 'purple' = personal best, 'green' = good, 'yellow' = slow
}

/** Build sector time rows from real lap data */
const sectorTimes = computed<SectorRow[]>(() => {
  if (lapTimes.laps.length === 0) return []

  const bestTime = lapTimes.bestLapS ?? Infinity

  return lapTimes.laps.map((lap, i) => {
    const sectors = lap.sectors ?? []
    const total = lap.lap_time_s ?? 0
    const mins = Math.floor(total / 60)
    const secs = (total % 60).toFixed(1)

    let state = 'yellow'
    if (lap.is_best) state = 'purple'
    else if (total - bestTime < 2) state = 'green'

    return {
      id: i,
      lap: lap.lap_number,
      s1: sectors[0]?.time_s?.toFixed(1) ?? '--.-',
      s2: sectors[1]?.time_s?.toFixed(1) ?? '--.-',
      s3: sectors[2]?.time_s?.toFixed(1) ?? '--.-',
      total: `${mins}:${secs.padStart(4, '0')}`,
      state,
    }
  }).reverse()  // newest lap first
})

const carPos = ref(0)
const trackMapRef = ref<any>(null)
const activeTurnId = ref<number | null>(null)
let intervalId: number | null = null

const tick = () => {
  // Use real telemetry distance only — no fake fallback. Car freezes when no live frame.
  if (!telemetry.frame) {
    activeTurnId.value = null
    return
  }

  // Track length ~4258m for Sonoma — normalize to 0-100%
  carPos.value = (telemetry.frame.distance / 4258) * 100 % 100

  if (trackMapRef.value && trackMapRef.value.trackTurns) {
    const pt = trackMapRef.value.getPointAtProgress(carPos.value)
    let closest: any = null
    let minDist = Infinity
    trackMapRef.value.trackTurns.forEach((t: any) => {
      const dist = Math.hypot(t.cx - pt.x, t.cy - pt.y)
      if (dist < minDist) {
        minDist = dist
        closest = t
      }
    })
    if (closest && minDist < 150) {
      activeTurnId.value = closest.id
    } else {
      activeTurnId.value = null
    }
  }
}

onMounted(async () => {
  const sid = session.activeSessionId ?? session.sessions.find(s => s.lap_count > 0)?.session_id
  if (sid) await lapTimes.fetchLapTimes(sid)

  intervalId = window.setInterval(tick, 200)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
    return
  }
  if (e.key === '1') switchTab(0)
  else if (e.key === '2') switchTab(1)
  else if (e.key === '3') switchTab(2)
})

const getColorClass = (state: string) => {
  if (state === 'purple') return 'text-purple-glow font-bold'
  if (state === 'green') return 'text-ui-good'
  return 'text-ui-warn'
}

// ── Telemetry formatting helpers (honest "—" when no live frame) ─────────────
const hasFrame = computed(() => telemetry.frame !== null)
const fmtNum = (v: number | undefined | null, digits = 0, suffix = '') =>
  (v === undefined || v === null || Number.isNaN(v)) ? '—' : `${v.toFixed(digits)}${suffix}`

const tSpeed = computed(() => fmtNum(telemetry.frame?.speed, 0, ' KM/H'))
const tRpm = computed(() => fmtNum(telemetry.frame?.rpm, 0, ' RPM'))
const tThrottle = computed(() => fmtNum(telemetry.frame?.throttle, 0, '%'))
const tBrake = computed(() => fmtNum(telemetry.frame?.brake_pressure, 0, '%'))
const tSteering = computed(() => fmtNum(telemetry.frame?.steering, 0, '°'))
const tGLat = computed(() => fmtNum(telemetry.frame?.g_lat, 2, ' G'))
const tGLong = computed(() => fmtNum(telemetry.frame?.g_long, 2, ' G'))
const tCombo = computed(() => fmtNum(telemetry.frame?.combo_g, 2, ' G'))
const tDistance = computed(() => fmtNum(telemetry.frame?.distance, 0, ' M'))

// ── Driver / Tyres / Fuel — real fields only ────────────────────────────────
// Driver: from active session row (string). Tyres + Fuel have no real source
// in the current store/backend, so they render "—". See deliverable note.
const driverName = computed(() => session.activeSession?.driver?.toUpperCase() ?? '—')
const lapCountStr = computed(() => {
  const n = lapTimes.laps.length
  return n > 0 ? `${n} LAPS` : '—'
})
</script>

<template>
  <PageShell title="PIT WALL" :hints="['1/2/3 · TABS', 'B · BACK', 'LIVE TELEMETRY']" bg="danger">

    <div class="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0)_0%,rgba(0,0,0,0.8)_100%)] z-0"></div>

    <template #heading>
      <div class="heading-block mb-[1vh] flex justify-between items-end relative z-10">
        <button
          class="text-title font-title text-silver tracking-[0.2em] bg-transparent border-none cursor-pointer min-h-[44px]"
          @click="audio.playSfx('cancel'); router.back()"
        >◀ RACE ENGINEER</button>
        <div class="flex items-center gap-3">
          <div
            class="text-small font-bold border px-2 rounded"
            :class="hasFrame ? 'text-ui-warn border-ui-warn animate-pulse' : 'text-slate border-slate'"
          >{{ hasFrame ? 'LIVE' : 'NO SIGNAL' }}</div>
        </div>
      </div>
    </template>

    <div class="flex-grow flex flex-col mx-2 pb-6 gap-2 relative z-10 font-mono min-h-0">

      <CyberTabs :tabs="TABS" :modelValue="activeTab" @update:modelValue="switchTab" />

      <!-- TRACK TAB ──────────────────────────────────────────────────────── -->
      <div v-if="activeTab === 0" class="flex-grow flex flex-col gap-2 min-h-0">
        <CyberPanel class="flex-grow flex flex-col items-center justify-center bg-black border-slate relative overflow-hidden p-2 min-h-0">
          <div class="absolute top-2 left-2 text-silver text-small font-bold uppercase z-10">TRACK MAP</div>
          <TrackMap ref="trackMapRef" :carProgress="carPos" :activeTurnId="activeTurnId" />
        </CyberPanel>

        <CyberPanel class="h-28 shrink-0 bg-ink border-slate p-3 grid grid-cols-3 gap-4">
          <div class="flex flex-col justify-center">
            <span class="text-slate font-bold text-small">DRIVER</span>
            <span class="text-white text-body truncate">{{ driverName }}</span>
          </div>
          <div class="flex flex-col justify-center">
            <span class="text-slate font-bold text-small">TYRES</span>
            <!-- No real tyre compound/age source in backend yet — honest "—" -->
            <span class="text-silver text-body">— <span class="text-slate text-small">({{ lapCountStr }})</span></span>
          </div>
          <div class="flex flex-col justify-center">
            <span class="text-slate font-bold text-small">FUEL</span>
            <!-- No real fuel telemetry channel exposed — honest "—" -->
            <span class="text-silver text-body">—</span>
          </div>
        </CyberPanel>
      </div>

      <!-- LAP TIMES TAB ───────────────────────────────────────────────────── -->
      <CyberPanel
        v-else-if="activeTab === 1"
        class="flex-grow flex flex-col bg-ink border-slate p-0 overflow-hidden min-h-0"
      >
        <div class="bg-charcoal flex text-silver font-bold text-small px-4 py-3 border-b border-slate sticky top-0 z-10">
          <div class="w-1/6">LAP</div>
          <div class="w-1/5 text-right">S1</div>
          <div class="w-1/5 text-right">S2</div>
          <div class="w-1/5 text-right">S3</div>
          <div class="w-auto ml-auto text-right">TOTAL</div>
        </div>

        <div class="flex-grow overflow-y-auto min-h-0 p-2">
          <div v-if="sectorTimes.length === 0" class="text-slate text-body text-center py-8">
            — NO LAP DATA —
          </div>
          <div
            v-for="(lap, idx) in sectorTimes"
            :key="lap.id"
            class="flex items-center px-4 py-3 border-b border-charcoal text-body transition-all min-h-[44px]"
            :class="idx === 0 ? 'bg-charcoal/50 animate-pulse' : ''"
          >
            <div class="w-1/6 text-silver font-bold">L{{ lap.lap }}</div>
            <div class="w-1/5 text-right" :class="getColorClass(lap.state)">{{ lap.s1 }}</div>
            <div class="w-1/5 text-right" :class="getColorClass(lap.state)">{{ lap.s2 }}</div>
            <div class="w-1/5 text-right" :class="getColorClass(lap.state)">{{ lap.s3 }}</div>
            <div class="w-auto ml-auto text-right font-bold text-white">{{ lap.total }}</div>
          </div>
        </div>
      </CyberPanel>

      <!-- TELEMETRY TAB ──────────────────────────────────────────────────── -->
      <CyberPanel
        v-else
        class="flex-grow flex flex-col bg-ink border-slate p-4 overflow-y-auto min-h-0"
      >
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-silver font-bold text-small uppercase">LIVE FRAME</span>
          <span
            class="text-small font-bold"
            :class="hasFrame ? 'text-ui-good' : 'text-slate'"
          >{{ hasFrame ? 'STREAMING' : 'NO LIVE FRAME' }}</span>
        </div>

        <!-- Primary readouts -->
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">SPEED</div>
            <div class="text-white text-title font-bold">{{ tSpeed }}</div>
          </div>
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">RPM</div>
            <div class="text-white text-title font-bold">{{ tRpm }}</div>
          </div>
        </div>

        <!-- Driver inputs -->
        <div class="grid grid-cols-3 gap-3 mb-4">
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">THROTTLE</div>
            <div class="text-ui-good text-body font-bold">{{ tThrottle }}</div>
          </div>
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">BRAKE</div>
            <div class="text-ui-warn text-body font-bold">{{ tBrake }}</div>
          </div>
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">STEERING</div>
            <div class="text-silver text-body font-bold">{{ tSteering }}</div>
          </div>
        </div>

        <!-- G forces -->
        <div class="grid grid-cols-3 gap-3 mb-4">
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">G LAT</div>
            <div class="text-silver text-body font-bold">{{ tGLat }}</div>
          </div>
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">G LONG</div>
            <div class="text-silver text-body font-bold">{{ tGLong }}</div>
          </div>
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">COMBO G</div>
            <div class="text-silver text-body font-bold">{{ tCombo }}</div>
          </div>
        </div>

        <!-- Position -->
        <div class="grid grid-cols-2 gap-3">
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">DISTANCE</div>
            <div class="text-silver text-body font-bold">{{ tDistance }}</div>
          </div>
          <div class="bg-charcoal border border-slate p-3 min-h-[44px]">
            <div class="text-slate text-small font-bold">LAP</div>
            <div class="text-silver text-body font-bold">{{ lapCountStr }}</div>
          </div>
        </div>
      </CyberPanel>

    </div>
  </PageShell>
</template>

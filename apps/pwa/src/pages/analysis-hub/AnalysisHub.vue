<script setup lang="ts">
/**
 * ANALYSIS HALL — tabbed telemetry workbench.
 *
 * Replaces the prior tile-grid hub. Six tabs (Overview / Telemetry /
 * Systems / IMU / Signals / Modules) each render against the same
 * DuckDB-wasm session view + lap-filter selection.
 *
 * Tab components are lazy-imported (defineAsyncComponent) so the
 * Leaflet + Chart.js + zoom-plugin bundles only ship to clients that
 * actually open those tabs.
 */
import { computed, defineAsyncComponent, onMounted, watch } from 'vue'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberCheckbox from '@/shared/ui/core/CyberCheckbox.vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useAnalysisStore, TAB_ORDER, type TabId } from '@/entities/analysis/model/analysisStore'

const router = useRouter()
const sessionStore = useSessionStore()
const audio = useAudioStore()
const analysis = useAnalysisStore()

const OverviewTab  = defineAsyncComponent(() => import('./tabs/OverviewTab.vue'))
const TelemetryTab = defineAsyncComponent(() => import('./tabs/TelemetryTab.vue'))
const SystemsTab   = defineAsyncComponent(() => import('./tabs/SystemsTab.vue'))
const ImuTab       = defineAsyncComponent(() => import('./tabs/ImuTab.vue'))
const SignalsTab   = defineAsyncComponent(() => import('./tabs/SignalsTab.vue'))
const ModulesTab   = defineAsyncComponent(() => import('./tabs/ModulesTab.vue'))

const TAB_LABELS = ['OVERVIEW', 'TELEMETRY', 'SYSTEMS', 'IMU', 'SIGNALS', 'MODULES'] as const

const activeTabIndex = computed({
  get: () => TAB_ORDER.indexOf(analysis.activeTab),
  set: (i: number) => {
    const t = TAB_ORDER[i] as TabId | undefined
    if (t) analysis.setActiveTab(t)
  },
})

// ── Initial session selection ────────────────────────────────────────────
onMounted(async () => {
  // Pull the live session list so the picker has options. The save
  // store may still expose past sessions for offline browsing — we
  // don't use those here, this view requires parquet exports.
  try {
    await sessionStore.fetchSessions()
  } catch { /* offline — surfaced inline */ }

  // Default to most recent session if none is selected yet.
  if (!analysis.sessionId && sessionStore.sessions.length) {
    const sorted = [...sessionStore.sessions].sort((a, b) => {
      const ta = a.started_at ? Date.parse(a.started_at) : 0
      const tb = b.started_at ? Date.parse(b.started_at) : 0
      return tb - ta
    })
    await analysis.loadSession(sorted[0].session_id)
  }
})

watch(() => analysis.sessionId, (sid) => {
  if (sid && sessionStore.activeSessionId !== sid) {
    sessionStore.activeSessionId = sid
  }
})

// ── Toolbar interactions ─────────────────────────────────────────────────
async function onSessionPick(e: Event) {
  const sid = (e.target as HTMLSelectElement).value
  if (sid) {
    await analysis.loadSession(sid)
  }
}

function onLapPick(e: Event) {
  const idx = parseInt((e.target as HTMLSelectElement).value, 10)
  if (!Number.isNaN(idx)) analysis.setSelectedLap(idx)
}

function fmtDur(s: number): string {
  if (!s) return '—'
  if (s < 60) return s.toFixed(1) + ' s'
  if (s < 3600) return Math.floor(s / 60) + 'm ' + Math.floor(s % 60) + 's'
  return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm'
}

const lapOptions = computed(() => analysis.laps.map((lap, i) => {
  const tag = lap.method === 'gps' ? '' : lap.method === 'stint' ? ' · stint' : lap.method === 'distance' ? ' · dist' : ''
  const dist = lap.distance_m > 50 ? ` · ${(lap.distance_m / 1000).toFixed(2)} km` : ''
  return { i, label: `${lap.name}${tag} · ${fmtDur(lap.duration_s)}${dist}` }
}))

// ── Keyboard ─────────────────────────────────────────────────────────────
useKeyboard((e: KeyboardEvent) => {
  // ESC is owned by App.vue's global pop — don't re-bind here.
  if (e.key >= '1' && e.key <= '6') {
    const i = parseInt(e.key, 10) - 1
    if (i >= 0 && i < TAB_ORDER.length) {
      activeTabIndex.value = i
      audio.playSfx('cursor_select')
    }
    return
  }
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    if (!analysis.laps.length) return
    analysis.cycleLap(e.key === 'ArrowRight' ? 1 : -1)
    audio.playSfx('cursor_move')
    return
  }
  if (e.key === 'o' || e.key === 'O') {
    analysis.setFilterOutliers(!analysis.filterOutliers)
    audio.playSfx('cursor_select')
    return
  }
  if (e.key === 'b' || e.key === 'Backspace') {
    audio.playSfx('cancel')
    router.push('/garage')
  }
})
</script>

<template>
  <PageShell title="ANALYSIS HALL" :hints="['1-6 · TABS', '◀▶ · LAPS', 'O · OUTLIERS', 'B · GARAGE']" bg="cool">
    <div class="flex flex-col h-full min-h-0 gap-2">
      <!-- Toolbar -->
      <div class="flex flex-wrap items-center gap-2 pb-1">
        <label class="text-slate text-small tracking-widest">SESSION</label>
        <select
          class="bg-charcoal text-silver border border-slate/40 rounded px-2 py-1 text-small min-h-[44px] min-w-[200px]"
          :value="analysis.sessionId ?? ''"
          aria-label="Select session"
          @change="onSessionPick"
        >
          <option value="" disabled>— pick a session —</option>
          <option
            v-for="s in sessionStore.sessions"
            :key="s.session_id"
            :value="s.session_id"
          >{{ s.session_id }} · {{ s.track || '—' }}{{ s.started_at ? ' · ' + new Date(s.started_at).toLocaleString() : '' }}</option>
        </select>

        <label class="text-slate text-small tracking-widest ml-2">LAP</label>
        <select
          class="bg-charcoal text-silver border border-slate/40 rounded px-2 py-1 text-small min-h-[44px] min-w-[180px]"
          :value="analysis.selectedLapIndex"
          :disabled="!analysis.laps.length"
          aria-label="Select lap"
          @change="onLapPick"
        >
          <option v-for="o in lapOptions" :key="o.i" :value="o.i">{{ o.label }}</option>
          <option v-if="!analysis.laps.length" value="0">— full session —</option>
        </select>

        <div class="ml-3">
          <CyberCheckbox
            label="FILTER OUTLIERS"
            :checked="analysis.filterOutliers"
            :focused="false"
            @change="(v) => analysis.setFilterOutliers(v)"
          />
        </div>

        <span v-if="analysis.loading" class="text-ui-warn text-small ml-auto">LOADING…</span>
        <span v-else-if="analysis.error" class="text-ui-bad text-small ml-auto">DATA UNAVAILABLE — {{ analysis.error }}</span>
        <span v-else-if="analysis.lapsError" class="text-ui-warn text-small ml-auto">LAPS UNAVAILABLE — {{ analysis.lapsError }}</span>
      </div>

      <!-- Tab bar -->
      <CyberTabs v-model="activeTabIndex" :tabs="TAB_LABELS" />

      <!-- Tab content -->
      <div class="flex-1 min-h-0">
        <div v-if="!analysis.sessionId && !analysis.loading" class="h-full flex items-center justify-center">
          <CyberPanel class="text-center" :animate="false">
            <div class="text-ui-warn text-body">NO SESSION SELECTED</div>
            <div class="text-slate text-small mt-2">
              Pick a session from the toolbar.
              <span v-if="sessionStore.sessionsError" class="block mt-1 text-ui-bad">SESSIONS UNAVAILABLE — bridge offline?</span>
            </div>
          </CyberPanel>
        </div>
        <OverviewTab  v-else-if="analysis.activeTab === 'overview'"  />
        <TelemetryTab v-else-if="analysis.activeTab === 'telemetry'" />
        <SystemsTab   v-else-if="analysis.activeTab === 'systems'"   />
        <ImuTab       v-else-if="analysis.activeTab === 'imu'"       />
        <SignalsTab   v-else-if="analysis.activeTab === 'signals'"   />
        <ModulesTab   v-else-if="analysis.activeTab === 'modules'"   />
      </div>
    </div>
  </PageShell>
</template>

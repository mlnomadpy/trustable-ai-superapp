<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useDuckDBStore } from '@/shared/lib/duckdb/duckdbStore'
import { useMedalStore } from '@/entities/quest/model/medalStore'
import { bridge } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberSplitView from '@/shared/ui/core/CyberSplitView.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberAvatar from '@/shared/ui/core/CyberAvatar.vue'
import MedalGrid from '@/widgets/medal-grid/MedalGrid.vue'
import CyberRadarChart from '@/shared/ui/core/CyberRadarChart.vue'
import CyberSkeleton from '@/shared/ui/core/CyberSkeleton.vue'
import { useSwipeGesture } from '@/shared/lib/useSwipeGesture'
import { formatLapTime } from '@/shared/lib/lap'

const medalStore = useMedalStore()

// Radar stats — populated from /driver/<id>/profile (the bridge
// computes per-skill scores from past sessions). Empty when the
// endpoint is unreachable; the template renders "DATA UNAVAILABLE".
const driverStats = ref<{ label: string; value: number }[]>([])
const profileError = ref<string | null>(null)

/**
 * Normalise the bridge's free-form /driver/<id>/profile response into
 * { label, value } points the radar chart can plot. The bridge returns
 * a dict whose keys are skill names and values are numeric scores
 * (typically 0–100 or 0–10). We accept either by:
 *   • dropping non-numeric values
 *   • clamping to a 0–100 range so the radar isn't dominated by outliers
 * If the response carries an explicit `radar` / `skills` array we use
 * that directly.
 */
function projectProfileToRadar(payload: any): { label: string; value: number }[] {
  if (!payload || typeof payload !== 'object') return []
  // Explicit array forms — preferred when present.
  const arr = payload.radar ?? payload.skills ?? payload.stats
  if (Array.isArray(arr)) {
    return arr
      .map((s: any) => ({
        label: String(s.label ?? s.name ?? '').toUpperCase(),
        value: typeof s.value === 'number' ? s.value : Number(s.value),
      }))
      .filter((s) => s.label && Number.isFinite(s.value))
      .map((s) => ({ ...s, value: Math.max(0, Math.min(100, s.value)) }))
  }
  // Otherwise treat the dict at the top level as { skill: score }, with
  // a few well-known meta fields filtered out.
  const META = new Set(['driver_id', 'driver', 'updated_at', 'session_count', 'error'])
  return Object.entries(payload)
    .filter(([k, v]) => !META.has(k) && typeof v === 'number' && Number.isFinite(v))
    .map(([k, v]) => ({
      label: k.toUpperCase().replace(/_/g, ' '),
      value: Math.max(0, Math.min(100, v as number)),
    }))
}

const tabs = ['SKILLS', 'MEDALS']
const activeTab = ref(0)

const switchTab = (val: number) => {
  activeTab.value = val
}

const router = useRouter()
const saveStore = useSaveStore()
const duckDB = useDuckDBStore()

const save = saveStore.activeSlot
const hints = ['◀ ▶ TABS', 'B · GARAGE']

const totalSessions = ref(save?.sessions.length ?? 0)
const bestLapS = ref<number | null>(null)
const loading = ref(true)

onMounted(async () => {
  medalStore.fetchMedals()
  if (!duckDB.db) {
    try {
      await duckDB.init()
    } catch (e) {
      console.error('Failed to init DuckDB', e)
    }
  }

  if (save && Object.keys(save.bestLapBySession).length > 0) {
    bestLapS.value = Math.min(...Object.values(save.bestLapBySession))
  }

  // /driver/<id>/profile exists on the bridge — populates the SKILLS
  // radar with real per-skill scores. Falls back to an honest empty
  // state on 404 / 503 (driver profile unavailable).
  const driverId = save?.driverName
  if (driverId) {
    try {
      const payload = await bridge.get<any>(`/driver/${encodeURIComponent(driverId)}/profile`)
      driverStats.value = projectProfileToRadar(payload)
    } catch (e: any) {
      profileError.value = e?.message ?? String(e)
      driverStats.value = []
    }
  }

  loading.value = false
})

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    router.push('/garage')
  } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    activeTab.value = activeTab.value === 0 ? 1 : 0
  }
})

// Profile card — HUD-style precision (matches what the driver saw in the car).
const formatLap = (s: number | null) => formatLapTime(s, 1)

useSwipeGesture(null, {
  onSwipeLeft: () => { activeTab.value = activeTab.value === 0 ? 1 : 0 },
  onSwipeRight: () => { activeTab.value = activeTab.value === 0 ? 1 : 0 },
})
</script>

<template>
  <PageShell title="TRAINER CARD" :hints="hints" bg="neutral">
    <template #heading>
      <div class="heading-block mb-[2vh] text-center">
        <h1 class="text-title font-title text-silver tracking-[0.3em]">TRAINER CARD</h1>
        <div class="heading-rule"></div>
        <button class="mt-2 text-small text-slate bg-transparent border border-slate px-3 py-1 cursor-pointer tracking-widest" @click="router.push('/garage')">◀ BACK TO GARAGE</button>
      </div>
    </template>
    
    <div class="content flex flex-col h-full relative z-10 w-full pb-[6vh]" v-if="save">
      
      <CyberSplitView split="40-60" gap="md" class="h-full min-h-0">
        <!-- Left Pane: Profile -->
        <template #left>
          <CyberPanel class="h-full flex flex-col min-h-0 p-3">
            <div class="text-body text-silver mb-[1.5vh] border-b border-slate pb-[1vh] tracking-[0.1em]">
              DRIVER PROFILE
            </div>
            
            <div class="flex flex-col items-center flex-grow justify-center gap-[2vmin]">
              <CyberAvatar :sheet="save.driverAvatar || 'avatar_a'" size="lg" variant="glow" />
              
              <div class="text-center w-full px-2">
                <div class="text-ui-good text-[clamp(14px,3.5vmin,24px)] font-bold mb-1 font-title">{{ save.driverName }}</div>
                <div class="text-silver text-body mb-[2vmin]">LV. {{ save.level }} · {{ save.skillLevel.toUpperCase() }}</div>
                
                <div class="grid grid-cols-2 gap-y-2 gap-x-4 text-small border-t border-slate pt-[2vmin] mt-[1vmin] w-full text-left">
                  <div class="text-slate">SESSIONS:</div>
                  <div class="text-silver text-right">{{ totalSessions }}</div>
                  <div class="text-slate">COACH:</div>
                  <div class="text-silver text-right uppercase">{{ save.preferredCoach }}</div>
                  <div class="text-slate">BEST LAP:</div>
                  <div class="text-ui-warn text-right font-bold">{{ formatLap(bestLapS) }}</div>
                </div>
              </div>
            </div>
          </CyberPanel>
        </template>
        
        <!-- Right Pane: Tabs (Skills / Medals) -->
        <template #right>
          <div class="h-full flex flex-col min-h-0 w-full">
            <CyberTabs :tabs="tabs" v-model="activeTab" @change="switchTab" class="mb-[1.5vh]" />
            
            <CyberPanel variant="glass" border="secondary" class="flex-1 flex flex-col overflow-hidden min-h-0 p-3">
              <div v-if="loading" class="w-full h-full flex flex-col items-center justify-center p-4 gap-4">
                <CyberSkeleton variant="chart" />
                <CyberSkeleton variant="stat" :count="3" />
              </div>
              
              <template v-else>
                <!-- SKILLS TAB -->
                <div v-if="activeTab === 0" class="w-full h-full flex flex-col min-h-0">
                  <div class="text-small text-silver mb-2 border-b border-slate pb-1 flex justify-between flex-shrink-0">
                    <span>DRIVING STYLE ANALYSIS</span>
                    <span class="text-slate font-bold">—</span>
                  </div>
                  <div class="flex-grow flex items-center justify-center p-2 min-h-0 text-center">
                    <div v-if="profileError" class="text-small text-ui-bad tracking-widest uppercase max-w-[28ch]">
                      DATA UNAVAILABLE
                      <div class="mt-2 text-slate/60 text-tiny normal-case tracking-normal">{{ profileError }}</div>
                    </div>
                    <div v-else-if="driverStats.length === 0" class="text-small text-slate tracking-widest uppercase max-w-[28ch]">
                      NO DRIVER PROFILE STATS YET
                      <div class="mt-2 text-slate/60 text-tiny normal-case tracking-normal">(Drive a few sessions to populate /driver/{id}/profile.)</div>
                    </div>
                    <CyberRadarChart v-else :stats="driverStats" />
                  </div>
                </div>
                
                <!-- MEDALS TAB -->
                <div v-if="activeTab === 1" class="w-full h-full flex flex-col min-h-0">
                  <div class="text-small text-silver mb-2 border-b border-slate pb-1 flex justify-between flex-shrink-0">
                    <span>MEDAL DATABASE</span>
                    <span class="text-ui-good font-bold">{{ medalStore.unlockedCount }} / {{ medalStore.totalCount }}</span>
                  </div>
                  <div
                    v-if="medalStore.endpointMissing"
                    class="flex-grow flex items-center justify-center text-center p-4"
                  >
                    <div class="text-ui-warn text-small tracking-widest uppercase max-w-[36ch]">
                      MEDALS UNAVAILABLE
                      <div class="mt-2 text-slate text-tiny normal-case tracking-normal">
                        Backend not implemented yet.
                      </div>
                    </div>
                  </div>
                  <div
                    v-else-if="medalStore.error"
                    class="flex-grow flex items-center justify-center text-center p-4"
                  >
                    <div class="text-ui-bad text-small tracking-widest uppercase max-w-[36ch]">
                      MEDALS UNAVAILABLE
                      <div class="mt-2 text-slate text-tiny normal-case tracking-normal">
                        {{ medalStore.error }}
                      </div>
                    </div>
                  </div>
                  <MedalGrid
                    v-else
                    :medals="medalStore.medals"
                    :cursorIndex="-1"
                    @select="() => {}"
                    class="flex-grow"
                  />
                </div>
              </template>
            </CyberPanel>
          </div>
        </template>
      </CyberSplitView>
      
    </div>
  </PageShell>
</template>

<style scoped>
.heading-block { text-align: center; }
</style>

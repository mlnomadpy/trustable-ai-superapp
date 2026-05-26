<script setup lang="ts">
/**
 * CALIBRATION — tabbed layout for Pixel 10 landscape.
 *
 * Four tabs: STEERING · PEDALS · IMU · GPS. Each tab polls
 * /diagnostics/can for current values (steering angle, throttle/brake
 * raw, IMU accel/gyro, GPS fix). When a signal isn't present in the
 * registry the tab surfaces a "DATA UNAVAILABLE — bridge signal
 * missing" banner rather than faking a value.
 *
 * Calibration writes (POST /calibration/...) do not yet exist on
 * the bridge. Each tab carries a "CALIBRATION NOT PERSISTED
 * SERVER-SIDE YET" badge so users aren't led to believe changes
 * survive a restart. The local zero/lock buttons store deltas in
 * component state only.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { bridge } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'

const router = useRouter()
const audio = useAudioStore()
const bridgeStore = useBridgeStore()

const TAB_LABELS = ['STEERING', 'PEDALS', 'IMU', 'GPS'] as const
const activeTab = ref(0)

// ── /diagnostics/can polling ────────────────────────────────────────────────
interface CanDiagnostics {
  loaded?: boolean
  connected?: boolean
  interface?: string | null
  channel?: string | null
  bitrate?: number | null
  frames_total?: number
  frames_unknown?: number
  frames_per_second?: number
  last_frame_age_s?: number | null
  signal_registry_count?: number
  // Live signal snapshot — present if the bridge populates it.
  signals?: Record<string, number | null>
}

const canDiag = ref<CanDiagnostics | null>(null)
const canDiagError = ref<string | null>(null)
const canDiagMissing = ref(false)
let pollHandle: number | null = null

const pollCanDiagnostics = async () => {
  if (!bridgeStore.health) return
  try {
    canDiag.value = await bridge.get<CanDiagnostics>('/diagnostics/can')
    canDiagError.value = null
    canDiagMissing.value = false
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg.includes('404')) {
      canDiagMissing.value = true
    } else {
      canDiagError.value = msg
    }
  }
}

onMounted(() => {
  if (!bridgeStore.health && !bridgeStore.isPolling) bridgeStore.startPolling()
  pollCanDiagnostics()
  pollHandle = window.setInterval(pollCanDiagnostics, 1000)
})

onUnmounted(() => {
  if (pollHandle !== null) {
    clearInterval(pollHandle)
    pollHandle = null
  }
})

// Live signal readers. The bridge does NOT currently expose a
// /diagnostics/can signal map — we treat it as missing and show the
// "no signal" banner. If a future bridge adds `signals`, we'll pick
// it up automatically without code changes.
const signal = (name: string): number | null => {
  const s = canDiag.value?.signals
  if (!s) return null
  const v = s[name]
  return typeof v === 'number' ? v : null
}

const steeringAngle = computed(() => signal('SteeringAngle'))
const throttlePos = computed(() => signal('ThrottlePos'))
const brakePos = computed(() => signal('BrakePos'))
const imuAccelX = computed(() => signal('AccelX'))
const imuAccelY = computed(() => signal('AccelY'))
const imuGyroZ = computed(() => signal('GyroZ'))
const gpsLat = computed(() => signal('GpsLat'))
const gpsLon = computed(() => signal('GpsLon'))
const gpsFix = computed(() => signal('GpsFix'))

// ── local calibration deltas (no server-side persist endpoint) ──────────────
const steeringCenter = ref(0)
const steeringLock = ref(0)
const throttleMin = ref(0)
const throttleMax = ref(100)
const brakeMin = ref(0)
const brakeMax = ref(100)
const imuZeroed = ref(false)

const zeroSteering = () => {
  audio.playSfx('cursor_select')
  steeringCenter.value = steeringAngle.value ?? 0
}
const setSteeringLock = () => {
  audio.playSfx('cursor_select')
  steeringLock.value = Math.abs(steeringAngle.value ?? 0)
}
const setThrottleMin = () => { audio.playSfx('cursor_select'); throttleMin.value = throttlePos.value ?? 0 }
const setThrottleMax = () => { audio.playSfx('cursor_select'); throttleMax.value = throttlePos.value ?? 100 }
const setBrakeMin = () => { audio.playSfx('cursor_select'); brakeMin.value = brakePos.value ?? 0 }
const setBrakeMax = () => { audio.playSfx('cursor_select'); brakeMax.value = brakePos.value ?? 100 }
const zeroImu = () => { audio.playSfx('goal_complete'); imuZeroed.value = true }

const bridgeOk = computed(() => bridgeStore.health !== null && bridgeStore.healthError === null)

const signalsMissing = computed(() => !canDiag.value?.signals)

useKeyboard((e: KeyboardEvent) => {
  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }
  if (e.key === '4') { audio.playSfx('cursor_move'); activeTab.value = 3; return }

  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage')
  }
})

const fmt = (v: number | null, digits = 2): string => {
  if (v === null) return '—'
  return v.toFixed(digits)
}
</script>

<template>
  <PageShell
    title="CALIBRATION"
    :hints="['1-4 · TAB', 'B · BACK']"
    bg="neutral"
    :show-heading="false"
  >
    <div class="cal-root flex flex-col h-full w-full gap-[1vmin]">

      <CyberTabs
        v-model="activeTab"
        :tabs="[...TAB_LABELS]"
        class="mx-2 shrink-0"
      />

      <!-- Global diag banners -->
      <div class="mx-2 shrink-0 flex flex-wrap gap-2">
        <div v-if="!bridgeOk" class="px-2 py-1 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-widest uppercase">
          BRIDGE OFFLINE — NO LIVE DATA
        </div>
        <div v-else-if="canDiagMissing" class="px-2 py-1 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-widest uppercase">
          /DIAGNOSTICS/CAN MISSING — UPGRADE BRIDGE
        </div>
        <div v-else-if="canDiagError" class="px-2 py-1 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-widest uppercase">
          DIAG ERROR — {{ canDiagError }}
        </div>
        <div class="px-2 py-1 border border-ui-info/40 bg-ui-info/5 text-small text-ui-info tracking-widest uppercase">
          CALIBRATION NOT PERSISTED SERVER-SIDE YET — LOCAL DELTAS ONLY
        </div>
      </div>

      <div class="flex-1 min-h-0 mx-2 overflow-hidden">

        <!-- STEERING -->
        <CyberPanel v-show="activeTab === 0" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            STEERING
          </div>

          <div v-if="signalsMissing" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">
              Bridge /diagnostics/can does not expose a live signal map.
              Calibration needs `signals.SteeringAngle` (or equivalent) wired through.
            </div>
          </div>
          <div v-else class="font-mono text-body text-silver/90 flex flex-col gap-2">
            <div><span class="text-slate uppercase tracking-widest mr-2">LIVE ANGLE</span><span class="text-white">{{ fmt(steeringAngle, 1) }}°</span></div>
            <div><span class="text-slate uppercase tracking-widest mr-2">CENTER</span><span class="text-ui-good">{{ fmt(steeringCenter, 1) }}°</span></div>
            <div><span class="text-slate uppercase tracking-widest mr-2">LOCK</span><span class="text-ui-good">±{{ fmt(steeringLock, 1) }}°</span></div>
          </div>

          <div class="flex gap-3 mt-[1vmin] shrink-0">
            <CyberBox interactive class="p-2 w-max" @click="zeroSteering">ZERO CENTER</CyberBox>
            <CyberBox interactive class="p-2 w-max" @click="setSteeringLock">SET LOCK-TO-LOCK</CyberBox>
          </div>
        </CyberPanel>

        <!-- PEDALS -->
        <CyberPanel v-show="activeTab === 1" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            PEDALS
          </div>

          <div v-if="signalsMissing" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">
              Bridge /diagnostics/can does not expose live pedal signals.
              Wire `signals.ThrottlePos` and `signals.BrakePos`.
            </div>
          </div>
          <div v-else class="font-mono text-body text-silver/90 flex flex-col gap-2">
            <div>
              <span class="text-slate uppercase tracking-widest mr-2">THROTTLE</span>
              <span class="text-white">{{ fmt(throttlePos, 1) }}%</span>
              <span class="text-slate ml-3">MIN <span class="text-ui-good">{{ fmt(throttleMin, 1) }}</span></span>
              <span class="text-slate ml-3">MAX <span class="text-ui-good">{{ fmt(throttleMax, 1) }}</span></span>
            </div>
            <div>
              <span class="text-slate uppercase tracking-widest mr-2">BRAKE</span>
              <span class="text-white">{{ fmt(brakePos, 1) }}%</span>
              <span class="text-slate ml-3">MIN <span class="text-ui-good">{{ fmt(brakeMin, 1) }}</span></span>
              <span class="text-slate ml-3">MAX <span class="text-ui-good">{{ fmt(brakeMax, 1) }}</span></span>
            </div>
          </div>

          <div class="flex flex-wrap gap-3 mt-[1vmin] shrink-0">
            <CyberBox interactive class="p-2 w-max" @click="setThrottleMin">CAPTURE THROTTLE MIN</CyberBox>
            <CyberBox interactive class="p-2 w-max" @click="setThrottleMax">CAPTURE THROTTLE MAX</CyberBox>
            <CyberBox interactive class="p-2 w-max" @click="setBrakeMin">CAPTURE BRAKE MIN</CyberBox>
            <CyberBox interactive class="p-2 w-max" @click="setBrakeMax">CAPTURE BRAKE MAX</CyberBox>
          </div>
        </CyberPanel>

        <!-- IMU -->
        <CyberPanel v-show="activeTab === 2" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            IMU
          </div>

          <div v-if="signalsMissing" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">
              Bridge /diagnostics/can does not expose IMU signals.
              Wire `signals.AccelX`, `signals.AccelY`, `signals.GyroZ`.
            </div>
          </div>
          <div v-else class="font-mono text-body text-silver/90 flex flex-col gap-2">
            <div><span class="text-slate uppercase tracking-widest mr-2">ACCEL X</span><span class="text-white">{{ fmt(imuAccelX, 2) }} g</span></div>
            <div><span class="text-slate uppercase tracking-widest mr-2">ACCEL Y</span><span class="text-white">{{ fmt(imuAccelY, 2) }} g</span></div>
            <div><span class="text-slate uppercase tracking-widest mr-2">GYRO Z</span><span class="text-white">{{ fmt(imuGyroZ, 2) }} °/s</span></div>
            <div v-if="imuZeroed" class="text-ui-good text-small uppercase tracking-widest mt-[1vmin]">
              ✓ ZEROED LOCALLY (NOT PERSISTED)
            </div>
          </div>

          <div class="flex gap-3 mt-[1vmin] shrink-0">
            <CyberBox interactive class="p-2 w-max" @click="zeroImu">ZERO ACCEL &amp; GYRO</CyberBox>
          </div>
        </CyberPanel>

        <!-- GPS -->
        <CyberPanel v-show="activeTab === 3" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            GPS FIX
          </div>

          <div v-if="signalsMissing" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">
              Bridge /diagnostics/can does not expose GPS signals.
              Wire `signals.GpsLat`, `signals.GpsLon`, `signals.GpsFix`.
            </div>
          </div>
          <div v-else class="font-mono text-body text-silver/90 flex flex-col gap-2">
            <div>
              <span class="text-slate uppercase tracking-widest mr-2">FIX</span>
              <span :class="(gpsFix ?? 0) > 0 ? 'text-ui-good' : 'text-ui-bad'">
                {{ gpsFix === null ? '—' : ((gpsFix ?? 0) > 0 ? '✓ LOCKED' : '✗ NO FIX') }}
              </span>
            </div>
            <div><span class="text-slate uppercase tracking-widest mr-2">LAT</span><span class="text-white">{{ fmt(gpsLat, 6) }}</span></div>
            <div><span class="text-slate uppercase tracking-widest mr-2">LON</span><span class="text-white">{{ fmt(gpsLon, 6) }}</span></div>
          </div>

          <div class="mt-auto pt-[1vmin] border-t border-slate/40 shrink-0 text-small text-slate uppercase tracking-widest leading-relaxed">
            FIX QUALITY DEPENDS ON SKY VIEW AND ANTENNA PLACEMENT. ALLOW 30S OUTDOORS BEFORE A SESSION.
          </div>
        </CyberPanel>

      </div>
    </div>
  </PageShell>
</template>

<style scoped>
.cal-root {
  min-height: 0;
}
</style>

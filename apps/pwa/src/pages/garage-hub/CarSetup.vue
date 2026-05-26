<script setup lang="ts">
/**
 * CAR SETUP — five tabs for Pixel 10 landscape.
 *
 *   CAR          — REAL: identity + CAN pipeline from /cars (data/cars/*.yaml)
 *   AERO         — LOCAL PREF: user choice, persisted to localStorage
 *   SUSPENSION   — LOCAL PREF
 *   BRAKES       — LOCAL PREF
 *   DRIVETRAIN   — LOCAL PREF
 *
 * Why this shape:
 *   The bridge exposes the YAML it loaded via `GET /cars` (see
 *   src/pitwall/features/bp_cars.py). That's the only honest source
 *   for car identity / CAN topology — everything else on this page is
 *   personal preference and would be lying if it claimed to come from
 *   the car. We keep the existing preset tabs but persist them per
 *   browser via localStorage and label them as such. The fake
 *   "TOP SPEED +2.0%" projection deltas were removed because their
 *   coefficients were fabricated; if/when we wire a real setup-impact
 *   model, the deltas come back wired to that.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { bridge, type CarConfig, type CarsResponse } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberValuePicker from '@/shared/ui/core/CyberValuePicker.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'

const router = useRouter()
const audio = useAudioStore()
const bridgeStore = useBridgeStore()

const TAB_LABELS = ['CAR', 'AERO', 'SUSPENSION', 'BRAKES', 'DRIVETRAIN'] as const
const activeTab = ref(0)

// ── /cars (REAL data from data/cars/*.yaml) ────────────────────────────────
const carsResp = ref<CarsResponse | null>(null)
const carsError = ref<string | null>(null)
const carsLoading = ref(false)

const loadedCar = computed<CarConfig | null>(() => {
  if (!carsResp.value) return null
  return carsResp.value.cars.find(c => c.loaded) ?? carsResp.value.cars[0] ?? null
})

const fetchCars = async () => {
  carsLoading.value = true
  carsError.value = null
  try {
    carsResp.value = await bridge.getCars()
  } catch (e) {
    carsError.value = e instanceof Error ? e.message : String(e)
    carsResp.value = null
  } finally {
    carsLoading.value = false
  }
}

// ── option lists (local prefs — labels are arbitrary brackets, not telemetry) ─
const aeroOptions = [
  { id: -2, label: 'MINIMUM' },
  { id: -1, label: 'LOW' },
  { id: 0, label: 'BALANCED' },
  { id: 1, label: 'HIGH' },
  { id: 2, label: 'MAXIMUM' },
]

const rideHeightOptions = [
  { id: -2, label: 'SLAMMED' },
  { id: -1, label: 'LOW' },
  { id: 0, label: 'NEUTRAL' },
  { id: 1, label: 'HIGH' },
  { id: 2, label: 'RALLY' },
]

const springOptions = [
  { id: -2, label: 'SOFT --' },
  { id: -1, label: 'SOFT' },
  { id: 0, label: 'MEDIUM' },
  { id: 1, label: 'STIFF' },
  { id: 2, label: 'STIFF ++' },
]

const damperOptions = [
  { id: -2, label: '-4 CLK' },
  { id: -1, label: '-2 CLK' },
  { id: 0, label: '0 CLK' },
  { id: 1, label: '+2 CLK' },
  { id: 2, label: '+4 CLK' },
]

const arbOptions = [
  { id: -2, label: 'DISC' },
  { id: -1, label: 'SOFT' },
  { id: 0, label: 'MED' },
  { id: 1, label: 'STIFF' },
  { id: 2, label: 'LOCKED' },
]

const brakeBiasOptions = [
  { id: -2, label: 'REAR ++' },
  { id: -1, label: 'REAR +' },
  { id: 0, label: '50 / 50' },
  { id: 1, label: 'FRONT +' },
  { id: 2, label: 'FRONT ++' },
]

const masterCylOptions = [
  { id: -2, label: '0.625"' },
  { id: -1, label: '0.700"' },
  { id: 0, label: '0.750"' },
  { id: 1, label: '0.812"' },
  { id: 2, label: '0.875"' },
]

const diffOptions = [
  { id: -2, label: 'OPEN' },
  { id: -1, label: 'LOOSE' },
  { id: 0, label: 'BALANCED' },
  { id: 1, label: 'TIGHT' },
  { id: 2, label: 'LOCKED' },
]

const ratioOptions = [
  { id: -2, label: 'SHORT --' },
  { id: -1, label: 'SHORT' },
  { id: 0, label: 'STOCK' },
  { id: 1, label: 'TALL' },
  { id: 2, label: 'TALL ++' },
]

const splitterOptions = [
  { id: -2, label: 'OFF' },
  { id: -1, label: 'SMALL' },
  { id: 0, label: 'MED' },
  { id: 1, label: 'LARGE' },
  { id: 2, label: 'MAX' },
]

// ── values (LOCAL PREFS, persisted to localStorage per car) ─────────────────
const LS_KEY = 'pitwall.carsetup.prefs.v1'

interface SetupPrefs {
  aero: number; wing: number; splitter: number; rideHeight: number
  springFront: number; springRear: number; damper: number; arb: number
  brakeBias: number; masterCyl: number
  diffPreload: number; finalDrive: number
}

const DEFAULTS: SetupPrefs = {
  aero: 0, wing: 0, splitter: 0, rideHeight: 0,
  springFront: 0, springRear: 0, damper: 0, arb: 0,
  brakeBias: 0, masterCyl: 0,
  diffPreload: 0, finalDrive: 0,
}

function loadPrefs(): SetupPrefs {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw) as Partial<SetupPrefs>
    return { ...DEFAULTS, ...parsed }
  } catch {
    return { ...DEFAULTS }
  }
}

const prefs = ref<SetupPrefs>(loadPrefs())

// Convenience refs that proxy individual keys for the existing template
const aero = computed({ get: () => prefs.value.aero, set: v => (prefs.value.aero = v) })
const wing = computed({ get: () => prefs.value.aero, set: v => (prefs.value.aero = v) }) // wing == overall aero in our simple model
const splitter = computed({ get: () => prefs.value.splitter, set: v => (prefs.value.splitter = v) })
const rideHeight = computed({ get: () => prefs.value.rideHeight, set: v => (prefs.value.rideHeight = v) })
const springFront = computed({ get: () => prefs.value.springFront, set: v => (prefs.value.springFront = v) })
const springRear = computed({ get: () => prefs.value.springRear, set: v => (prefs.value.springRear = v) })
const damper = computed({ get: () => prefs.value.damper, set: v => (prefs.value.damper = v) })
const arb = computed({ get: () => prefs.value.arb, set: v => (prefs.value.arb = v) })
const brakeBias = computed({ get: () => prefs.value.brakeBias, set: v => (prefs.value.brakeBias = v) })
const masterCyl = computed({ get: () => prefs.value.masterCyl, set: v => (prefs.value.masterCyl = v) })
const diffPreload = computed({ get: () => prefs.value.diffPreload, set: v => (prefs.value.diffPreload = v) })
const finalDrive = computed({ get: () => prefs.value.finalDrive, set: v => (prefs.value.finalDrive = v) })

watch(prefs, val => {
  try { localStorage.setItem(LS_KEY, JSON.stringify(val)) } catch { /* quota: ignore */ }
}, { deep: true })

// ── bridge health ───────────────────────────────────────────────────────────
const bridgeOk = computed(() => bridgeStore.health !== null && bridgeStore.healthError === null)

onMounted(() => {
  if (!bridgeStore.health && !bridgeStore.isPolling) {
    bridgeStore.startPolling()
  }
  fetchCars()
})

// ── helpers ─────────────────────────────────────────────────────────────────
const rotateValue = (
  model: { value: number },
  options: Array<{ id: number; label: string }>,
  dir: number
) => {
  const idx = options.findIndex(o => o.id === model.value)
  const next = (idx + dir + options.length) % options.length
  model.value = options[next].id
  audio.playSfx('cursor_move')
}

useKeyboard((e: KeyboardEvent) => {
  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }
  if (e.key === '4') { audio.playSfx('cursor_move'); activeTab.value = 3; return }
  if (e.key === '5') { audio.playSfx('cursor_move'); activeTab.value = 4; return }

  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  }
})

const labelOf = (
  options: Array<{ id: number; label: string }>,
  value: number,
): string => options.find(o => o.id === value)?.label ?? '—'

const fmtBitrate = (bps: number | null | undefined): string => {
  if (!bps && bps !== 0) return '—'
  if (bps >= 1_000_000) return `${(bps / 1_000_000).toFixed(bps % 1_000_000 ? 2 : 0)} MBIT/S`
  if (bps >= 1_000) return `${(bps / 1_000).toFixed(0)} KBIT/S`
  return `${bps} BIT/S`
}
</script>

<template>
  <PageShell
    title="CAR SETUP"
    :hints="['1-5 · TAB', '◀ ▶ TAP TO TUNE', 'B · BACK']"
    bg="neutral"
    :show-heading="false"
  >
    <div class="setup-root flex flex-col h-full w-full gap-[1vmin]">

      <CyberTabs
        v-model="activeTab"
        :tabs="[...TAB_LABELS]"
        class="mx-2 shrink-0"
      />

      <div class="flex-1 min-h-0 mx-2 overflow-hidden">

        <!-- CAR (REAL — sourced from /cars → data/cars/*.yaml) -->
        <CyberPanel v-show="activeTab === 0" class="h-full flex flex-col gap-[1.2vmin] p-[2vmin] overflow-y-auto">
          <!-- Error / loading states -->
          <div v-if="carsLoading" class="p-2 border border-ui-info/40 bg-ui-info/5 text-small text-ui-info tracking-widest uppercase shrink-0">
            LOADING CAR CONFIG…
          </div>
          <div v-else-if="carsError" class="p-2 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-widest uppercase shrink-0">
            CAR CONFIG UNAVAILABLE — BRIDGE OFFLINE?
            <div class="text-ui-bad/70 normal-case tracking-normal mt-1">{{ carsError }}</div>
            <CyberBox interactive class="inline-block mt-2 p-2 min-w-[44px] min-h-[44px]" @click="fetchCars">RETRY</CyberBox>
          </div>
          <div v-else-if="!loadedCar" class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-widest uppercase shrink-0">
            NO CAR YAML FOUND IN data/cars/
          </div>

          <template v-else>
            <div class="p-2 border shrink-0 text-small tracking-widest uppercase"
                 :class="loadedCar.loaded
                   ? 'border-ui-good/40 bg-ui-good/5 text-ui-good'
                   : 'border-ui-warn/40 bg-ui-warn/5 text-ui-warn'">
              {{ loadedCar.loaded ? 'LOADED BY BRIDGE' : 'NOT LOADED — BRIDGE USING DIFFERENT CONFIG' }}
            </div>

            <!-- Identity -->
            <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
              IDENTITY
            </div>
            <div class="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-small">
              <div><span class="text-slate uppercase tracking-widest">MAKE</span> <span class="text-fg">{{ loadedCar.make || '—' }}</span></div>
              <div><span class="text-slate uppercase tracking-widest">MODEL</span> <span class="text-fg">{{ loadedCar.model || '—' }}</span></div>
              <div><span class="text-slate uppercase tracking-widest">CHASSIS</span> <span class="text-fg">{{ loadedCar.chassis || '—' }}</span></div>
              <div><span class="text-slate uppercase tracking-widest">YEAR</span> <span class="text-fg">{{ loadedCar.year ?? '—' }}</span></div>
              <div class="col-span-2"><span class="text-slate uppercase tracking-widest">ENGINE</span> <span class="text-fg">{{ loadedCar.engine || '—' }}</span></div>
              <div v-if="loadedCar.notes" class="col-span-2 text-slate normal-case tracking-normal mt-1 leading-snug">
                {{ loadedCar.notes }}
              </div>
            </div>

            <!-- CAN pipeline -->
            <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0 mt-2">
              CAN PIPELINE
            </div>
            <div class="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-small">
              <div><span class="text-slate uppercase tracking-widest">DASH</span> <span class="text-fg">{{ loadedCar.dash_logger?.make || '—' }} {{ loadedCar.dash_logger?.model || '' }}</span></div>
              <div><span class="text-slate uppercase tracking-widest">BUS</span> <span class="text-fg">{{ fmtBitrate(loadedCar.can_bus?.bitrate_bps) }} · {{ loadedCar.can_bus?.frame_format || '—' }}</span></div>
              <div><span class="text-slate uppercase tracking-widest">FRAMES</span> <span class="text-fg">{{ loadedCar.frame_count ?? 0 }}</span></div>
              <div><span class="text-slate uppercase tracking-widest">CHANNELS</span> <span class="text-fg">{{ loadedCar.channel_count ?? 0 }}</span></div>
              <div class="col-span-2 text-slate normal-case tracking-normal text-small/snug">
                {{ loadedCar.dash_logger?.protocol || '' }}
              </div>
            </div>

            <!-- Channel list -->
            <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0 mt-2">
              CHANNELS ({{ loadedCar.channels?.length ?? 0 }})
            </div>
            <div class="font-mono text-small grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-0.5">
              <div v-for="ch in loadedCar.channels ?? []" :key="`${ch.frame_id}/${ch.name}`" class="truncate">
                <span class="text-slate">{{ ch.frame_id }}</span>
                <span class="text-fg/80 ml-1">{{ ch.name }}</span>
                <span v-if="ch.rate_hz" class="text-slate/60 ml-1">{{ ch.rate_hz }}Hz</span>
              </div>
            </div>
          </template>
        </CyberPanel>

        <!-- AERO -->
        <CyberPanel v-show="activeTab === 1" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div v-if="!bridgeOk" class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-widest uppercase shrink-0">
            DATA UNAVAILABLE — BRIDGE OFFLINE
          </div>
          <div class="p-2 border border-ui-info/40 bg-ui-info/5 text-small text-ui-info tracking-widest uppercase shrink-0">
            LOCAL PREF — STORED IN THIS BROWSER. NOT SENT TO THE BRIDGE OR TO THE CAR.
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            AERO
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(splitter, splitterOptions, 1)">
            <CyberValuePicker
              label="SPLITTER"
              :value="labelOf(splitterOptions, splitter)"
              :focused="false"
              :editing="true"
              label-width="clamp(80px,20vw,160px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(splitter, splitterOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(splitter, splitterOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(wing, aeroOptions, 1)">
            <CyberValuePicker
              label="REAR WING"
              :value="labelOf(aeroOptions, wing)"
              :focused="false"
              :editing="true"
              label-width="clamp(80px,20vw,160px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(wing, aeroOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(wing, aeroOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(aero, aeroOptions, 1)">
            <CyberValuePicker
              label="OVERALL AERO"
              :value="labelOf(aeroOptions, aero)"
              :focused="false"
              :editing="true"
              label-width="clamp(80px,20vw,160px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(aero, aeroOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(aero, aeroOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(rideHeight, rideHeightOptions, 1)">
            <CyberValuePicker
              label="RIDE HEIGHT"
              :value="labelOf(rideHeightOptions, rideHeight)"
              :focused="false"
              :editing="true"
              label-width="clamp(80px,20vw,160px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(rideHeight, rideHeightOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(rideHeight, rideHeightOptions, 1)">▶</CyberBox>
          </div>

          <div class="mt-auto pt-[1vmin] border-t border-slate/40 shrink-0 text-small text-slate uppercase tracking-widest leading-relaxed">
            PROJECTION DISABLED — NO REAL SETUP-IMPACT MODEL WIRED.
          </div>
        </CyberPanel>

        <!-- SUSPENSION -->
        <CyberPanel v-show="activeTab === 2" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div v-if="!bridgeOk" class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-widest uppercase shrink-0">
            DATA UNAVAILABLE — BRIDGE OFFLINE
          </div>
          <div class="p-2 border border-ui-info/40 bg-ui-info/5 text-small text-ui-info tracking-widest uppercase shrink-0">
            LOCAL PREF — STORED IN THIS BROWSER. NOT SENT TO THE BRIDGE OR TO THE CAR.
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            SPRINGS &amp; DAMPERS
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(springFront, springOptions, 1)">
            <CyberValuePicker
              label="SPRING (FRONT)"
              :value="labelOf(springOptions, springFront)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(springFront, springOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(springFront, springOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(springRear, springOptions, 1)">
            <CyberValuePicker
              label="SPRING (REAR)"
              :value="labelOf(springOptions, springRear)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(springRear, springOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(springRear, springOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(damper, damperOptions, 1)">
            <CyberValuePicker
              label="DAMPER CLICKS"
              :value="labelOf(damperOptions, damper)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(damper, damperOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(damper, damperOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(arb, arbOptions, 1)">
            <CyberValuePicker
              label="ANTI-ROLL BAR"
              :value="labelOf(arbOptions, arb)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(arb, arbOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(arb, arbOptions, 1)">▶</CyberBox>
          </div>

          <div class="mt-auto pt-[1vmin] border-t border-slate/40 shrink-0 text-small text-slate uppercase tracking-widest leading-relaxed">
            BALANCE: STIFFER FRONT → MORE UNDERSTEER · STIFFER REAR → MORE OVERSTEER.
          </div>
        </CyberPanel>

        <!-- BRAKES -->
        <CyberPanel v-show="activeTab === 3" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div v-if="!bridgeOk" class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-widest uppercase shrink-0">
            DATA UNAVAILABLE — BRIDGE OFFLINE
          </div>
          <div class="p-2 border border-ui-info/40 bg-ui-info/5 text-small text-ui-info tracking-widest uppercase shrink-0">
            LOCAL PREF — STORED IN THIS BROWSER. NOT SENT TO THE BRIDGE OR TO THE CAR.
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            BRAKES
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(brakeBias, brakeBiasOptions, 1)">
            <CyberValuePicker
              label="BRAKE BIAS"
              :value="labelOf(brakeBiasOptions, brakeBias)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(brakeBias, brakeBiasOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(brakeBias, brakeBiasOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(masterCyl, masterCylOptions, 1)">
            <CyberValuePicker
              label="MASTER CYL"
              :value="labelOf(masterCylOptions, masterCyl)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(masterCyl, masterCylOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(masterCyl, masterCylOptions, 1)">▶</CyberBox>
          </div>

          <div class="mt-auto pt-[1vmin] border-t border-slate/40 shrink-0 text-small text-slate uppercase tracking-widest leading-relaxed">
            PROJECTION DISABLED — NO REAL SETUP-IMPACT MODEL WIRED.
          </div>
        </CyberPanel>

        <!-- DRIVETRAIN -->
        <CyberPanel v-show="activeTab === 4" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div v-if="!bridgeOk" class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-widest uppercase shrink-0">
            DATA UNAVAILABLE — BRIDGE OFFLINE
          </div>
          <div class="p-2 border border-ui-info/40 bg-ui-info/5 text-small text-ui-info tracking-widest uppercase shrink-0">
            LOCAL PREF — STORED IN THIS BROWSER. NOT SENT TO THE BRIDGE OR TO THE CAR.
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            DRIVETRAIN
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(diffPreload, diffOptions, 1)">
            <CyberValuePicker
              label="DIFF PRELOAD"
              :value="labelOf(diffOptions, diffPreload)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(diffPreload, diffOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(diffPreload, diffOptions, 1)">▶</CyberBox>
          </div>

          <div class="flex items-center gap-3 cursor-pointer min-h-[44px]" @click="rotateValue(finalDrive, ratioOptions, 1)">
            <CyberValuePicker
              label="FINAL DRIVE"
              :value="labelOf(ratioOptions, finalDrive)"
              :focused="false"
              :editing="true"
              label-width="clamp(100px,22vw,180px)"
              class="flex-1"
            />
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(finalDrive, ratioOptions, -1)">◀</CyberBox>
            <CyberBox interactive class="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center" @click.stop="rotateValue(finalDrive, ratioOptions, 1)">▶</CyberBox>
          </div>

          <div class="mt-auto pt-[1vmin] border-t border-slate/40 shrink-0 text-small text-slate uppercase tracking-widest leading-relaxed">
            TIGHTER DIFF → MORE TRACTION OUT OF SLOW CORNERS · TALLER RATIO → HIGHER TOP SPEED, SLOWER ACCEL.
          </div>
        </CyberPanel>

      </div>
    </div>
  </PageShell>
</template>

<style scoped>
.setup-root {
  min-height: 0;
}
</style>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import CyberDataGrid from '@/shared/ui/core/CyberDataGrid.vue'
import CyberGauge from '@/shared/ui/core/CyberGauge.vue'
import { useCoachStore } from '@/entities/coach/model/coachStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { bridge } from '@/shared/api/bridge'

const props = defineProps<{
  state: Record<string, string | number>
}>()

const coach = useCoachStore()
const session = useSessionStore()

// /session/<sid>/capabilities returns the set of signals the current
// session's telemetry pipeline produces. The shape isn't strictly typed
// on the bridge so we treat it as an opaque object and use Object.keys
// for membership checks. When no session is active this stays null and
// every agent renders ✗.
interface CapabilitiesResponse {
  signals?: string[] | Record<string, unknown>
  [k: string]: unknown
}
const capabilities = ref<CapabilitiesResponse | null>(null)
const capabilitiesError = ref<string | null>(null)

onMounted(async () => {
  // Coach agents are global to the bridge (AGENT_REGISTRY) — fetch once.
  coach.fetchAgents()
  // Capabilities are per-session; only fetch when one is active.
  const sid = session.activeSessionId
  if (!sid) return
  try {
    capabilities.value = await bridge.get<CapabilitiesResponse>(`/session/${sid}/capabilities`)
  } catch (e: any) {
    capabilitiesError.value = e?.message ?? String(e)
  }
})

const capabilitySignalNames = computed<Set<string>>(() => {
  const c = capabilities.value
  if (!c) return new Set()
  if (Array.isArray(c.signals)) return new Set(c.signals.map(s => s.toLowerCase()))
  if (c.signals && typeof c.signals === 'object') {
    return new Set(Object.keys(c.signals).map(s => s.toLowerCase()))
  }
  // Fall back to the top-level keys of the response — older bridge builds
  // returned the capability map at the root.
  return new Set(Object.keys(c).map(s => s.toLowerCase()))
})

interface AgentPill {
  name: string
  ok: boolean
}

// Each coach agent has a `role` that hints at the signal it consumes.
// We do a name-substring match against the capabilities set: if the
// agent's name or role tokens appear in the signal set, it's ready.
// This is the most honest mapping we can do without a per-agent
// "required_signals" field on /coach/agents (which the bridge doesn't
// expose yet). If the session has no capabilities response at all, we
// render every agent as ✗ rather than ✓ — never lie that signals exist.
const agentPills = computed<AgentPill[]>(() => {
  const sigs = capabilitySignalNames.value
  return coach.agents.map((a) => {
    const haystack = (a.name + ' ' + a.role).toLowerCase()
    let ok = false
    if (sigs.size > 0) {
      for (const s of sigs) {
        if (s && haystack.includes(s)) { ok = true; break }
      }
    }
    return { name: a.name, ok }
  })
})

const engineItems = computed(() => [
  { label: 'GEAR', value: props.state.gear },
  { label: 'OIL', value: props.state.oil, unit: '°C' },
  { label: 'COOLANT', value: props.state.coolant, unit: '°C' },
  { label: 'FUEL', value: props.state.fuel, unit: '%' },
])

const dynamicsItems = computed(() => [
  { label: 'STEER', value: props.state.steer, unit: '°' },
  { label: 'G-LAT', value: props.state.glat, unit: 'g' },
  { label: 'G-LONG', value: props.state.glong, unit: 'g' },
  { label: 'COMBO', value: props.state.gcombo, unit: 'g' },
])
</script>

<template>
  <div class="live-car-state text-body font-ui flex flex-col gap-4">
    <!-- Hero Numbers -->
    <div class="flex justify-between items-end mb-2 bg-charcoal p-[clamp(8px,2vmin,16px)] border border-slate shadow-inner">
      <div class="flex flex-col">
        <span class="text-silver tracking-widest text-small">RPM</span>
        <span class="text-[clamp(24px,5vmin,36px)] font-bold font-mono leading-none text-white drop-shadow-[2px_2px_0_#000]">{{ state.rpm }}</span>
      </div>
      <div class="flex flex-col text-right">
        <span class="text-silver tracking-widest text-small">SPEED</span>
        <span class="text-[clamp(24px,5vmin,36px)] font-bold font-mono leading-none text-ui-good drop-shadow-[2px_2px_0_#000]">{{ state.speed }}<span class="text-small text-silver ml-1">km/h</span></span>
      </div>
    </div>

    <div>
      <div class="mb-1 text-silver tracking-wider font-bold text-small border-b border-slate pb-1">POWERTRAIN</div>
      <CyberDataGrid :items="engineItems" :columns="2" />
    </div>

    <div>
      <div class="mb-1 text-silver tracking-wider font-bold text-small border-b border-slate pb-1 mt-2">DYNAMICS</div>
      <CyberDataGrid :items="dynamicsItems" :columns="2" />
    </div>

    <div>
      <div class="mb-1 text-silver tracking-wider font-bold text-small border-b border-slate pb-1 mt-2">DRIVER INPUTS</div>
      <div class="flex flex-col gap-2 mt-2">
        <div class="flex items-center gap-2">
          <span class="w-[clamp(60px,15vw,100px)] text-silver text-[clamp(10px,2.5vmin,14px)] font-bold">THROTTLE</span>
          <CyberGauge :value="state.throttle" variant="good" class="flex-grow" />
          <span class="w-[40px] text-right text-ui-good font-mono text-[clamp(10px,2.5vmin,16px)]">{{ state.throttle }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-[clamp(60px,15vw,100px)] text-silver text-[clamp(10px,2.5vmin,14px)] font-bold">BRAKE</span>
          <CyberGauge :value="state.brake" variant="bad" class="flex-grow" />
          <span class="w-[40px] text-right text-ui-bad font-mono text-[clamp(10px,2.5vmin,16px)]">{{ state.brake }}</span>
        </div>
      </div>
    </div>

    <div class="coaches-available pt-2 border-t border-slate border-dashed mt-2">
      <div class="mb-2 text-silver tracking-wider font-bold text-small">AVAILABLE COACHES</div>

      <div v-if="coach.agentsLoading" class="text-small text-slate tracking-widest uppercase animate-pulse">
        loading coaches…
      </div>
      <div v-else-if="coach.agentsError" class="text-small text-ui-bad tracking-widest uppercase">
        DATA UNAVAILABLE
      </div>
      <div v-else-if="agentPills.length === 0" class="text-small text-slate tracking-widest uppercase">
        NO COACHES LOADED
      </div>
      <div v-else class="grid grid-cols-2 gap-x-2 gap-y-1 text-small">
        <div v-for="p in agentPills" :key="p.name"
             class="flex items-center gap-2"
             :class="p.ok ? 'text-ui-good' : 'text-ui-bad'">
          <span :class="p.ok ? 'text-ui-good' : 'text-ui-bad'">{{ p.ok ? '✓' : '✗' }}</span>
          {{ p.name }}<span v-if="!p.ok" class="text-slate text-tiny ml-1">(no signal)</span>
        </div>
      </div>
    </div>
  </div>
</template>

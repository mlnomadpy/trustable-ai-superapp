<!--
  SimulatorBadge.vue

  Shows a small "SIM" pill in the status bar whenever the bridge reports
  it's running its own synthetic AiM MXP simulator (`python -m pitwall
  --simulate`). Reads from useBridgeStore — the field comes from /health
  under `simulator.running`.

  Purpose: prevent the driver mistaking a synthetic session for a real
  one during dev / demos. The badge is intentionally noisy (yellow,
  pulsing) so it's hard to miss but small enough not to take attention
  during driving.
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useBridgeStore } from '@/shared/api/bridgeStore'

const bridge = useBridgeStore()

const isSimulating = computed(() => Boolean(bridge.health?.simulator?.running))

const tooltip = computed(() => {
  const sim = bridge.health?.simulator
  if (!sim?.running) return ''
  const parts: string[] = ['Bridge is running its own synthetic simulator.']
  if (sim.lap_seconds) parts.push(`Lap: ${sim.lap_seconds.toFixed(0)} s`)
  if (sim.speed_x && sim.speed_x !== 1) parts.push(`Speed: ${sim.speed_x.toFixed(2)}×`)
  return parts.join('\n')
})
</script>

<template>
  <span
    v-if="isSimulating"
    class="sim-badge"
    :title="tooltip"
    aria-label="Simulator is running"
  >SIM</span>
</template>

<style scoped>
.sim-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-ui-warn, #f5a623);
  color: var(--color-ink, #0b0c10);
  font-family: var(--font-ui);
  font-weight: 900;
  font-size: clamp(8px, 1.4vmin, 12px);
  line-height: 1;
  letter-spacing: 0.12em;
  padding: 2px 6px;
  border-radius: 2px;
  box-shadow: 0 0 8px var(--color-ui-warn, rgba(245, 166, 35, 0.6));
  animation: sim-pulse 1.4s steps(2) infinite;
}

@keyframes sim-pulse {
  0%   { opacity: 0.7; }
  100% { opacity: 1; }
}
</style>

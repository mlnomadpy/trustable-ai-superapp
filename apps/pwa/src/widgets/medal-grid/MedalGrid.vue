<script setup lang="ts">
import CyberBox from '@/shared/ui/core/CyberBox.vue'
import CyberMedal from '@/shared/ui/core/CyberMedal.vue'

interface Medal {
  id: string
  tier: string
  name: string
  desc: string
  unlocked: boolean
}

const props = defineProps<{
  medals: Medal[]
  cursorIndex: number
  /**
   * Optional honest-failure surface for callers. When set, the grid
   * shows a real error panel instead of the "unavailable" placeholder.
   * Consumers should pass `medalStore.error` here.
   */
  error?: string | null
  /**
   * Optional: when true, force the "MEDALS UNAVAILABLE" empty state
   * even if `medals` is non-empty (e.g. stale-cache scenarios).
   * Consumers should pass `medalStore.endpointMissing` here.
   */
  endpointMissing?: boolean
}>()

defineEmits<{
  (e: 'select', index: number): void
}>()
</script>

<template>
  <!-- ERROR — surfaces a real bridge malfunction explicitly. -->
  <div
    v-if="props.error"
    class="medal-empty-state"
  >
    <span class="medal-empty-title text-ui-bad">MEDALS UNAVAILABLE</span>
    <span class="medal-empty-sub text-ui-bad/80 normal-case">{{ props.error }}</span>
  </div>

  <!-- ENDPOINT MISSING / empty response — backend not wired yet. -->
  <div
    v-else-if="props.endpointMissing || !props.medals || props.medals.length === 0"
    class="medal-empty-state"
  >
    <span class="medal-empty-title text-ui-warn">MEDALS UNAVAILABLE</span>
    <span class="medal-empty-sub text-ui-warn/90">Backend not implemented</span>
    <span class="medal-empty-foot text-slate normal-case">
      No <span class="font-mono text-silver">/medals</span> endpoint on the bridge yet.
    </span>
  </div>

  <!-- Normal grid. -->
  <div v-else class="medal-grid-container">
    <CyberBox
      v-for="(m, i) in props.medals"
      :key="m.id"
      variant="ink"
      border="slate"
      :selected="cursorIndex === i"
      class="medal-cell"
      :class="[
        !m.unlocked ? 'locked' : '',
        cursorIndex === i ? 'focused' : ''
      ]"
      @click="$emit('select', i)"
    >
      <CyberMedal
        :tier="(m.tier as any)"
        :unlocked="m.unlocked"
      />
    </CyberBox>
  </div>
</template>

<style scoped>
.medal-grid-container {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: clamp(4px, 1vmin, 8px);
  align-content: start;
  overflow-y: auto;
  padding-bottom: clamp(4px, 1vmin, 8px);
  min-height: 0;
  height: 100%;
  scrollbar-width: none;
}

.medal-grid-container::-webkit-scrollbar { display: none; }

.medal-cell {
  position: relative;
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.medal-cell.focused {
  transform: scale(1.08);
  box-shadow:
    0 0 0 2px var(--color-ui-good),
    0 0 12px rgba(78, 205, 196, 0.4);
  z-index: 2;
}

.medal-cell.locked {
  opacity: 0.4;
}

/* Empty / error state — fits inside the panel without breaking flex layout. */
.medal-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(4px, 1vmin, 10px);
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: clamp(8px, 2vmin, 18px);
  text-align: center;
}

.medal-empty-title {
  font-family: var(--font-title);
  font-size: clamp(12px, 2.6vmin, 20px);
  letter-spacing: 0.18em;
  font-weight: 700;
}

.medal-empty-sub {
  font-family: var(--font-ui);
  font-size: clamp(10px, 2vmin, 15px);
  letter-spacing: 0.12em;
  font-weight: 700;
  text-transform: uppercase;
  max-width: 32ch;
  line-height: 1.4;
}

.medal-empty-foot {
  font-family: var(--font-ui);
  font-size: clamp(9px, 1.8vmin, 13px);
  max-width: 36ch;
  line-height: 1.4;
}
</style>

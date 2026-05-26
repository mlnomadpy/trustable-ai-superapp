<script setup lang="ts">
import StatusBar from '@/widgets/status-bar/StatusBar.vue'
import HintBar from '@/widgets/hint-bar/HintBar.vue'
import type { HintAction } from '@/widgets/hint-bar/HintBar.vue'
import PageHeading from '@/shared/ui/PageHeading.vue'
import CyberBackground from '@/shared/ui/core/CyberBackground.vue'

interface Props {
  title?: string
  subtitle?: string
  hints?: string[]
  actions?: HintAction[]
  bg?: 'default' | 'warm' | 'cool' | 'danger' | 'neutral'
  bgVariant?: 'grid' | 'landscape' | 'stars'
  showHeading?: boolean
  headingAlign?: 'center' | 'left'
  statusExtra?: string
  hideStatus?: boolean
  performanceMode?: boolean
}

withDefaults(defineProps<Props>(), {
  hints: () => [],
  actions: () => [],
  bg: 'default',
  bgVariant: 'grid',
  showHeading: true,
  headingAlign: 'center',
  hideStatus: false,
  performanceMode: false
})

const emit = defineEmits<{
  (e: 'action', action: HintAction): void
}>()
</script>

<template>
  <div class="viewport pixelated relative w-full h-full bg-ink text-silver overflow-hidden font-ui" role="application" :aria-label="title ?? 'Pitwall'">
    <StatusBar v-if="!hideStatus" :extra="statusExtra" />

    <CyberBackground v-if="!performanceMode" :variant="bgVariant" :color="bg" />

    <div class="shell-content">
      <!-- Heading -->
      <div class="stagger-1">
        <slot name="heading">
          <PageHeading
            v-if="showHeading && title"
            :title="title"
            :subtitle="subtitle"
            :align="headingAlign"
            class="mb-[1.5vh]"
          />
        </slot>
      </div>

      <!-- Main page content -->
      <div class="stagger-2 flex-grow min-h-0 flex flex-col" role="main">
        <slot></slot>
      </div>

      <!-- Floating content above HintBar (e.g. CoachFloat) -->
      <div class="stagger-3" aria-live="polite">
        <slot name="floating"></slot>
      </div>
    </div>

    <HintBar :hints="hints" :actions="actions" @action="(a) => emit('action', a)" />
  </div>
</template>


<style scoped>
.shell-content {
  position: relative;
  z-index: 1;
  padding-top: calc(max(var(--safe-top), 32px) + var(--space-md));
  padding-left: calc(var(--safe-left) + var(--space-md));
  padding-right: calc(var(--safe-right) + var(--space-md));
  padding-bottom: calc(max(var(--safe-bottom), 28px) + var(--space-md));
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

</style>

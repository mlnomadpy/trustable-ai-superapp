<script setup lang="ts">
const props = defineProps<{
  tabs: readonly string[]
  modelValue: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
  (e: 'change', value: number): void
}>()

const selectTab = (index: number) => {
  if (props.modelValue !== index) {
    emit('update:modelValue', index)
    emit('change', index)
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    selectTab((props.modelValue + 1) % props.tabs.length)
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    selectTab((props.modelValue - 1 + props.tabs.length) % props.tabs.length)
  }
}
</script>

<template>
  <div 
    class="cyber-tabs"
    role="tablist"
    tabindex="0"
    @keydown="handleKeydown"
  >
    <div 
      v-for="(t, i) in tabs" 
      :key="t"
      class="cyber-tab"
      role="tab"
      :aria-selected="modelValue === i"
      :tabindex="modelValue === i ? 0 : -1"
      :class="modelValue === i ? 'tab-active' : 'tab-default'"
      @click="selectTab(i)"
    >
      <span v-if="modelValue === i" class="text-ui-good mr-[4px]" aria-hidden="true">▶</span>
      {{ t }}
    </div>
  </div>
</template>

<style scoped>
.cyber-tabs {
  display: flex;
  border: 2px solid var(--color-slate);
  background-color: var(--color-charcoal);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.cyber-tabs::-webkit-scrollbar { display: none; }

.cyber-tabs:focus-visible {
  outline: 2px solid var(--color-ui-good);
  outline-offset: 2px;
}

.cyber-tab {
  padding: var(--space-xs, clamp(2px, 0.5vmin, 4px)) var(--space-md, clamp(8px, 2vmin, 16px));
  min-height: var(--touch-target-min);
  font-size: clamp(10px, 2.3vmin, 20px);
  white-space: nowrap;
  cursor: pointer;
  transition: all var(--duration-fast, 150ms) ease;
  user-select: none;
  -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
}

.tab-active {
  background-color: var(--color-ink);
  color: var(--color-ui-good);
  font-weight: bold;
  box-shadow: inset 0 -3px 0 var(--color-ui-good);
}

.tab-default {
  color: var(--color-slate);
}

.tab-default:hover {
  color: var(--color-silver);
  background-color: color-mix(in srgb, var(--color-ink) 80%, transparent);
}
</style>

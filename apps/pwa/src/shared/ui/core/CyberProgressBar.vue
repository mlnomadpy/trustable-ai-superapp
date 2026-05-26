<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: number // 0 to 100
  focused: boolean
  editing: boolean
  labelWidth?: string
}>()

const renderBar = computed(() => {
  const filled = Math.round(props.value / 5)
  return '█'.repeat(filled) + '░'.repeat(20 - filled)
})
</script>

<template>
  <div class="flex items-center mt-1 mb-1">
    <span 
      :style="{ width: labelWidth || 'clamp(60px,15vw,120px)' }" 
      class="inline-block"
      :class="focused ? 'text-white' : 'text-silver'"
    >
      <span v-if="focused" class="text-ui-good">▶ </span>{{ label }}
    </span>
    <span class="font-mono text-ui-good" :class="editing && focused ? 'animate-pulse' : ''">
      {{ renderBar }}
    </span>
    <span class="w-[clamp(30px,8vw,60px)] text-right font-mono">{{ value }}%</span>
  </div>
</template>

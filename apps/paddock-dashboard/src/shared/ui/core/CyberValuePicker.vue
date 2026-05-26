<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  focused: boolean
  editing: boolean
  labelWidth?: string
}>()
</script>

<template>
  <div 
    class="flex items-center mt-1 mb-1"
    role="spinbutton"
    :aria-valuenow="typeof value === 'number' ? value : undefined"
    :aria-valuetext="String(value)"
    :aria-label="label"
  >
    <span 
      :style="{ width: labelWidth || 'clamp(60px,15vw,120px)' }" 
      class="inline-block"
      :class="focused ? 'text-white' : 'text-silver'"
    >
      <span v-if="focused" class="text-ui-good">▶ </span>{{ label }}
    </span>
    <span 
      class="font-bold text-ui-good transition-all duration-100" 
      :class="editing && focused ? 'animate-pulse scale-110 ml-2' : ''"
    >
      <span v-if="editing && focused">◀ </span>{{ value }}<span v-if="editing && focused"> ▶</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import CyberButton from '@/shared/ui/core/CyberButton.vue'

export interface TileData {
  id: string
  title: string
  subText: string
  route: string
  disabled?: boolean
}

defineProps<{
  tile: TileData
  focused: boolean
}>()

const emit = defineEmits<{
  (e: 'select'): void
  (e: 'hover'): void
}>()
</script>

<template>
  <CyberButton
    :disabled="tile.disabled"
    fluid
    variant="secondary"
    :active="focused"
    :subText="tile.subText"
    @click="!tile.disabled && emit('select')"
    @mouseover="!tile.disabled && emit('hover')"
    class="w-full h-[clamp(60px,12vh,100px)]"
  >
    <template #icon>
      <span v-if="focused" class="cursor-bounce text-ui-warn absolute left-[10px]">▶</span>
    </template>
    <div class="relative z-10">{{ tile.title }}</div>
    
    <div v-if="tile.disabled" class="absolute inset-0 bg-ink/60 z-20 flex items-center justify-center">
      <span class="bg-charcoal px-2 py-1 text-xs border border-slate flex items-center gap-1 shadow-md">
        <span>🔒</span> LOCKED
      </span>
    </div>
  </CyberButton>
</template>

<style scoped>
/* Scoped styles removed because PixelButton handles the full presentation now */
.cursor-bounce {
  text-shadow: 1px 1px 0 #0d0d12;
  font-size: clamp(14px, 3vmin, 20px);
}
</style>


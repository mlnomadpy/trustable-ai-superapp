<script setup lang="ts">
import type { SaveSlot } from '@/shared/types/save'
import CyberButton from '@/shared/ui/core/CyberButton.vue'
import CyberAvatar from '@/shared/ui/core/CyberAvatar.vue'

defineProps<{
  slotId: 1 | 2 | 3
  slotData: SaveSlot | null
  focused: boolean
  deleteProgress?: number
}>()

const emit = defineEmits<{ (e: 'select'): void; (e: 'delete'): void }>()
</script>

<template>
  <CyberButton 
    fluid 
    complex
    size="sm"
    :variant="slotData ? 'primary' : 'dark'" 
    :active="focused"
    @click="emit('select')"
    :class="[
      'mb-2 w-full',
      slotData ? 'h-20' : 'h-12 border-2 border-dashed border-slate opacity-60'
    ]"
  >
    <div class="slot-content w-full flex items-center justify-between text-left relative z-10 px-2 pointer-events-none">
      
      <!-- Filled slot -->
      <template v-if="slotData">
        <div class="flex items-center gap-3 w-full">
          <div class="cursor-col shrink-0 w-4 text-white text-body font-bold text-center">
            <span v-if="focused" class="animate-pulse">▶</span>
          </div>
          
          <div class="avatar-col shrink-0">
            <CyberAvatar :sheet="slotData.driverAvatar || 'avatar_a'" size="sm" />
          </div>
          
          <div class="info-col flex-1 flex flex-col justify-center gap-[2px]">
            <div class="slot-label text-small text-white/70 tracking-[0.1em]">SLOT {{ slotId }}</div>
            <div class="driver-name text-title text-white font-bold leading-none">
              {{ slotData.driverName.toUpperCase() }}
            </div>
            <div class="driver-meta text-small text-white/80">
              LV.{{ slotData.level }} · {{ slotData.skillLevel.toUpperCase() }} · {{ slotData.car }}
            </div>
          </div>
          
          <div class="time-col shrink-0 text-right pr-4 flex flex-col items-end justify-center">
            <span class="last-played text-small text-white/60 font-mono">{{ new Date(slotData.lastPlayedAt).toLocaleDateString() }}</span>
            
            <div v-if="deleteProgress !== undefined && deleteProgress > 0" class="mt-1 w-20 h-3 bg-charcoal border border-slate overflow-hidden relative">
              <div class="h-full bg-ui-bad transition-all duration-75" :style="{ width: `${deleteProgress}%` }"></div>
              <span class="absolute inset-0 text-[8px] font-black text-white text-center leading-3 drop-shadow-[1px_1px_0_#000]">HOLD TO DELETE</span>
            </div>

          </div>
        </div>
      </template>
      
      <!-- Empty slot -->
      <template v-else>
        <div class="flex items-center gap-3 w-full py-2">
          <div class="cursor-col shrink-0 w-4 text-white text-body font-bold text-center">
            <span v-if="focused" class="animate-pulse">▶</span>
          </div>
          <div class="empty-content flex flex-col justify-center gap-1">
            <div class="slot-label text-small text-white/50 tracking-[0.1em]">SLOT {{ slotId }}</div>
            <div class="new-driver-text text-title-sm text-white/80 animate-pulse font-bold">NEW DRIVER</div>
          </div>
        </div>
      </template>
      
    </div>
  </CyberButton>
</template>

<style scoped>
/* Layout styling handled by tailwind classes inside PixelButton */
</style>


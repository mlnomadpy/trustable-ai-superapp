<script setup lang="ts">
import Sprite from '@/entities/coach/Sprite.vue'
import CyberTile from '@/shared/ui/core/CyberTile.vue'
import { computed } from 'vue'

interface Props {
  id: string
  name?: string
  levelReq?: number
  focused?: boolean
  selected?: boolean
  locked?: boolean
  // Optional flag if we only want the portrait (e.g. for dialogue)
  portraitOnly?: boolean
  animation?: string
  paused?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  name: '',
  levelReq: 0,
  focused: false,
  selected: false,
  locked: false,
  portraitOnly: false,
  animation: '',
  paused: false
})

const computedAnimation = computed(() => {
  if (props.animation) return props.animation
  if (props.locked) return 'idle'
  if (props.focused) return 'talk'
  return 'idle'
})
</script>

<template>
  <div class="coach-card font-ui" :class="{ 'portrait-mode': portraitOnly, 'is-focused': focused, 'is-locked': locked, 'is-selected': selected }">
    <CyberTile 
      :focused="focused && !locked"
      :locked="locked"
      :showKerb="selected"
      variant="glass"
      class="card-container"
    >
      <!-- Optional Name -->
      <div v-if="!portraitOnly && name" class="coach-name" :class="{ 'text-ui-good': selected }">
        {{ name }}
      </div>
      
      <!-- Portrait Area -->
      <div class="sprite-area">
        <div class="sprite-backdrop"></div>
        <Sprite :sheet="id" :animation="computedAnimation" :paused="paused" class="coach-sprite" />
      </div>
      
      <!-- Status Badge -->
      <template v-if="!portraitOnly">
        <div v-if="locked" class="status-badge badge-locked">
          <span class="lock-icon">🔒</span> LV {{ levelReq }}
        </div>
        <div v-else-if="selected" class="status-badge badge-active">
          ACTIVE
        </div>
      </template>
    </CyberTile>
  </div>
</template>

<style scoped>
.coach-card {
  transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.coach-card.is-focused {
  transform: translateY(-4px) scale(1.05);
  z-index: 10;
}

.card-container {
  width: clamp(72px, 16vmin, 140px);
  height: clamp(72px, 16vmin, 140px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0;
  position: relative;
  overflow: hidden;
}

.portrait-mode .card-container {
  width: 100%;
  height: 100%;
  min-width: 40px;
  min-height: 40px;
  border-radius: 4px; /* Slightly different styling for dialogue portraits */
}

.coach-name {
  position: absolute;
  top: clamp(4px, 1vmin, 8px);
  font-size: clamp(9px, 2.2vmin, 18px);
  color: var(--color-silver);
  font-weight: bold;
  z-index: 2;
  letter-spacing: 0.1em;
  text-shadow: 0 2px 4px rgba(0,0,0,0.8);
}

.sprite-area {
  position: absolute;
  inset: clamp(12px, 3vmin, 24px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1;
}

.portrait-mode .sprite-area {
  inset: 0; /* Fill container in portrait mode */
}

.sprite-backdrop {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, rgba(42, 161, 152, 0.15) 0%, transparent 70%);
  border-radius: 50%;
  transform: scale(0.8);
  transition: all 0.3s ease;
}

.is-focused .sprite-backdrop {
  transform: scale(1.1);
  background: radial-gradient(circle at center, rgba(42, 161, 152, 0.3) 0%, transparent 80%);
}

.is-locked .sprite-backdrop {
  background: radial-gradient(circle at center, rgba(220, 50, 47, 0.1) 0%, transparent 70%);
}

.coach-sprite {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
  transition: filter 0.3s ease;
}

/* Make locked coaches look like silhouettes */
.is-locked .coach-sprite {
  filter: brightness(0) contrast(0) opacity(0.6) drop-shadow(0 0 0 transparent);
}

.status-badge {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  text-align: center;
  font-size: clamp(8px, 1.8vmin, 14px);
  font-weight: bold;
  padding: clamp(2px, 0.5vh, 6px) 0;
  z-index: 3;
  backdrop-filter: blur(4px);
  border-top: 1px solid rgba(255,255,255,0.1);
}

.badge-locked {
  background: rgba(13, 13, 18, 0.95);
  color: var(--color-ui-bad);
}

.lock-icon {
  font-size: 0.9em;
  margin-right: 2px;
}

.badge-active {
  background: rgba(42, 161, 152, 0.2);
  color: var(--color-ui-good);
  text-shadow: 0 0 8px rgba(42, 161, 152, 0.8);
  border-top-color: rgba(42, 161, 152, 0.5);
  box-shadow: inset 0 2px 8px rgba(42, 161, 152, 0.2);
}
</style>

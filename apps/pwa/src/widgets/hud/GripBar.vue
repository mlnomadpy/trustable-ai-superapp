<script setup lang="ts">
defineProps<{
  pct: number
  isOver: boolean
  label: string
}>()
</script>

<template>
  <div class="grip-bar-container">
    <div class="grip-bar">
      <div 
        class="fill" 
        :class="isOver ? 'fill-over' : 'fill-normal'"
        :style="{ height: `${Math.min(100, Math.max(0, pct))}%` }"
      ></div>
    </div>
    <div class="grip-label text-small flex flex-col items-center">
      <span class="text-slate">{{ label }}</span>
      <span class="text-white font-bold text-num">{{ Math.floor(pct) }}%</span>
    </div>
  </div>
</template>

<style scoped>
.grip-bar-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(4px, 1vmin, 10px);
  font-family: var(--font-ui);
}

.grip-bar {
  width: clamp(16px, 3.5vw, 32px);
  height: clamp(80px, 20vh, 180px);
  border: 2px solid var(--color-slate);
  background: var(--color-ink);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 2px;
  position: relative;
  overflow: hidden;
}

/* Inner glow at top */
.grip-bar::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 30%;
  background: linear-gradient(180deg, rgba(0,0,0,0.3) 0%, transparent 100%);
  pointer-events: none;
}

.fill {
  width: 100%;
  transition: height 0.05s linear;
  will-change: height;
  position: relative;
  /* Texture pattern for colorblind clarity */
  background-image: repeating-linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.1),
    rgba(255, 255, 255, 0.1) 2px,
    transparent 2px,
    transparent 4px
  );
}

.fill-normal {
  background-color: var(--color-ui-good);
  box-shadow: 0 0 10px rgba(78, 205, 196, 0.4);
}

.fill-over {
  background-color: var(--color-ui-bad);
  box-shadow: 0 0 10px rgba(255, 71, 87, 0.4);
}


.grip-label {
  color: var(--color-silver);
  text-align: center;
}
</style>

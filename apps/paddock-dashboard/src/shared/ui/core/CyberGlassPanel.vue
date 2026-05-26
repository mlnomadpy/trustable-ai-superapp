<script setup lang="ts">
// A premium, glassmorphic container that elevates the UI above basic panels.
</script>

<template>
  <div class="glass-panel">
    <slot></slot>
  </div>
</template>

<style scoped>
.glass-panel {
  position: relative;
  background: rgba(10, 10, 15, 0.4);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  overflow: hidden;
}

.glass-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0) 100%);
  z-index: 0;
}

/* Ensure contents stay above the subtle gradient */
.glass-panel > * {
  position: relative;
  z-index: 1;
}
</style>

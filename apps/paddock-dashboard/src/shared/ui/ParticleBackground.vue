<script setup lang="ts">
import { computed } from 'vue'

const numParticles = 20
const colors = ['#ff4757', '#4ecdc4', '#c44569', '#feca57', '#45b7d1', '#ff6b6b']

const particles = computed(() => {
  return Array.from({ length: numParticles }).map((_, i) => {
    return {
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      color: colors[Math.floor(Math.random() * colors.length)],
      delay: Math.random() * 5,
      animClass: `anim-var-${Math.floor(Math.random() * 3) + 1}`,
      size: Math.random() * 3 + 2 // 2 to 5px
    }
  })
})
</script>

<template>
  <div class="floating-particles">
    <div 
      v-for="p in particles" 
      :key="p.id" 
      class="particle" 
      :class="p.animClass"
      :style="{
        left: p.x + '%',
        top: p.y + '%',
        backgroundColor: p.color,
        boxShadow: `0 0 10px ${p.color}`,
        animationDelay: p.delay + 's',
        width: p.size + 'px',
        height: p.size + 'px'
      }"
    ></div>
  </div>
</template>

<style scoped>
.floating-particles {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
  overflow: hidden;
  mix-blend-mode: screen;
}

.particle {
  position: absolute;
  border-radius: 50%;
}

.anim-var-1 { animation: float-particle-1 8s infinite ease-in-out alternate; }
.anim-var-2 { animation: float-particle-2 10s infinite ease-in-out alternate-reverse; }
.anim-var-3 { animation: float-particle-3 6s infinite ease-in-out alternate; }

@keyframes float-particle-1 {
  0% { transform: translateY(0) scale(1); opacity: 0.2; }
  100% { transform: translateY(-30px) scale(1.5); opacity: 0.8; }
}
@keyframes float-particle-2 {
  0% { transform: translateY(0) translateX(0) scale(0.8); opacity: 0.1; }
  100% { transform: translateY(20px) translateX(20px) scale(1.2); opacity: 0.9; }
}
@keyframes float-particle-3 {
  0% { transform: translateY(0) translateX(0) scale(1); opacity: 0.3; }
  100% { transform: translateY(-15px) translateX(-15px) scale(1.8); opacity: 0.7; }
}
</style>

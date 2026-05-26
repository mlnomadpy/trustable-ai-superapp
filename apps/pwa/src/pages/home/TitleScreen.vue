<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import Sprite from '@/entities/coach/Sprite.vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'
import CyberBackground from '@/shared/ui/core/CyberBackground.vue'

const router = useRouter()
const audio = useAudioStore()

const pressed = ref(false)
const showWanderer = ref(false)
const wandererX = ref(-100)

// Track all timeouts to prevent leaks on unmount
const timeouts: number[] = []
const track = (id: number) => { timeouts.push(id); return id }

const handleStart = (e?: Event) => {
  if (e && e instanceof KeyboardEvent && !['Enter', ' ', 'a', 'A'].includes(e.key)) {
    return
  }
  
  if (pressed.value) return
  
  pressed.value = true
  audio.playSfx('cursor_select')
  
  // Wipe to save select
  track(window.setTimeout(() => {
    router.push('/save')
  }, 400))
}

const animateWanderer = () => {
  showWanderer.value = true
  wandererX.value = -100
  
  track(window.setTimeout(() => {
    wandererX.value = window.innerWidth + 100
  }, 100))
  
  track(window.setTimeout(() => {
    animateWanderer()
  }, 30000))
}

useKeyboard((e: KeyboardEvent) => {
  handleStart(e)
})

onMounted(() => {
  audio.playSfx('boot_chime')
  audio.playMusic('title_loop')
  
  track(window.setTimeout(() => {
    animateWanderer()
  }, 5000))
})

onUnmounted(() => {
  timeouts.forEach(clearTimeout)
})
</script>

<template>
  <div class="viewport relative w-full h-full overflow-hidden font-ui cursor-pointer select-none" @click="handleStart">
    
    <CyberBackground variant="landscape" />

    <!-- CRT scanlines -->
    <div class="crt-overlay"></div>

    <!-- Main UI -->
    <div class="absolute inset-0 z-10 flex flex-col items-center justify-center">
      
      <!-- Title block -->
      <div class="title-block text-center mb-[2vh]">
        <!-- Main title with glow -->
        <h1 class="title-text font-title font-bold text-white tracking-[0.2em] relative">
          PITWALL
        </h1>
        
        <!-- Decorative separator -->
        <div class="separator mx-auto my-[1.5vh]"></div>
        
        <!-- Subtitle badge -->
        <div class="subtitle-badge inline-flex items-center gap-[1.5vw]">
          <span class="badge-dot"></span>
          <span class="text-body text-ui-good font-bold tracking-[0.4em] uppercase">AI Racing Coach</span>
          <span class="badge-dot"></span>
        </div>
      </div>
      
      <!-- Press Start -->
      <div class="press-start-block mt-[6vh] transition-opacity duration-200" :class="{ 'opacity-0': pressed }">
        <CyberButton @click.stop="handleStart" size="lg" variant="primary" class="animate-pulse">
          <template #icon>
            <span class="mr-2">▶</span>
          </template>
          START
        </CyberButton>
      </div>
      
    </div>
    
    <!-- Wanderer Sprite -->
    <div class="absolute z-20 transition-transform duration-[8000ms] linear" 
         :style="{ transform: `translateX(${wandererX}px)`, bottom: 'calc(22vh + 2px)' }">
      <Sprite v-if="showWanderer" sheet="trod" animation="idle" class="scale-150" />
    </div>

    <!-- Footer -->
    <p class="absolute bottom-[1.5vh] left-0 w-full text-center text-small text-slate z-30 tracking-widest">
      SONOMA RACEWAY · 2026 EDITION
    </p>

    <!-- Flash overlay when pressed -->
    <div v-if="pressed" class="absolute inset-0 z-50 bg-white animate-flash pointer-events-none"></div>
  </div>
</template>

<style scoped>
/* ── Title text ── */
.title-text {
  font-size: clamp(32px, 12vmin, 80px);
  line-height: 1;
  text-shadow:
    0 0 20px rgba(200, 120, 106, 0.6),    /* warm dusk glow */
    0 0 60px rgba(200, 120, 106, 0.2),
    0 2px 0 #0d0d12,                        /* crisp drop shadow */
    0 4px 0 rgba(0,0,0,0.3);
  color: #f8f8f0;
}

/* ── Separator ── */
.separator {
  width: clamp(80px, 30vw, 320px);
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(200, 120, 106, 0.6) 20%,
    rgba(42, 161, 152, 0.8) 50%,
    rgba(200, 120, 106, 0.6) 80%,
    transparent
  );
}

/* ── Subtitle badge ── */
.badge-dot {
  width: clamp(4px, 0.8vmin, 8px);
  height: clamp(4px, 0.8vmin, 8px);
  background: var(--color-ui-good);
  border-radius: 50%;
  box-shadow: 0 0 6px rgba(42, 161, 152, 0.8);
}

.subtitle-badge {
  padding: clamp(2px, 0.5vh, 6px) clamp(8px, 2vw, 24px);
  border: 1px solid rgba(42, 161, 152, 0.3);
  border-radius: 2px;
  background: rgba(26, 29, 46, 0.7);
}

/* ── Press Start ── */
.press-start-text {
  animation: press-start-glow 1.5s steps(2) infinite;
}

@keyframes press-start-glow {
  0%, 100% {
    opacity: 0.5;
    text-shadow: 0 0 4px rgba(110, 118, 134, 0.3);
  }
  50% {
    opacity: 1;
    text-shadow: 0 0 12px rgba(110, 118, 134, 0.6), 0 0 30px rgba(110, 118, 134, 0.2);
  }
}

/* ── Flash ── */
.animate-flash {
  animation: flash 0.4s steps(2) forwards;
}

@keyframes flash {
  0% { opacity: 0.9; }
  100% { opacity: 0; }
}
</style>

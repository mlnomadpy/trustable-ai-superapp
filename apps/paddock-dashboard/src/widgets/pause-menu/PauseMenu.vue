<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { usePauseStore } from '@/shared/lib/pauseStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const store = usePauseStore()

const items = ['RESUME', 'SETTINGS', 'END SESSION FOR THE DAY', 'QUIT TO TITLE']
const cursorIndex = ref(0)

watch(() => store.isVisible, (visible) => {
  if (visible) {
    cursorIndex.value = 0
    audio.playSfx('cursor_move') // sound for opening
  }
})

const handleKey = (e: KeyboardEvent) => {
  if (!store.isVisible) return

  // Stop propagation so other components don't react to key presses while paused
  e.stopPropagation()

  if (store.confirmingQuit) {
    if (e.key === 'y' || e.key === 'Y' || e.key === 'Enter') {
      audio.playSfx('cancel') // heavy
      store.closePause()
      save.activeSlotId = null
      router.push('/')
    } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'n' || e.key === 'N' || e.key === 'b') {
      store.confirmingQuit = false
      audio.playSfx('cursor_move')
    }
    return
  }

  if (e.key === 'ArrowDown') {
    cursorIndex.value = (cursorIndex.value + 1) % items.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursorIndex.value = (cursorIndex.value - 1 + items.length) % items.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter' || e.key === 'a') {
    const action = items[cursorIndex.value]
    if (action === 'RESUME') {
      audio.playSfx('cursor_select')
      store.closePause()
    } else if (action === 'SETTINGS') {
      audio.playSfx('cursor_select')
      store.closePause()
      router.push('/settings')
    } else if (action === 'END SESSION FOR THE DAY') {
      audio.playSfx('cursor_select')
      store.closePause()
      router.push('/end-of-day')
    } else if (action === 'QUIT TO TITLE') {
      audio.playSfx('error_quiet')
      store.confirmingQuit = true
    }
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    store.closePause()
  }
}

const triggerEnter = () => {
  handleKey(new KeyboardEvent('keydown', { key: 'Enter' }))
}

useKeyboard(handleKey)
</script>

<template>
  <Teleport to="body">
    <Transition name="pause-fade">
      <div v-if="store.isVisible" class="pause-backdrop pixelated font-ui">
        
        <div class="pause-panel pointer-events-auto">
          <!-- Top accent -->
          <div class="panel-accent-top"></div>
          
          <h2 class="pause-title text-title-lg text-white font-bold text-shadow-glow font-title">PAUSED</h2>
          <div class="pause-rule"></div>
          
          <ul class="pause-menu">
            <li 
              v-for="(item, i) in items" 
              :key="item"
              class="pause-item touch-target"
              :class="[
                cursorIndex === i ? 'item-focused' : 'item-default',
                { '!text-ui-bad text-shadow-glow': item === 'QUIT TO TITLE' && cursorIndex === i }
              ]"
              @click="cursorIndex === i ? triggerEnter() : (cursorIndex = i, audio.playSfx('cursor_move'))"
            >
              <span class="item-cursor" v-if="cursorIndex === i">▶</span>
              <span class="item-cursor item-invisible" v-else>&nbsp;</span>
              {{ item }}
            </li>
          </ul>

          <!--
            Plain status panel — not a coach moment. Pausing is a UI
            affordance, never routed through /coach/*. Don't synthesise
            coach dialogue here.
          -->
          <div
            v-if="store.confirmingQuit"
            class="pause-dialogue pause-status-panel pause-status-warn"
          >
            QUIT TO TITLE — unsaved laps will stay in the bridge. (Y/N)
          </div>
          <div
            v-else
            class="pause-dialogue pause-status-panel pause-status-info"
          >
            PAUSED
          </div>
          
          <!-- Bottom accent -->
          <div class="panel-accent-bottom"></div>
        </div>

        <div class="pause-hints text-small text-slate pointer-events-auto" v-if="!store.confirmingQuit">
          A · CONFIRM &nbsp;&nbsp; B · RESUME &nbsp;&nbsp; ESC · RESUME
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.pause-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(13, 13, 18, 0.7);
  backdrop-filter: blur(2px) brightness(0.6);
  -webkit-backdrop-filter: blur(2px) brightness(0.6);
  pointer-events: none;
}

.pause-panel {
  width: clamp(280px, 80vw, 560px);
  background: linear-gradient(
    180deg,
    rgba(42, 47, 66, 0.95) 0%,
    rgba(26, 29, 46, 0.98) 100%
  );
  border: 2px solid var(--color-slate);
  padding: clamp(20px, 4vh, 40px) clamp(16px, 4vw, 40px);
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  overflow: hidden;
  box-shadow:
    0 0 0 1px rgba(61, 68, 88, 0.5),
    0 8px 32px rgba(0, 0, 0, 0.5);
}

.panel-accent-top {
  position: absolute;
  top: 0;
  left: 10%;
  width: 80%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(110, 118, 134, 0.4), transparent);
}

.panel-accent-bottom {
  position: absolute;
  bottom: 0;
  left: 10%;
  width: 80%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(110, 118, 134, 0.3), transparent);
}

.pause-title {
  margin-bottom: clamp(4px, 1vh, 10px);
  letter-spacing: 0.15em;
}

.pause-rule {
  width: clamp(80px, 40%, 200px);
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-slate), transparent);
  margin-bottom: clamp(12px, 3vh, 28px);
}

.pause-menu {
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 2vh, 20px);
  width: 100%;
  max-width: clamp(200px, 60%, 400px);
  list-style: none;
  padding: 0;
  margin: 0 0 clamp(12px, 3vh, 24px);
}

.pause-item {
  display: flex;
  align-items: center;
  gap: clamp(6px, 1.5vw, 14px);
  font-size: clamp(12px, 3vmin, 24px);
  transition: color 0.1s ease;
}

.item-focused {
  color: white;
}

.item-default {
  color: var(--color-slate);
}

.item-cursor {
  color: var(--color-ui-good);
  font-size: clamp(10px, 2.5vmin, 20px);
  text-shadow: 0 0 6px rgba(42, 161, 152, 0.6);
  animation: cursor-bounce 0.25s steps(2) infinite;
  flex-shrink: 0;
  width: clamp(12px, 3vmin, 20px);
}

.item-invisible { visibility: hidden; }

@keyframes cursor-bounce {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(2px); }
}

.pause-dialogue {
  position: relative;
  bottom: auto;
  left: auto;
  width: 100%;
  padding: 0;
  margin-top: clamp(4px, 1vh, 10px);
}

.pause-status-panel {
  text-align: center;
  font-family: var(--font-ui);
  font-weight: 700;
  letter-spacing: 0.12em;
  padding: clamp(6px, 1.5vh, 12px) clamp(10px, 2vw, 20px);
  border: 1px solid var(--color-slate);
  background: rgba(13, 13, 18, 0.55);
  text-transform: uppercase;
  font-size: clamp(11px, 2.2vmin, 16px);
}

.pause-status-info { color: var(--color-silver); }
.pause-status-warn {
  color: var(--color-ui-warn);
  border-color: var(--color-ui-warn);
}

.pause-hints {
  margin-top: clamp(8px, 2vh, 16px);
  text-align: center;
  letter-spacing: 0.05em;
}

/* Transition */
.pause-fade-enter-active,
.pause-fade-leave-active {
  transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.pause-fade-enter-from,
.pause-fade-leave-to {
  transform: translateY(-12px);
  opacity: 0;
}
</style>

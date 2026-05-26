<script setup lang="ts">
import { onMounted } from 'vue'
import CoachCard from '@/shared/ui/CoachCard.vue'
import CoachVoiceButton from '@/widgets/coach-voice-button/CoachVoiceButton.vue'
import { useTypewriter } from '@/shared/lib/useTypewriter'
import { useKeyboard } from '@/shared/lib/useKeyboard'

const props = withDefaults(defineProps<{
  coachId: string
  emotion: string
  text: string
  compact?: boolean
  /** When true (default), render a mic FAB inside the speech bubble so the
   *  driver can reply by voice. Set false on dialogues that are pure
   *  narration (e.g. an opening cutscene where the user can't talk back). */
  voiceEnabled?: boolean
}>(), { voiceEnabled: true })

const emit = defineEmits<{ (e: 'done'): void }>()

const { displayedText, isTyping, start, complete } = useTypewriter()

onMounted(() => {
  start(props.text)
})

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    // Only intercept Enter — let Escape and other keys propagate to PauseMenu etc.
    e.stopPropagation()

    if (isTyping.value) {
      complete()
    } else {
      emit('done')
    }
  }
})

const handleClick = () => {
  if (isTyping.value) {
    complete()
  } else {
    emit('done')
  }
}
</script>

<template>
  <div class="dialogue-box pixelated" :class="{ compact }" @keydown.stop>
    <div class="dialogue-layout" @click="handleClick">
      <!-- Coach NPC — stands next to speech bubble -->
      <div class="npc-column">
        <div class="npc-character">
          <CoachCard 
            :id="coachId" 
            :animation="emotion || 'idle'" 
            :paused="!isTyping"
            portrait-only
          />
        </div>
        <div class="npc-shadow" aria-hidden="true"></div>
      </div>
      
      <!-- Speech bubble -->
      <div class="speech-bubble">
        <div class="speech-header">
          <span class="speaker-name">{{ coachId.toUpperCase() }}</span>
          <span v-if="isTyping" class="typing-dots" aria-label="typing">···</span>
        </div>
        <div class="dialogue-text text-body">
          {{ displayedText }}
          <span v-if="!isTyping" class="advance-indicator">▼</span>
        </div>
        <!-- Voice-reply affordance. Wired via the shared CoachVoiceButton
             widget which delegates to useVoiceConversation → coachStore.
             Click stops propagation so it doesn't also advance / complete
             the typewriter. Hidden while the typewriter is still running
             so the driver doesn't talk over the line they haven't heard. -->
        <div
          v-if="voiceEnabled && !isTyping"
          class="dialogue-voice-row"
          @click.stop
        >
          <CoachVoiceButton mode="toggle" position="inline" />
          <span class="dialogue-voice-hint">tap to reply</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialogue-box {
  position: absolute;
  /* Float above HintBar: HintBar height (calc(var(--safe-bottom) + 32px)) + gap */
  bottom: calc(var(--safe-bottom) + 36px + var(--space-sm));
  left: var(--safe-left);
  right: var(--safe-right);
  padding: 0 var(--space-md);
  z-index: var(--z-modal); /* Increased z-index to clear sticky footer */
  pointer-events: none;
}


.dialogue-box.compact {
  transform: scale(0.9);
  transform-origin: bottom left;
}

.dialogue-layout {
  display: flex;
  align-items: flex-end;
  gap: var(--space-xs);
  pointer-events: auto;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}

/* ── NPC Character Column ── */
.npc-column {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 2;
  margin-right: calc(-1 * var(--space-xs));
}

.npc-character {
  width: clamp(64px, 15vmin, 120px);
  height: clamp(64px, 15vmin, 120px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.6));
}

/* ── Speech Bubble ── */
.speech-bubble {
  flex: 1;
  border: 2px solid var(--color-slate);
  background-color: var(--color-ink);
  padding: var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  min-height: clamp(60px, 12vh, 100px);
  box-shadow: var(--shadow-hard);
  position: relative;
  clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
}


/* Speech tail pointing to NPC */
.speech-bubble::before {
  content: '';
  position: absolute;
  left: -8px;
  bottom: clamp(12px, 2.5vmin, 20px);
  width: 0;
  height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 8px solid var(--color-slate);
}

.speech-bubble::after {
  content: '';
  position: absolute;
  left: -5px;
  bottom: clamp(13px, 2.6vmin, 21px);
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-right: 6px solid var(--color-ink);
}

.speech-header {
  display: flex;
  align-items: center;
  gap: clamp(4px, 1vmin, 8px);
}

.speaker-name {
  font-size: clamp(9px, 2vmin, 16px);
  color: var(--color-ui-good);
  font-weight: bold;
  letter-spacing: 0.1em;
}

.typing-dots {
  color: var(--color-ui-info);
  animation: dots-blink 1s steps(3) infinite;
  font-size: 1.2em;
  letter-spacing: 2px;
}

.dialogue-text {
  color: var(--color-silver);
  flex: 1;
  line-height: 1.5;
}

.advance-indicator {
  color: var(--color-ui-info);
  margin-left: clamp(4px, 1vmin, 8px);
  animation: advance-blink 1s steps(2) infinite;
}

/* Voice reply row inside the speech bubble. The CoachVoiceButton sits
   here as an inline-positioned FAB; the hint label gives the driver a
   prompt that they can talk back. */
.dialogue-voice-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-top: var(--space-xs);
}
.dialogue-voice-hint {
  font-family: var(--font-mono);
  color: var(--color-slate);
  font-size: clamp(10px, 1.6vmin, 12px);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

@keyframes advance-blink {
  0%, 100% { opacity: 0; }
  50% { opacity: 1; }
}

@keyframes dots-blink {
  0% { opacity: 0.3; }
  50% { opacity: 1; }
  100% { opacity: 0.3; }
}
</style>

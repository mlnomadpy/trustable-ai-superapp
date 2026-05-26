import { ref, onUnmounted } from 'vue'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

export interface SequenceStep {
  phase: number
  timeMs: number
  sfx?: string
  callback?: () => void
}

export function useSequence(endPhase: number) {
  const phase = ref(0)
  const audio = useAudioStore()
  
  let sequenceTimeouts: number[] = []

  const addStep = (step: SequenceStep) => {
    const t = window.setTimeout(() => {
      phase.value = step.phase
      if (step.sfx) audio.playSfx(step.sfx)
      if (step.callback) step.callback()
    }, step.timeMs)
    sequenceTimeouts.push(t)
  }

  const addCustomInterval = (intervalMs: number, callback: () => boolean) => {
    const interval = window.setInterval(() => {
      const shouldClear = callback()
      if (shouldClear) clearInterval(interval)
    }, intervalMs)
    sequenceTimeouts.push(interval)
    return interval
  }

  const addDelay = (timeMs: number, callback: () => void) => {
    const t = window.setTimeout(callback, timeMs)
    sequenceTimeouts.push(t)
    return t
  }

  const skip = (customSkipLogic?: () => void) => {
    sequenceTimeouts.forEach(clearTimeout)
    sequenceTimeouts.forEach(clearInterval)
    sequenceTimeouts = []
    phase.value = endPhase
    if (customSkipLogic) {
      customSkipLogic()
    }
  }

  onUnmounted(() => {
    sequenceTimeouts.forEach(clearTimeout)
    sequenceTimeouts.forEach(clearInterval)
  })

  return {
    phase,
    addStep,
    addCustomInterval,
    addDelay,
    skip
  }
}

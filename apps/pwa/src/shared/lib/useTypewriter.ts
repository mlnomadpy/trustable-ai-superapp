import { ref, onUnmounted } from 'vue'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSaveStore } from '@/entities/save/model/saveStore'

export function useTypewriter(fallbackSpeedMs: number = 30) {
  const displayedText = ref('')
  const isTyping = ref(false)
  const audio = useAudioStore()
  const saveStore = useSaveStore()
  
  let typeInterval: number | undefined
  let fullText = ''

  const clear = () => {
    if (typeInterval) {
      clearInterval(typeInterval)
      typeInterval = undefined
    }
  }

  const start = (text: string) => {
    clear()
    fullText = text
    
    const speedPref = saveStore.activeSlot?.settings?.ux?.typewriterSpeed ?? 'normal'
    
    if (speedPref === 'off') {
      displayedText.value = fullText
      isTyping.value = false
      return
    }

    displayedText.value = ''
    isTyping.value = true
    
    const speedMap: Record<string, number> = { fast: 10, normal: 30, slow: 70 }
    const speedMs = speedMap[speedPref] ?? fallbackSpeedMs

    let i = 0
    typeInterval = window.setInterval(() => {
      if (i < fullText.length) {
        displayedText.value += fullText.charAt(i)
        if (i % 2 === 0) audio.playSfx('dialogue_blip')
        i++
      } else {
        clear()
        isTyping.value = false
      }
    }, speedMs)
  }


  const complete = () => {
    if (isTyping.value) {
      clear()
      displayedText.value = fullText
      isTyping.value = false
    }
  }

  onUnmounted(() => {
    clear()
  })

  return {
    displayedText,
    isTyping,
    start,
    complete
  }
}

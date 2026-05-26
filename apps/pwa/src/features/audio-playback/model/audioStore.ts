import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import { Howl } from 'howler'
import { useSaveStore } from '@/entities/save/model/saveStore'

export const useAudioStore = defineStore('audio', {
  state: () => ({
    sfx: markRaw(new Map<string, Howl>()),
    music: markRaw(new Map<string, Howl>()),
    voice: markRaw(new Map<string, Howl>()),
    ttsDucked: false,
    _duckUntil: 0
  }),
  actions: {
    playSfx(id: string) {
      const saveStore = useSaveStore()
      
      // Haptic Feedback for GBA-style tactility
      if (saveStore.activeSlot?.settings?.ux?.hapticFeedback) {
        try {
          if (id.includes('cursor_move')) {
            navigator.vibrate?.(5)
          } else if (id.includes('cursor_select') || id.includes('level_up')) {
            navigator.vibrate?.([10, 30])
          } else if (id.includes('cancel') || id.includes('error')) {
            navigator.vibrate?.(40)
          } else if (id.includes('goal_complete')) {
            navigator.vibrate?.([20, 10, 20])
          }
        } catch { /* Fail silently if vibration is blocked */ }
      }

      if (this.sfx.size > 50) {

        const firstKey = this.sfx.keys().next().value;
        if (firstKey) {
          this.sfx.get(firstKey)?.unload();
          this.sfx.delete(firstKey);
        }
      }
      let h = this.sfx.get(id)
      if (!h) {
        // We use dummy URLs; Howler will fail silently if the mp3 is missing
        h = new Howl({ src: [`/sfx/${id}.mp3`], volume: 0.3 })
        this.sfx.set(id, h)
      }
      h.play()
    },
    
    playMusic(track: string) {
      if (this.music.size > 10) {
        const firstKey = this.music.keys().next().value;
        if (firstKey && firstKey !== track) {
          this.music.get(firstKey)?.unload();
          this.music.delete(firstKey);
        }
      }
      let h = this.music.get(track)
      if (!h) {
        h = new Howl({ src: [`/music/${track}.mp3`], loop: true, volume: 0.15 })
        this.music.set(track, h)
      }
      
      this.music.forEach((m, k) => {
        if (k !== track && m.playing()) {
          m.fade(m.volume(), 0, 500)
          setTimeout(() => m.pause(), 500)
        }
      })
      
      if (!h.playing()) {
        h.play()
        h.fade(0, 0.15, 500)
      }
    },
    
    playVoice(coachId: string, phraseId: string, hintMs = 0) {
      const key = `${coachId}/${phraseId}`
      if (this.voice.size > 20) {
        const firstKey = this.voice.keys().next().value;
        if (firstKey && firstKey !== key) {
          this.voice.get(firstKey)?.unload();
          this.voice.delete(firstKey);
        }
      }
      let h = this.voice.get(key)
      if (!h) {
        h = new Howl({ src: [`/audio/coaches/${key}.mp3`], volume: 1.0 })
        this.voice.set(key, h)
      }
      
      this.duckMusic(true)
      const durationMs = hintMs || (h.duration() ? h.duration() * 1000 : 1500)
      this.duckTactical(true, durationMs)
      
      h.once('end', () => {
        this.duckMusic(false)
      })
      
      // Fade out all other voices quickly instead of hard stopping
      this.voice.forEach((v) => {
        if (v.playing()) {
          v.fade(v.volume(), 0, 100)
          setTimeout(() => v.stop(), 100)
        }
      })
      h.play()
    },
    
    duckMusic(ducked: boolean) {
      this.music.forEach(m => {
        if (m.playing()) {
          m.fade(m.volume(), ducked ? 0.05 : 0.15, 200)
        }
      })
    },
    
    duckTactical(ducked: boolean, holdMs = 0) {
      if (ducked) {
        this._duckUntil = Math.max(this._duckUntil, performance.now() + holdMs)
        this.ttsDucked = true
        // For actual implementation, this adjusts Web Audio API gain nodes
        setTimeout(() => this._maybeUnduck(), holdMs + 16)
      }
    },
    
    _maybeUnduck() {
      if (performance.now() >= this._duckUntil - 8) {
        this.ttsDucked = false
      }
    }
  }
})

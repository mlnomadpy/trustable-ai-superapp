import { defineStore } from 'pinia'

export interface CoachSpeaksState {
  isVisible: boolean
  coachId: string
  emotion: string
  title: string
  text: string
}

export const useCoachSpeaksStore = defineStore('coachSpeaks', {
  state: (): CoachSpeaksState => ({
    isVisible: false,
    coachId: 'trod',
    emotion: 'neutral',
    title: '',
    text: '',
  }),

  actions: {
    speak(opts: Omit<CoachSpeaksState, 'isVisible'>) {
      this.coachId = opts.coachId
      this.emotion = opts.emotion
      this.title = opts.title
      this.text = opts.text
      this.isVisible = true
    },

    dismiss() {
      this.isVisible = false
    }
  }
})

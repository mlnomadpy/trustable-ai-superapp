import { defineStore } from 'pinia'

export const usePauseStore = defineStore('pause', {
  state: () => ({
    isVisible: false,
    confirmingQuit: false
  }),
  actions: {
    togglePause() {
      this.isVisible = !this.isVisible
      this.confirmingQuit = false
    },
    closePause() {
      this.isVisible = false
      this.confirmingQuit = false
    }
  }
})

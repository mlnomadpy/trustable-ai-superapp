import { defineStore } from 'pinia'

export type TransitionDirection = 'right' | 'left' | 'up' | 'down' | 'fade-night' | null

const durationFor = (dir: TransitionDirection) => dir === 'fade-night' ? 1500 : 300

export const useTransitionStore = defineStore('transition', {
  state: () => ({
    direction: null as TransitionDirection,
    inProgress: false,
  }),
  actions: {
    async play(direction: NonNullable<TransitionDirection>) {
      this.direction = direction
      this.inProgress = true
      await new Promise(resolve => setTimeout(resolve, durationFor(direction)))
      this.inProgress = false
      this.direction = null
    }
  }
})

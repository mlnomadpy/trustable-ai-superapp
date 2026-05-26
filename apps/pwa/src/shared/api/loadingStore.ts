import { defineStore } from 'pinia'

export const useLoadingStore = defineStore('loading', {
  state: () => ({
    isLoading: false,
    message: '',
    source: '' as 'adk' | 'duckdb' | 'system' | ''
  }),
  actions: {
    start(message = '', source: 'adk' | 'duckdb' | 'system' | '' = 'system') {
      this.isLoading = true
      this.message = message
      this.source = source
    },
    stop() {
      this.isLoading = false
      this.message = ''
      this.source = ''
    }
  }
})

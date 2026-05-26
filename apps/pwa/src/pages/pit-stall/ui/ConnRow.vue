<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import CyberListRow from '@/shared/ui/core/CyberListRow.vue'

const props = defineProps<{
  title: string
  state: 'checking' | 'ok' | 'error' | 'pending'
  statusText?: string
  details: string[]
}>()

const frames = ['▒▒░', '▒░░', '░░░', '░▒▒', '░▒▒', '▒▒▒']
const animFrame = ref('▒▒▒')
let interval: number | null = null

watch(() => props.state, (newVal) => {
  if (newVal === 'checking') {
    let i = 0
    interval = window.setInterval(() => {
      animFrame.value = frames[i % frames.length]
      i++
    }, 150)
  } else {
    if (interval) clearInterval(interval)
    animFrame.value = ''
  }
}, { immediate: true })

onUnmounted(() => {
  if (interval) clearInterval(interval)
})
</script>

<template>
  <CyberListRow 
    :title="title"
    :detail="details[0]"
    :statusState="state"
    :statusText="statusText"
    :subLines="details.slice(1)"
  />
</template>

<style scoped>
</style>

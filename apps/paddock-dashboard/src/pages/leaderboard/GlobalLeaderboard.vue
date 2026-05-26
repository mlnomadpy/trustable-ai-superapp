<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useLeaderboardStore } from '@/entities/leaderboard/model/leaderboardStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberSkeleton from '@/shared/ui/core/CyberSkeleton.vue'
import CyberTag from '@/shared/ui/core/CyberTag.vue'
import ErrorBoundary from '@/shared/ui/ErrorBoundary.vue'

const router = useRouter()
const audio = useAudioStore()
const store = useLeaderboardStore()

const cursorIndex = ref(3) // Default to 'YOU'

onMounted(() => {
  store.fetchLeaderboard()
})

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    if (!store.isLoading && store.entries.length > 0) {
      cursorIndex.value = (cursorIndex.value + 1) % store.entries.length
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'ArrowUp') {
    if (!store.isLoading && store.entries.length > 0) {
      cursorIndex.value = (cursorIndex.value - 1 + store.entries.length) % store.entries.length
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage')
  }
})

const getRankColor = (rank: number) => {
  if (rank === 1) return 'text-rank-gold' // Gold
  if (rank === 2) return 'text-rank-silver' // Silver
  if (rank === 3) return 'text-rank-bronze' // Bronze
  return 'text-silver'
}
</script>

<template>
  <PageShell title="HIGH SCORES" :hints="['B · BACK', '▲ ▼ MOVE']" bg="neutral">
    <template #heading>
      <div class="heading-block mb-[1.5vh] text-center">
        <h1 class="text-title font-title text-ui-warn tracking-[0.2em] animate-pulse">RANKING</h1>
        <div class="heading-rule"></div>
      </div>
    </template>

    <CyberPanel class="flex-grow flex flex-col p-2 bg-ink border-slate overflow-hidden mx-2 pb-6">
      <ErrorBoundary>
        <div v-if="store.endpointMissing" class="flex-grow flex flex-col items-center justify-center gap-3 p-6 text-center">
          <span class="text-title font-title text-ui-warn tracking-widest">GLOBAL LEADERBOARD</span>
          <p class="text-body text-ui-warn/90 max-w-md leading-relaxed font-bold tracking-wider uppercase">
            Endpoint not yet available on bridge
          </p>
          <p class="text-body text-silver max-w-md leading-relaxed">
            Multi-driver benchmarking + privacy controls land post-Sonoma.
            For now your session-by-session times live in
            <span class="text-ui-good">LAP TIMES HALL</span> and
            <span class="text-ui-good">DRIVER EVOLUTION</span>.
          </p>
        </div>

        <div v-else-if="store.error" class="flex-grow flex flex-col items-center justify-center gap-3 p-6 text-center">
          <span class="text-title font-title text-ui-bad tracking-widest">LEADERBOARD UNAVAILABLE</span>
          <p class="text-body text-ui-bad/80 max-w-md leading-relaxed normal-case">{{ store.error }}</p>
        </div>

        <div v-else-if="store.isLoading" class="flex-grow flex flex-col items-center justify-center gap-4 p-4">
          <CyberSkeleton variant="row" :count="8" />
        </div>

        <table v-else class="w-full text-left font-mono text-body">
        <thead>
          <tr class="text-charcoal-light border-b border-charcoal">
            <th class="pb-2 w-10 text-center">RK</th>
            <th class="pb-2 w-16">NAME</th>
            <th class="pb-2">CAR</th>
            <th class="pb-2 text-right">TIME</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(entry, i) in store.entries"
            :key="`rank-${entry.rank}-${entry.initials}`"
            class="transition-colors border-b border-charcoal/30 cursor-pointer"
            :class="cursorIndex === i ? 'bg-charcoal text-white font-bold' : 'text-slate'"
            @click="cursorIndex = i; audio.playSfx('cursor_move')"
          >
            <td class="py-2 text-center" :class="getRankColor(entry.rank)">
              <span v-if="cursorIndex === i" class="text-ui-good mr-1 animate-pulse absolute -ml-4">▶</span>
              <CyberTag v-if="entry.rank <= 3" :variant="entry.rank === 1 ? 'warn' : entry.rank === 2 ? 'info' : 'slate'">{{ entry.rank < 10 ? '0' + entry.rank : entry.rank }}</CyberTag>
              <span v-else>{{ entry.rank < 10 ? '0' + entry.rank : entry.rank }}</span>
            </td>
            <td class="py-2" :class="getRankColor(entry.rank)">{{ entry.initials }}</td>
            <td class="py-2 truncate max-w-[80px]">{{ entry.car }}</td>
            <td class="py-2 text-right tracking-wider">{{ entry.time }}</td>
          </tr>
        </tbody>
      </table>
      
      <div class="flex-grow flex items-end justify-center pb-4 pointer-events-none mt-4">
        <span class="text-ui-warn text-title-sm font-bold tracking-[0.3em] animate-pulse">INSERT COIN</span>
      </div>
      </ErrorBoundary>
    </CyberPanel>
  </PageShell>
</template>

<style scoped>
/* No specific viewport styles, PageShell handles bounds */
</style>

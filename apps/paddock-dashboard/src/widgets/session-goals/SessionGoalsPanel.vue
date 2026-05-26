<script setup lang="ts">
import { onMounted } from 'vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberStatusIcon from '@/shared/ui/core/CyberStatusIcon.vue'
import ErrorBoundary from '@/shared/ui/ErrorBoundary.vue'
import { useQuestStore } from '@/entities/quest/model/questStore'

const store = useQuestStore()

interface Props {
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'ACTIVE GOALS (THIS SESSION)'
})

onMounted(() => {
  store.fetchQuests()
})

</script>

<template>
  <CyberPanel variant="glass" border="primary" class="goals-frame w-full h-full">
    <h2 class="section-label">{{ title }}</h2>
    
    <ErrorBoundary>
      <div v-if="store.isLoading" class="flex-grow flex items-center justify-center">
        <div class="text-ui-info text-small animate-pulse">SYNCING GOALS...</div>
      </div>
      <div
        v-else-if="store.error"
        class="flex-grow flex items-center justify-center text-center px-2"
      >
        <div class="text-ui-bad text-small tracking-widest uppercase max-w-[36ch]">
          GOALS UNAVAILABLE
          <div class="mt-1 text-slate text-tiny normal-case tracking-normal">
            {{ store.error }}
          </div>
        </div>
      </div>
      <div
        v-else-if="store.daily.length === 0"
        class="flex-grow flex items-center justify-center text-center px-2"
      >
        <div class="text-slate text-small tracking-widest uppercase max-w-[36ch]">
          NO ACTIVE QUESTS
          <div class="mt-1 text-slate/60 text-tiny normal-case tracking-normal">
            (No insights from this session yet.)
          </div>
        </div>
      </div>
      <div v-else class="goals-list flex flex-col gap-2">
        <div
          v-for="quest in store.daily"
          :key="quest.id"
          class="goal-row"
          :class="quest.completed ? 'goal-complete' : 'goal-pending'"
        >
          <!-- Status icon -->
          <CyberStatusIcon :status="quest.completed ? 'success' : 'pending'" />

          <span class="goal-name">{{ quest.title }}</span>
          <span class="goal-val font-nums">{{ quest.progress }} / {{ quest.target }}</span>
        </div>
      </div>
    </ErrorBoundary>
  </CyberPanel>
</template>

<style scoped>
.goals-frame {
  padding: clamp(8px, 2vmin, 16px);
  display: flex;
  flex-direction: column;
}

.section-label {
  font-family: var(--font-title);
  font-size: clamp(10px, 2.5vmin, 20px);
  color: var(--color-silver);
  margin-bottom: clamp(6px, 1.5vmin, 12px);
  border-bottom: 1px solid var(--color-slate);
  padding-bottom: 4px;
}

.goals-list {
  flex: 1;
  overflow-y: auto;
}

.goal-row {
  display: flex;
  align-items: center;
  gap: clamp(6px, 1.5vw, 14px);
  font-size: clamp(10px, 2.3vmin, 18px);
  margin-bottom: clamp(2px, 0.4vh, 5px);
  background: rgba(0, 0, 0, 0.2);
  padding: clamp(4px, 1vmin, 8px) clamp(8px, 1.5vmin, 12px);
  border-radius: 4px;
  border-left: 2px solid transparent;
  transition: border-color 0.2s ease, opacity 0.2s ease;
}

.goal-complete {
  border-left-color: var(--color-ui-good);
  color: var(--color-ui-good);
}

.goal-complete .goal-name {
  text-decoration: line-through;
  opacity: 0.7;
}

.goal-pending {
  color: var(--color-silver);
}

.goal-name { 
  flex: 1; 
  font-weight: bold;
  letter-spacing: 0.05em;
}

.goal-val { 
  flex: 0 0 auto; 
  text-align: right; 
  font-family: var(--font-nums, monospace);
  opacity: 0.8;
}
</style>

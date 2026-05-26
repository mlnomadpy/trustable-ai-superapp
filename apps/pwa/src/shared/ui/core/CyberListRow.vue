<script setup lang="ts">
import CyberBadge from '@/shared/ui/core/CyberBadge.vue'
interface Props {
  title: string
  detail?: string
  statusState?: 'checking' | 'ok' | 'error' | 'pending' | 'none'
  statusText?: string
  subLines?: string[]
  focused?: boolean
}

withDefaults(defineProps<Props>(), {
  statusState: 'none',
  subLines: () => [],
  focused: false
})
</script>

<template>
  <div class="cyber-list-row" :class="{ 'row-pending': statusState === 'pending', 'row-focused': focused }">
    <div class="icon-col">
      <slot name="icon">
        <span v-if="statusState === 'checking'" class="text-ui-info animate-pulse">▒▒</span>
        <span v-else-if="statusState === 'ok'" class="text-ui-good drop-shadow-[0_0_4px_rgba(78,205,196,0.6)]">✓</span>
        <span v-else-if="statusState === 'error'" class="text-ui-bad drop-shadow-[0_0_4px_rgba(255,71,87,0.6)]">✗</span>
        <span v-else class="text-slate">○</span>
      </slot>
    </div>
    
    <div class="main-col">
      <div class="row-header flex items-center">
        <span class="row-title">{{ title }}</span>
        <span v-if="detail" class="row-detail">{{ detail }}</span>
        
        <CyberBadge 
          v-if="statusState === 'ok'" 
          variant="good"
        >
          {{ statusText || 'OK' }}
        </CyberBadge>
        <CyberBadge 
          v-else-if="statusState === 'error'" 
          variant="bad"
        >
          FAIL
        </CyberBadge>
      </div>
      
      <div v-for="(line, i) in subLines" :key="i" class="row-sub">
        {{ line }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.cyber-list-row {
  display: flex;
  gap: clamp(6px, 1.5vw, 14px);
  font-size: clamp(10px, 2.3vmin, 20px);
  font-family: var(--font-ui);
  line-height: 1.4;
  margin-bottom: clamp(6px, 1.2vh, 12px);
  padding-bottom: clamp(4px, 0.8vh, 8px);
  border-bottom: 1px solid rgba(61, 68, 88, 0.2);
  transition: all 0.2s ease;
}

.cyber-list-row:hover {
  background: linear-gradient(90deg, rgba(78, 205, 196, 0.15) 0%, transparent 100%);
}

.row-focused {
  background: var(--color-charcoal);
  border-bottom-color: var(--color-ui-good);
}

.row-pending { opacity: 0.4; filter: grayscale(1); }

.icon-col {
  flex-shrink: 0;
  width: clamp(20px, 5vmin, 36px);
  text-align: center;
  font-size: clamp(11px, 2.5vmin, 22px);
}

.main-col { flex: 1; }

.row-header {
  display: flex;
  justify-content: space-between;
  gap: clamp(6px, 1.5vw, 14px);
}

.row-title {
  font-weight: bold;
  flex-shrink: 0;
  min-width: clamp(36px, 10vw, 72px);
  color: #fff;
}

.row-detail {
  flex: 1;
  color: var(--color-silver);
}

.row-sub {
  color: var(--color-slate);
  padding-left: clamp(36px, 10vw, 72px);
}
</style>

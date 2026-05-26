<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useNotificationsStore } from '@/shared/api/notificationStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberListRow from '@/shared/ui/core/CyberListRow.vue'
import CyberAvatar from '@/shared/ui/core/CyberAvatar.vue'
import CyberEmptyState from '@/shared/ui/core/CyberEmptyState.vue'
import CyberSkeleton from '@/shared/ui/core/CyberSkeleton.vue'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const store = useNotificationsStore()

// Bind the spinner directly to the store's `loading` flag. The store
// flips this around `bridge.get('/notifications')`.
const loading = computed(() => store.loading)

// `items` must be a computed so the template re-renders when polling
// refreshes the list (capturing `store.items` once at setup time would
// pin to the initial empty array).
const items = computed(() => store.items)

const cursorIndex = ref(0)

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'r' || e.key === 'R') {
    audio.playSfx('cursor_select')
    void store.fetch()
    return
  }

  if (items.value.length === 0) {
    if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
      audio.playSfx('cancel')
      router.back()
    }
    return
  }

  if (e.key === 'ArrowDown') {
    cursorIndex.value = (cursorIndex.value + 1) % items.value.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursorIndex.value = (cursorIndex.value - 1 + items.value.length) % items.value.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter' || e.key === 'a') {
    const item = items.value[cursorIndex.value]
    store.markRead(item.id)
    audio.playSfx('cursor_select')
    if (item.route) {
      router.push(item.route)
    }
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  } else if (e.key === ' ') { // Space for ◆
    store.markAllRead()
    audio.playSfx('cancel') // Using cancel as a "sweep" sound based on spec
  }
})

onMounted(() => {
  audio.playSfx('cursor_select') // Sound on enter
  // Begin polling /notifications every 30 s; this also kicks off the
  // initial fetch via the store action.
  store.startPolling()
})

onUnmounted(() => {
  store.stopPolling()
})

// Reference `save` so the import isn't pruned — kept available for
// future per-driver filtering of the notification feed.
void save

</script>

<template>
  <PageShell :hints="['A · OPEN', 'B · BACK', 'R · REFRESH', '◆ MARK ALL READ']" bg="neutral">
    <template #heading>
      <div class="heading-block mb-[1.5vh] text-center">
        <h1 class="text-title font-title text-silver tracking-[0.2em]">NOTIFICATIONS</h1>
        <span class="text-body" :class="store.unreadCount > 0 ? 'text-ui-warn font-bold' : 'text-slate'">{{ store.unreadCount }} new</span>
      </div>
    </template>

    <div
      v-if="store.error"
      class="mx-2 mb-2 p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase"
    >
      <div class="font-bold mb-1">NOTIFICATIONS UNAVAILABLE</div>
      <div class="text-ui-bad/80 normal-case tracking-normal">{{ store.error }}</div>
    </div>

    <template v-if="loading && items.length === 0">
      <CyberPanel class="flex-grow overflow-hidden flex flex-col p-4 bg-ink gap-2">
        <div class="text-small text-slate tracking-widest uppercase mb-2">LOADING NOTIFICATIONS…</div>
        <CyberSkeleton variant="row" :count="4" />
      </CyberPanel>
    </template>

    <template v-else-if="items.length > 0">
      <CyberPanel class="flex-grow overflow-hidden flex flex-col p-2 bg-ink">
        <div
          v-for="(item, i) in items"
          :key="item.id"
          :class="[
            cursorIndex === i ? 'bg-charcoal' : '',
            item.isRead ? 'opacity-50' : 'opacity-100'
          ]"
          class="px-2 pt-2 -mx-2 transition-opacity cursor-pointer"
          @click="cursorIndex = i; store.markRead(item.id); audio.playSfx('cursor_select'); if (item.route) router.push(item.route)"
        >
          <CyberListRow
            :title="item.title"
            :detail="item.timestamp"
            :status-state="item.kind === 'hardware-warning' ? 'error' : 'none'"
            :sub-lines="[item.subText]"
          >
            <template #icon v-if="cursorIndex === i">
              <span class="text-ui-good text-body animate-pulse">▶</span>
            </template>
          </CyberListRow>
        </div>
      </CyberPanel>
    </template>

    <template v-else-if="!store.error">
      <CyberEmptyState
        icon="🏁"
        title="No notifications"
        description="Drive a session to fill this up."
        class="flex-grow"
      />
    </template>
  </PageShell>
</template>

<style scoped>
/* No hardcoded viewport dimensions — fullscreen is enforced by global.css */
</style>

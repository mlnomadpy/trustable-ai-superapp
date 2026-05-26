<script setup lang="ts">
/**
 * QUEST LOG — tabbed layout for Pixel 10 landscape.
 *
 * Four tabs (1–4):
 *   1. QUESTS    — medals + session goals (live data via medalStore / SessionGoalsPanel)
 *   2. CODEX     — <CoachCodexMode> (/coach/concepts)
 *   3. ASK COACH — <AskCoachMode>   (/coach/ask + /coach/ask/stream — gated mount)
 *   4. SPONSORS  — <SponsorContracts /> rendered inline
 *
 * Per-mode child components own their own keybindings; the page only owns
 * the tab switcher (1–4) and global ESC/B back-nav. The Ask Coach SSE is
 * expensive — the component is only mounted (`v-if`) when its tab is
 * active so we don't open the stream on page mount.
 */
import { computed, ref, onMounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useMedalStore } from '@/entities/quest/model/medalStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberSplitView from '@/shared/ui/core/CyberSplitView.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import CoachCodexMode from './ui/CoachCodexMode.vue'
import AskCoachMode from './ui/AskCoachMode.vue'
import SessionGoalsPanel from '@/widgets/session-goals/SessionGoalsPanel.vue'
import MedalGrid from '@/widgets/medal-grid/MedalGrid.vue'
import SponsorContractsBody from './ui/SponsorContractsBody.vue'

const router = useRouter()
const audio = useAudioStore()
const medalStore = useMedalStore()

// SPONSORS shows as "COMING SOON" — the /sponsors backend isn't wired
// yet and the tab body renders an honest empty-state panel.
const TAB_LABELS = ['QUESTS', 'CODEX', 'ASK COACH', 'COMING SOON'] as const
const activeTab = ref(0)

// Medal-tier sub-tabs (only meaningful inside the QUESTS tab).
const medalTiers = ['ALL', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'RAINBOW']
const activeTier = ref(0)
const cursorIndex = ref(0)
const detailText = ref<string | null>(null)

onMounted(() => {
  medalStore.fetchMedals()
})

const filteredMedals = computed(() => medalStore.byTier(medalTiers[activeTier.value]))

const titleByTab = computed(() => {
  switch (activeTab.value) {
    case 0: return 'QUEST LOG'
    case 1: return 'COACH CODEX'
    case 2: return 'ASK THE COACH'
    case 3: return 'COMING SOON'
    default: return 'QUEST LOG'
  }
})

const hintsByTab = computed(() => {
  const tabs = ['1·QUESTS', '2·CODEX', '3·ASK', '4·SOON']
  switch (activeTab.value) {
    case 0: return [...tabs, 'A · DETAIL', 'SHIFT+◀ ▶ TIER', 'B · GARAGE']
    case 1: return [...tabs, 'A · PLAY', 'SHIFT+◀ ▶ COACH', 'B · GARAGE']
    case 2: return [...tabs, 'TYPE A QUESTION', 'B · GARAGE']
    case 3: return [...tabs, 'B · GARAGE']
    default: return tabs
  }
})

useKeyboard((e: KeyboardEvent) => {
  // Detail overlay swallows input until dismissed.
  if (detailText.value) return

  // Top-level tab switching — always available, before child components.
  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }
  if (e.key === '4') { audio.playSfx('cursor_move'); activeTab.value = 3; return }

  // Global back-nav.
  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage')
    return
  }

  // Quests tab owns its own medal-grid keyboard. Other tabs' child
  // components register their own useKeyboard handlers and gate via
  // `active` props (CoachCodexMode / AskCoachMode) or render-gating
  // (SponsorContracts is mounted only on tab 3).
  if (activeTab.value !== 0) return

  const max = filteredMedals.value.length
  if (!max) return
  const COLS = 4

  if (e.key === 'ArrowRight') {
    if (e.shiftKey) {
      activeTier.value = (activeTier.value + 1) % medalTiers.length
      cursorIndex.value = 0
      audio.playSfx('cursor_select')
    } else {
      cursorIndex.value = (cursorIndex.value + 1) % max
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'ArrowLeft') {
    if (e.shiftKey) {
      activeTier.value = (activeTier.value - 1 + medalTiers.length) % medalTiers.length
      cursorIndex.value = 0
      audio.playSfx('cursor_select')
    } else {
      cursorIndex.value = (cursorIndex.value - 1 + max) % max
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'ArrowDown') {
    cursorIndex.value = (cursorIndex.value + COLS) % max
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursorIndex.value = (cursorIndex.value - COLS + max) % max
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter' || e.key === 'a') {
    viewDetails()
  }
})

const viewDetails = (index = cursorIndex.value) => {
  cursorIndex.value = index
  const m = filteredMedals.value[index]
  if (m?.unlocked) {
    audio.playSfx('cursor_select')
    detailText.value = m.desc
  } else {
    audio.playSfx('cancel')
    detailText.value = 'Keep driving to unlock this.'
  }
}

const onCodexPlay = (phrase: any) => {
  detailText.value = phrase.text
}

const switchTier = (i: number) => {
  activeTier.value = i
  cursorIndex.value = 0
  audio.playSfx('cursor_select')
}
</script>

<template>
  <PageShell
    :title="titleByTab"
    :hints="hintsByTab"
    bg="warm"
    :show-heading="false"
  >
    <div class="questlog-root flex flex-col h-full w-full gap-[1vmin]">

      <!-- Top-level tab bar (1–4) -->
      <CyberTabs
        v-model="activeTab"
        :tabs="TAB_LABELS"
        class="mx-2 shrink-0"
      />

      <!-- Tab content -->
      <div class="flex-1 min-h-0 mx-2 overflow-hidden relative">

        <!-- TAB 1 · QUESTS -->
        <CyberPanel v-show="activeTab === 0" class="h-full p-[1.5vmin]">
          <CyberSplitView split="40-60" gap="sm" class="h-full">

            <template #left>
              <div class="flex flex-col gap-3 h-full">
                <SessionGoalsPanel class="flex-shrink-0" />

                <CyberPanel variant="solid" border="secondary" class="flex-1 flex flex-col justify-center">
                  <h2 class="section-label mb-2 text-ui-warn">MEDAL INTEL</h2>
                  <div class="medal-preview">
                    <span class="text-ui-good mr-[4px]">▶</span>
                    <span class="font-bold text-[clamp(14px,2.5vmin,22px)]">
                      {{ filteredMedals[cursorIndex]?.unlocked ? filteredMedals[cursorIndex]?.name : 'CLASSIFIED' }}
                    </span>
                    <p class="mt-2 text-slate text-[clamp(10px,2vmin,16px)]">
                      {{ filteredMedals[cursorIndex]?.unlocked
                        ? 'Press A to view full acquisition criteria.'
                        : 'Requirements unknown. Keep driving.' }}
                    </p>
                  </div>
                </CyberPanel>
              </div>
            </template>

            <template #right>
              <div class="flex flex-col h-full overflow-hidden">
                <CyberTabs :tabs="medalTiers" v-model="activeTier" @change="switchTier" class="mb-2" />

                <CyberPanel variant="glass" border="secondary" class="flex-1 flex flex-col overflow-hidden min-h-0">
                  <div class="flex justify-between items-end mb-2 border-b border-slate pb-1">
                    <h2 class="section-label m-0">MEDAL DATABASE</h2>
                    <span class="text-ui-good text-sm font-bold">
                      {{ medalStore.unlockedCount }} / {{ medalStore.totalCount }} UNLOCKED
                    </span>
                  </div>

                  <div
                    v-if="medalStore.endpointMissing"
                    class="flex-1 flex items-center justify-center text-center p-4"
                  >
                    <div class="text-ui-warn text-small tracking-widest uppercase max-w-[36ch]">
                      MEDALS UNAVAILABLE
                      <div class="mt-2 text-slate text-tiny normal-case tracking-normal">
                        Backend not implemented yet.
                      </div>
                    </div>
                  </div>
                  <div
                    v-else-if="medalStore.error"
                    class="flex-1 flex items-center justify-center text-center p-4"
                  >
                    <div class="text-ui-bad text-small tracking-widest uppercase max-w-[36ch]">
                      MEDALS UNAVAILABLE
                      <div class="mt-2 text-slate text-tiny normal-case tracking-normal">
                        {{ medalStore.error }}
                      </div>
                    </div>
                  </div>
                  <MedalGrid
                    v-else
                    :medals="filteredMedals"
                    :cursorIndex="cursorIndex"
                    @select="viewDetails"
                    class="flex-1"
                  />
                </CyberPanel>
              </div>
            </template>

          </CyberSplitView>
        </CyberPanel>

        <!-- TAB 2 · CODEX (mount-gated so its keyboard handler isn't stack-top
             when another tab is active and would otherwise swallow tab keys) -->
        <CyberPanel v-show="activeTab === 1" class="h-full p-[1.5vmin]">
          <CoachCodexMode v-if="activeTab === 1" :active="true" @play="onCodexPlay" class="h-full" />
        </CyberPanel>

        <!-- TAB 3 · ASK COACH (SSE-gated: mount only when active) -->
        <CyberPanel v-show="activeTab === 2" class="h-full p-[1.5vmin]">
          <AskCoachMode v-if="activeTab === 2" :active="true" class="h-full" />
        </CyberPanel>

        <!-- TAB 4 · SPONSORS — body extracted from /garage/sponsors page -->
        <CyberPanel v-show="activeTab === 3" class="h-full p-[1.5vmin] overflow-hidden">
          <SponsorContractsBody :active="activeTab === 3" :owns-back-nav="false" />
        </CyberPanel>

      </div>
    </div>

    <template #floating>
      <CoachFloat
        v-if="detailText"
        emotion="idle"
        :text="detailText"
        @done="detailText = null"
      />
    </template>
  </PageShell>
</template>

<style scoped>
.questlog-root {
  min-height: 0;
}

.section-label {
  font-family: var(--font-title);
  font-size: clamp(10px, 2.5vmin, 20px);
  color: var(--color-silver);
  letter-spacing: 0.1em;
}

.medal-preview {
  color: var(--color-silver);
}
</style>

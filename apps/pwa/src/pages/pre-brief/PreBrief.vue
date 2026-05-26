<script setup lang="ts">
/**
 * PRE-SESSION BRIEFING — tabbed layout for Pixel 10 landscape.
 *
 * Three tabs: BRIEF (coach narrative + preflight badges) · SETUP
 * (source + session pickers) · GOALS (checkboxes + confirm). The flat
 * stacked layout used to push the confirm button and weather badges
 * off the viewport in landscape.
 *
 * Phase state machine is preserved: 'loading' → 'briefing' → 'goals'.
 * The Brief tab is what advances the phase when the DialogueBox finishes.
 */
import { computed, ref, onMounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useCoachStore } from '@/entities/coach/model/coachStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import Frame from '@/shared/ui/core/Frame.vue'
import CyberCheckbox from '@/shared/ui/core/CyberCheckbox.vue'
import DialogueBox from '@/widgets/dialogue-box/DialogueBox.vue'
import SessionStartPicker from '@/widgets/session-start/SessionStartPicker.vue'
import BriefSourcePicker from '@/widgets/brief-source/BriefSourcePicker.vue'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const bridgeStore = useBridgeStore()
const coach = useCoachStore()
const sessionStore = useSessionStore()

const phase = ref<'loading' | 'briefing' | 'goals'>('loading')

const briefText = ref('')
const briefError = ref<string | null>(null)

const briefSourceSessionId = ref<string | null>(null)
const briefFetching = ref(false)

interface GoalSuggestion {
  id: string
  desc: string
  target: string
  selected: boolean
}
const suggestions = ref<GoalSuggestion[]>([])

const TAB_LABELS = ['BRIEF', 'SETUP', 'GOALS'] as const
const activeTab = ref(0)

async function loadBrief() {
  briefFetching.value = true
  briefError.value = null
  try {
    const sessionId =
      briefSourceSessionId.value
      ?? sessionStore.activeSessionId
      ?? undefined
    await coach.fetchBrief({
      driver: save.activeSlot?.driverName,
      sessionId,
    })

    if (coach.briefError) {
      briefError.value = coach.briefError
      briefText.value = ''
      suggestions.value = []
    } else if (coach.brief) {
      const narrative = coach.brief.narrative_md?.trim() ?? ''
      if (!narrative) {
        briefError.value = 'Coach brief unavailable — LLM offline or no narrative returned.'
        briefText.value = ''
      } else {
        briefText.value = narrative
      }
      suggestions.value = (coach.brief.focus ?? []).map((f, i) => ({
        id: String(i + 1),
        desc: f.toUpperCase(),
        target: '',
        selected: false,
      }))
    } else {
      briefError.value = 'No brief returned by bridge.'
      briefText.value = ''
      suggestions.value = []
    }
  } catch (e: unknown) {
    briefError.value = e instanceof Error ? e.message : String(e)
    briefText.value = ''
    suggestions.value = []
  } finally {
    briefFetching.value = false
  }
}

function onBriefSourceChange(_v: string | null) {
  loadBrief()
}

onMounted(async () => {
  await loadBrief()
  phase.value = 'briefing'
})

const cursorIndex = ref(0) // 0-2 for goals (max 3), 3 for confirm

// Confirm sits at index = suggestions.length (cap at 3).
const confirmIndex = computed(() => suggestions.value.length)

useKeyboard((e: KeyboardEvent) => {
  // Tab switching — always available.
  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }

  if (e.key === 'w' || e.key === 'W') {
    audio.playSfx('cursor_select')
    router.push('/analysis/track')
    return
  }

  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage')
    return
  }

  if (e.key === 's' || e.key === 'S') {
    confirmSelection()
    return
  }

  // Goals tab — arrow/enter only meaningful when we're past the brief.
  if (activeTab.value !== 2 || phase.value !== 'goals') return

  if (e.key === 'ArrowDown') {
    cursorIndex.value = Math.min(cursorIndex.value + 1, confirmIndex.value)
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursorIndex.value = Math.max(cursorIndex.value - 1, 0)
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter' || e.key === ' ') {
    if (cursorIndex.value === confirmIndex.value) {
      confirmSelection()
    } else {
      toggleGoal(cursorIndex.value)
    }
  }
})

async function confirmSelection() {
  audio.playSfx('cursor_select')
  await sessionStore.startSession({
    driver: save.activeSlot?.driverName,
    track: 'Sonoma Raceway',
  })
  router.push('/hud')
}

function toggleGoal(index: number) {
  const target = suggestions.value[index]
  if (!target) return
  const currentlySelected = suggestions.value.filter(g => g.selected).length
  if (!target.selected && currentlySelected >= 3) {
    audio.playSfx('error_quiet')
    return
  }
  target.selected = !target.selected
  cursorIndex.value = index
  audio.playSfx('cursor_select')
  if (target.selected && suggestions.value.filter(g => g.selected).length === 3) {
    audio.playSfx('goal_complete')
  }
}

// Bridge / CAN preflight status sourced from /health (polled every 5s
// by bridgeStore). DBC presence comes from the same source: when CAN is
// connected AND frames are being decoded, the DBC is loaded. CALIBRATION
// has no honest source on the bridge — the badge is dropped rather than
// shipped as a hardcoded green checkmark.
const bridgeOk = computed(() => {
  const h = bridgeStore.health
  return h !== null && bridgeStore.healthError === null
})
const canOk = computed(() => Boolean(bridgeStore.health?.can?.connected))
const dbcOk = computed(() => {
  const c = bridgeStore.health?.can
  return Boolean(c && c.connected && (c.frames_total ?? 0) > 0)
})
</script>

<template>
  <PageShell
    title="PRE-SESSION BRIEFING · SONOMA RACEWAY"
    :actions="[
      { label: 'TOGGLE', key: 'Enter', keyLabel: 'A' },
      { label: 'START', key: 's', keyLabel: 'START', variant: 'primary' },
      { label: 'WALK', key: 'w', keyLabel: 'W' },
      { label: 'BACK', key: 'Escape', keyLabel: 'B', variant: 'warn' }
    ]"
    bg="cool"
    :show-heading="false"
  >
    <div class="prebrief-root flex flex-col h-full min-h-0 w-full gap-[clamp(4px,1vmin,10px)]">

      <!-- Tab bar -->
      <CyberTabs
        v-model="activeTab"
        :tabs="TAB_LABELS"
        class="mx-2 shrink-0"
      />

      <!-- Tab content fills remaining height -->
      <div class="flex-1 min-h-0 mx-2 overflow-hidden">

        <!-- BRIEF -->
        <CyberPanel v-show="activeTab === 0" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin]">
          <div class="flex flex-wrap gap-x-4 gap-y-1 text-small tracking-[0.2em] text-slate uppercase shrink-0">
            <span class="text-ui-info font-bold">PRE-FLIGHT</span>
            <span><span :class="bridgeOk ? 'text-ui-good' : 'text-ui-bad'">{{ bridgeOk ? '✓' : '✗' }}</span> BRIDGE</span>
            <span><span :class="canOk ? 'text-ui-good' : 'text-ui-bad'">{{ canOk ? '✓' : '✗' }}</span> USB-CAN</span>
            <span><span :class="dbcOk ? 'text-ui-good' : 'text-ui-bad'">{{ dbcOk ? '✓' : '✗' }}</span> DBC</span>
          </div>

          <div class="flex-1 min-h-0 flex flex-col justify-center">
            <div v-if="phase === 'loading' || briefFetching" class="text-slate text-body animate-pulse text-center">
              LOADING BRIEF…
            </div>
            <div v-else-if="briefError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
              <div class="font-bold mb-1">BRIEF UNAVAILABLE</div>
              <div class="text-ui-bad/80 normal-case tracking-normal">{{ briefError }}</div>
            </div>
            <DialogueBox
              v-else-if="briefText"
              :coach-id="save.activeSlot?.preferredCoach ?? 'trod'"
              :emotion="coach.brief?.emotion ?? 'talk'"
              :text="briefText"
              @done="phase = 'goals'"
            />
            <div v-else class="text-small text-slate tracking-widest uppercase text-center">— waiting for brief —</div>
          </div>

          <div class="flex gap-8 text-small text-slate shrink-0 border-t border-slate/40 pt-[1vmin] tracking-widest uppercase">
            <span class="flex items-center gap-2"><span class="text-ui-info text-body">☀</span> WEATHER <span class="text-slate/30 mx-1">|</span> {{ coach.brief?.weather_phase ?? '—' }}</span>
            <span class="flex items-center gap-2"><span class="text-ui-info text-body">☷</span> TRACK <span class="text-slate/30 mx-1">|</span> {{ coach.brief?.surface_state ?? '—' }}</span>
          </div>
        </CyberPanel>

        <!-- SETUP -->
        <CyberPanel v-show="activeTab === 1" class="h-full flex flex-col gap-[clamp(8px,1.5vmin,16px)] p-[clamp(8px,2vmin,18px)] overflow-hidden">
          <div class="flex-1 min-h-0 grid grid-cols-1 landscape:grid-cols-2 gap-[clamp(8px,2vmin,18px)] overflow-y-auto">
            <section class="flex flex-col gap-[clamp(6px,1.2vmin,12px)] min-w-0">
              <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1">BRIEF SOURCE</div>
              <BriefSourcePicker
                v-model="briefSourceSessionId"
                :disabled="briefFetching"
                @change="onBriefSourceChange"
              />
            </section>

            <section class="flex flex-col gap-[clamp(6px,1.2vmin,12px)] min-w-0">
              <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1">SESSION START</div>
              <SessionStartPicker />
            </section>
          </div>

          <div class="shrink-0 text-small text-slate/70 tracking-widest uppercase pt-[1vmin] border-t border-slate/40">
            CHOICES HERE APPLY ON THE NEXT BRIEF FETCH AND THE NEXT SESSION START.
          </div>
        </CyberPanel>

        <!-- GOALS -->
        <CyberPanel v-show="activeTab === 2" class="h-full flex flex-col gap-[clamp(6px,1.2vmin,14px)] p-[clamp(8px,2vmin,18px)] overflow-hidden">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            PICK YOUR GOALS (1-3)
          </div>

          <div class="flex-1 min-h-0 overflow-y-auto">
            <Frame variant="default" padding="clamp(8px,1.5vmin,16px)" class="h-full flex flex-col">
              <div v-if="phase !== 'goals'" class="text-small text-slate tracking-widest uppercase py-4 text-center">
                FINISH THE COACH BRIEF FIRST — TAB 1.
              </div>
              <div v-else-if="suggestions.length === 0" class="text-small text-slate tracking-widest uppercase py-4 text-center">
                NO FOCUS LOADED — COACH BRIEF DID NOT RETURN GOALS.
              </div>
              <div v-else class="flex flex-col gap-[clamp(6px,1.2vmin,14px)]">
                <CyberCheckbox
                  v-for="(g, i) in suggestions"
                  :key="g.id"
                  :label="g.desc"
                  :sub-label="g.target || undefined"
                  :checked="g.selected"
                  :focused="cursorIndex === i"
                  @click="toggleGoal(i)"
                />
              </div>
            </Frame>
          </div>

          <div class="shrink-0 pt-[1vmin] border-t border-slate text-center">
            <button
              type="button"
              class="px-[clamp(16px,4vmin,48px)] tracking-[0.2em] transition-all cursor-pointer inline-flex items-center justify-center min-h-[44px] border-2 uppercase font-bold"
              :class="cursorIndex === confirmIndex
                ? 'bg-ui-good text-ink border-ui-good shadow-[0_0_15px_rgba(42,161,152,0.5)]'
                : 'text-silver border-slate hover:text-white hover:border-silver'"
              :style="{ fontSize: 'clamp(13px, 2.4vmin, 20px)' }"
              @click="confirmSelection"
              @mouseover="cursorIndex = confirmIndex"
            >
              <span v-if="cursorIndex === confirmIndex" class="mr-2">▶</span>CONFIRM SELECTION
            </button>
          </div>
        </CyberPanel>

      </div>
    </div>
  </PageShell>
</template>

<style scoped>
.prebrief-root {
  /* PageShell already constrains us to the landscape viewport;
     this ensures the inner tabbed layout never overflows. */
  min-height: 0;
}
</style>

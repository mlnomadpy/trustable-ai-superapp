<script setup lang="ts">
/**
 * SponsorContractsBody — sponsor backend is not wired. The previous
 * implementation hardcoded a fake sponsor seed; we ripped it out per the
 * no-mocks / no-fake-fallbacks policy. This component now renders an
 * honest "FEATURE NOT IMPLEMENTED" panel.
 *
 * The file is intentionally preserved (rather than deleted) because the
 * `/garage/sponsors` route and the QuestLog "SPONSORS" tab both import
 * it. Hidden until a `/sponsors` endpoint exists on the bridge.
 *
 * // Sponsor backend not wired. Hidden until /sponsors endpoint exists.
 */
import { useRouter } from 'vue-router'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'

const props = withDefaults(defineProps<{
  /** Whether this view owns keyboard input right now (legacy contract;
   *  retained so the QuestLog tab gating still type-checks). */
  active?: boolean
  /** When true, ESC/B navigates back; when false the parent handles it. */
  ownsBackNav?: boolean
}>(), {
  active: true,
  ownsBackNav: false,
})

const router = useRouter()
const audio = useAudioStore()

useKeyboard((e: KeyboardEvent) => {
  if (!props.active) return
  if (props.ownsBackNav && (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b')) {
    audio.playSfx('cancel')
    router.back()
  }
})
</script>

<template>
  <CyberPanel class="h-full min-h-0 flex flex-col items-center justify-center text-center gap-3 p-6 bg-ink">
    <span class="text-title font-title text-ui-warn tracking-widest">
      SPONSORS UNAVAILABLE
    </span>
    <p class="text-body text-ui-warn/90 max-w-md leading-relaxed font-bold tracking-wider uppercase">
      Feature not implemented
    </p>
    <p class="text-body text-slate max-w-md leading-relaxed normal-case">
      The bridge does not expose a <span class="text-silver font-mono">/sponsors</span>
      endpoint yet. This screen will populate the moment a sponsor backend
      is wired up — no PWA changes required.
    </p>
  </CyberPanel>
</template>

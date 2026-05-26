<script setup lang="ts">
/**
 * Ghost-data overlay manager — COMING SOON.
 *
 * The previous implementation rendered a hardcoded list of 5 "ghost laps"
 * with a setTimeout-based toggle. No bridge endpoint exposes saved ghost
 * laps yet; nothing here was real. Replaced with an honest placeholder so
 * direct-URL navigation doesn't show fake telemetry overlays. When ghost
 * laps land on the bridge (likely an extension of `/session/<sid>/export.parquet`
 * + a per-driver ghost-pick endpoint), re-implement the picker here.
 */
import { useRouter } from 'vue-router'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'

const router = useRouter()
const audio = useAudioStore()

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  }
})
</script>

<template>
  <PageShell title="GHOST DATA" :hints="['B · BACK']" bg="cool">
    <template #heading>
      <div class="heading-block mb-[1.5vh] text-center">
        <h1 class="text-title font-title text-ui-warn tracking-[0.2em] animate-pulse">COMING SOON</h1>
        <div class="heading-rule"></div>
      </div>
    </template>

    <CyberPanel class="flex-grow flex flex-col items-center justify-center gap-3 p-6 text-center mx-2">
      <span class="text-title font-title text-ui-warn tracking-widest">GHOST DATA</span>
      <p class="text-body text-silver max-w-md leading-relaxed">
        Ghost-lap overlays will land when the bridge ships a per-driver
        ghost-pick endpoint built on top of <span class="text-ui-good">/session/&lt;sid&gt;/export.parquet</span>.
        For now use <span class="text-ui-good">DRIVER EVOLUTION</span> for
        session-over-session deltas and
        <span class="text-ui-good">COMPARE</span> for side-by-side metrics.
      </p>
      <p class="text-small text-slate italic">Press B to return.</p>
    </CyberPanel>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * Telemetry replay (VCR) — COMING SOON.
 *
 * The previous implementation rendered a fake car on the track map driven
 * by `Math.sin(progress)` — speed, gear, and RPM were all sine waves. No
 * actual session data was being replayed. Replaced with an honest stub
 * until we have a real frame stream. The likely build path is:
 *   1. Pull `/session/<sid>/export.parquet` into DuckDB-Wasm (already
 *      wired in `duckdbStore`).
 *   2. Step through the rows on a wall-clock tick, projecting `distance_m`
 *      onto the TrackMap path the same way `HudTrackMap` does.
 *   3. Show real speed / gear / rpm from the parquet columns.
 *
 * The replay page intentionally subscribes to the SSE telemetry stream as
 * soon as the bridge reports an `active_session_id`, regardless of CAN
 * connection state. The previous gate (`can.connected === true`) blocked
 * the replay-only use case — replaying an old/sim session does not require
 * live USB-CAN. Pattern mirrors PitStall.vue's `watch(carState, …,
 * { immediate: true })` shape.
 */
import { onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { useTelemetryStore } from '@/entities/session/model/telemetryStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'

const router = useRouter()
const audio = useAudioStore()
const bridgeStore = useBridgeStore()
const telemetry = useTelemetryStore()

// Subscribe whenever the bridge reports an active session — independent of
// CAN connectivity. If the sid disappears we drop the SSE handle so the
// store stops retrying.
let lastSid: string | null = null
watch(
  () => bridgeStore.health?.active_session_id ?? null,
  (sid) => {
    if (sid && sid !== lastSid) {
      lastSid = sid
      telemetry.open(sid)
    } else if (!sid && lastSid) {
      lastSid = null
      telemetry.close()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  telemetry.close()
})

useKeyboard((e: KeyboardEvent) => {
  // ESC is handled globally by App.vue (router.back). Keep B/Backspace as
  // local fallbacks so the page still responds when the immersive HUD
  // chrome isn't around to remind the user.
  if (e.key === 'Backspace' || e.key === 'b' || e.key === 'B') {
    audio.playSfx('cancel')
    router.back()
  }
})
</script>

<template>
  <PageShell title="VCR REPLAY" :hints="['B · BACK']" bg="cool">
    <template #heading>
      <div class="heading-block mb-[1.5vh] text-center">
        <h1 class="text-title font-title text-ui-warn tracking-[0.2em] animate-pulse">COMING SOON</h1>
        <div class="heading-rule"></div>
      </div>
    </template>

    <CyberPanel class="flex-grow flex flex-col items-center justify-center gap-3 p-6 text-center mx-2">
      <span class="text-title font-title text-ui-warn tracking-widest">VCR REPLAY</span>
      <p class="text-body text-silver max-w-md leading-relaxed">
        Frame-by-frame lap replay needs a real telemetry source. The plan:
        hydrate <span class="text-ui-good">/session/&lt;sid&gt;/export.parquet</span>
        into the client-side DuckDB-Wasm instance, step rows on a wall-clock
        tick, and project distance onto the track map. Until that lands,
        check <span class="text-ui-good">LAP TIMES HALL</span> for sector
        deltas and <span class="text-ui-good">ON-TRACK HUD</span> for live
        telemetry while driving.
      </p>
      <p class="text-small text-slate italic">Press B to return.</p>
    </CyberPanel>
  </PageShell>
</template>

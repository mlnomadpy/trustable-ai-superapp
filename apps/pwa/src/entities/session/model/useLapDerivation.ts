/**
 * useLapDerivation — derive a live `lap_number` and per-lap progress %
 * from the cumulative `distance` field on the telemetry SSE frame.
 *
 * The bridge does NOT currently emit `lap_number` on the realtime
 * telemetry channel (it only computes laps server-side via
 * `/session/<sid>/laps`). For the cockpit HUD we want the lap tile to
 * tick over the moment the car crosses the start/finish, without
 * waiting for the post-session lap detector.
 *
 * Algorithm:
 *   • Anchor `startDistance` to the first frame distance we see
 *     (this is "metres travelled since wheel-start", monotonic).
 *   • Lap N = floor((distance - startDistance) / track_length_m) + 1.
 *   • Lap progress % = ((distance - startDistance) mod track_length_m)
 *                      / track_length_m * 100.
 *   • `reset()` clears the anchor so it re-captures on the next frame —
 *     called whenever the session id flips OR a new replay begins
 *     (telemetry.firstFrameAt changes).
 *
 * Returns `null` until both a frame AND a `track_length_m` are
 * available — callers should render "—" not "1" in that window so we
 * never invent a fake lap count.
 */
import { computed, ref, type ComputedRef, type Ref } from 'vue'

export interface LapDerivationInput {
  /** Reactive view of the latest SSE frame; only `distance` is consumed. */
  frame: { distance?: number | null } | null
}

export interface LapDerivationApi {
  lapNumber: ComputedRef<number | null>
  lapProgressPct: ComputedRef<number | null>
  /** Forget the anchor; the next non-null distance becomes the new origin. */
  reset(): void
}

export function useLapDerivation(
  telemetry: { frame: LapDerivationInput['frame'] | null } | Ref<LapDerivationInput['frame'] | null>,
  trackLengthM: Ref<number | null>,
): LapDerivationApi {
  const startDistance = ref<number | null>(null)

  function readDistance(): number | null {
    // Support both Pinia store (reactive prop) and a plain Ref<frame>.
    const f: LapDerivationInput['frame'] | null = 'value' in telemetry
      ? (telemetry as Ref<LapDerivationInput['frame']>).value
      : (telemetry as { frame: LapDerivationInput['frame'] | null }).frame
    const d = f?.distance
    if (d == null || !Number.isFinite(d)) return null
    return d
  }

  const lapNumber = computed<number | null>(() => {
    const d = readDistance()
    const tl = trackLengthM.value
    if (d == null || !tl || tl <= 0) return null
    if (startDistance.value == null) startDistance.value = d
    const since = d - startDistance.value
    if (!Number.isFinite(since) || since < 0) return 1
    return Math.max(1, Math.floor(since / tl) + 1)
  })

  const lapProgressPct = computed<number | null>(() => {
    const d = readDistance()
    const tl = trackLengthM.value
    if (d == null || !tl || tl <= 0) return null
    if (startDistance.value == null) return 0
    const since = d - startDistance.value
    if (!Number.isFinite(since) || since < 0) return 0
    const within = since % tl
    return Math.max(0, Math.min(100, (within / tl) * 100))
  })

  function reset() {
    startDistance.value = null
  }

  return { lapNumber, lapProgressPct, reset }
}

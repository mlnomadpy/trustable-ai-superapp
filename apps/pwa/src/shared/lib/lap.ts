/**
 * Lap-time formatting — single source of truth for the whole PWA.
 *
 * Pre-2026-05-13 the same `formatLap` was inlined in 8 screens, with two
 * different precisions:
 *   • One-decimal `M:SS.s`  on live / HUD-style surfaces (OnTrackHud,
 *     StageClear, EndOfDay, DriverEvolution, ComparisonView, TrainerCard)
 *   • Three-decimal `M:SS.mmm` on analytics surfaces (LapTimesHall,
 *     AnalysisHub)
 *
 * The same lap rendering as `1:47.2` on the HUD and `1:47.234` in Lap
 * Times Hall was confusing — drivers couldn't tell if it was the same
 * lap. This helper keeps the two precisions but routes them through one
 * function so the rounding rule is identical.
 *
 * Convention:
 *   • `formatLapTime(t)` defaults to 3-decimal analytics precision.
 *   • Pass `1` for HUD-style readability (`1:47.2`).
 *   • Pass `2` for "stopwatch" precision (`1:47.23`) — currently unused
 *     but available for future stints / sectors.
 *
 * Returns the empty-state string `--:--.-` / `--:--.--` / `--:--.---`
 * (matching precision) when the input is null / undefined / non-finite.
 * Never throws.
 */

export type LapPrecision = 1 | 2 | 3

const EMPTY: Record<LapPrecision, string> = {
  1: '--:--.-',
  2: '--:--.--',
  3: '--:--.---',
}

const PAD: Record<LapPrecision, number> = {
  1: 4,   // SS.s
  2: 5,   // SS.ss
  3: 6,   // SS.sss
}

/** Format `seconds` as `M:SS.<precision>`. Pass null/undefined for empty state. */
export function formatLapTime(
  seconds: number | null | undefined,
  precision: LapPrecision = 3,
): string {
  if (seconds == null || !Number.isFinite(seconds)) return EMPTY[precision]
  const mins = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(precision)
  return `${mins}:${secs.padStart(PAD[precision], '0')}`
}

/**
 * Format a signed delta in seconds — used for "ideal-lap gain" and
 * comparison views. Positive numbers get a leading `+`. Always renders
 * a sign; magnitude uses the same precision rules as `formatLapTime`.
 */
export function formatLapDelta(
  seconds: number | null | undefined,
  precision: LapPrecision = 3,
): string {
  if (seconds == null || !Number.isFinite(seconds)) return EMPTY[precision].replace(/^/, '')
  const sign = seconds >= 0 ? '+' : '−'   // unicode minus for visual symmetry
  return `${sign}${Math.abs(seconds).toFixed(precision)}s`
}

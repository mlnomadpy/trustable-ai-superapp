/**
 * Per-signal sanity ranges. Values outside these are replaced with null
 * (a gap in the line) when the outlier filter is on.
 *
 * Pulled from the AiM MXP v3.0 PDF + DBC value_range hints + physical
 * reality. Ported from docs/telemetry-viewer.html.
 */
export interface SanityRange {
  min: number
  max: number
}

export const SANITY_RANGES: Readonly<Record<string, SanityRange>> = Object.freeze({
  // pressures
  brake_press_psi: { min: 0, max: 200 },
  brake_bar: { min: 0, max: 14 },
  oil_press_psi: { min: 0, max: 150 },
  oil_press_bar: { min: 0, max: 10 },
  water_press_psi: { min: 0, max: 60 },
  water_press_bar: { min: 0, max: 4 },
  fuel_press_psi: { min: 0, max: 150 },
  // temperatures (°F)
  water_temp_f: { min: -40, max: 350 },
  engine_oil_temp_f: { min: -40, max: 400 },
  oil_filter_temp_f: { min: -40, max: 400 },
  ambient_temp_f: { min: -40, max: 150 },
  logger_temp_f: { min: -40, max: 200 },
  // TPMS
  tpms_press_fl_psi: { min: 5, max: 60 },
  tpms_press_fr_psi: { min: 5, max: 60 },
  tpms_press_rl_psi: { min: 5, max: 60 },
  tpms_press_rr_psi: { min: 5, max: 60 },
  tpms_temp_fl_f: { min: 32, max: 250 },
  tpms_temp_fr_f: { min: 32, max: 250 },
  tpms_temp_rl_f: { min: 32, max: 250 },
  tpms_temp_rr_f: { min: 32, max: 250 },
  // IMU
  inline_accel_g: { min: -3.5, max: 3.5 },
  lateral_accel_g: { min: -3.5, max: 3.5 },
  vertical_accel_g: { min: -3.5, max: 3.5 },
  g_lat: { min: -3.5, max: 3.5 },
  g_long: { min: -3.5, max: 3.5 },
  g_vert: { min: -3.5, max: 3.5 },
  combo_g: { min: 0, max: 5 },
  roll_rate_degs: { min: -360, max: 360 },
  pitch_rate_degs: { min: -360, max: 360 },
  yaw_rate_degs: { min: -360, max: 360 },
  // ECU
  rpm: { min: 0, max: 10000 },
  speed_ms: { min: 0, max: 120 },
  speed_mph: { min: 0, max: 250 },
  steering_deg: { min: -540, max: 540 },
  throttle_pct: { min: 0, max: 100 },
  pedal_pos_pct: { min: 0, max: 100 },
  fuel_level_gal: { min: 0, max: 30 },
  battery_volt: { min: 0, max: 16 },
})

export type PointXY = { x: number; y: number | null }
export type Sample = number | null | PointXY
export type SampleArr<T extends Sample> = T[]

const isPoint = (d: unknown): d is PointXY =>
  typeof d === 'object' && d !== null && 'x' in d && 'y' in d

/**
 * Sanity-clip an array of {x,y} or scalar values. Returns the input
 * unchanged when `enabled` is false or the signal has no range defined.
 * Out-of-range y-values are replaced with null (becomes a gap in line
 * charts; Chart.js handles this naturally).
 */
export function clipOutliers<T extends Sample>(
  name: string,
  data: SampleArr<T>,
  enabled = true,
): SampleArr<T> {
  if (!enabled) return data
  const r = SANITY_RANGES[name]
  if (!r) return data
  return data.map((d) => {
    if (d == null) return d
    if (isPoint(d)) {
      const y = d.y
      if (y == null || y < r.min || y > r.max) {
        return { x: d.x, y: null } as T
      }
      return d
    }
    const y = d as number
    if (y == null || y < r.min || y > r.max) {
      return null as T
    }
    return d
  })
}

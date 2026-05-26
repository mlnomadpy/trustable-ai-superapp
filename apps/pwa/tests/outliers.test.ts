import { describe, it, expect } from 'vitest'
import { clipOutliers, SANITY_RANGES } from '../src/shared/lib/telemetry/outliers'

describe('clipOutliers', () => {
  it('returns the input unchanged when disabled', () => {
    const data = [1, 999_999, 2]
    expect(clipOutliers('rpm', data, false)).toBe(data)
  })

  it('returns the input unchanged for unknown signals', () => {
    const data = [1, 999_999, 2]
    // 'not_a_real_signal' has no sanity range — pass-through.
    expect(clipOutliers('not_a_real_signal', data, true)).toBe(data)
  })

  it('nulls scalar values outside the sanity range', () => {
    expect(SANITY_RANGES.rpm.max).toBe(10000)
    const clipped = clipOutliers('rpm', [500, 12000, 7500, -100, null], true)
    expect(clipped).toEqual([500, null, 7500, null, null])
  })

  it('nulls y of {x,y} points outside the range, preserving x', () => {
    const data = [
      { x: 0, y: 0 },
      { x: 1, y: 999 },
      { x: 2, y: 0.5 },
      { x: 3, y: null },
    ]
    const clipped = clipOutliers('g_lat', data, true)
    expect(clipped).toEqual([
      { x: 0, y: 0 },
      { x: 1, y: null },
      { x: 2, y: 0.5 },
      { x: 3, y: null },
    ])
  })

  it('handles boundary values (inclusive)', () => {
    const r = SANITY_RANGES.throttle_pct
    expect(r).toEqual({ min: 0, max: 100 })
    const clipped = clipOutliers('throttle_pct', [0, 100, 100.01, -0.01], true)
    expect(clipped).toEqual([0, 100, null, null])
  })
})

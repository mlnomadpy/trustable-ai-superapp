import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAnalysisStore } from '../src/entities/analysis/model/analysisStore'

describe('analysisStore', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('starts with no session, full-session selected, outlier filter on', () => {
    const a = useAnalysisStore()
    expect(a.sessionId).toBeNull()
    expect(a.selectedLapIndex).toBe(0)
    expect(a.filterOutliers).toBe(true)
    expect(a.selectedLap).toBeNull()
  })

  it('lapFilterSql returns empty fragment when no lap is selected', () => {
    const a = useAnalysisStore()
    const lf = a.lapFilterSql('timestamp')
    expect(lf.sql).toBe('')
    expect(lf.params).toEqual([])
  })

  it('lapFilterSql returns AND-fragment + params when a lap is selected', () => {
    const a = useAnalysisStore()
    // Inject laps as if loadSession populated them.
    a.laps = [
      { name: 'Full session', t_start: 0, t_end: 100, duration_s: 100, distance_m: 5000, method: 'all' },
      { name: 'Lap 1', t_start: 10, t_end: 50, duration_s: 40, distance_m: 4060, method: 'gps' },
    ]
    a.setSelectedLap(1)
    const lf = a.lapFilterSql('ts.t')
    expect(lf.sql).toBe(' AND ts.t BETWEEN ? AND ?')
    expect(lf.params).toEqual([10, 50])
    expect(a.selectedLap?.name).toBe('Lap 1')
  })

  it('cycleLap wraps both directions', () => {
    const a = useAnalysisStore()
    a.laps = [
      { name: 'Full', t_start: 0, t_end: 1, duration_s: 1, distance_m: 0, method: 'all' },
      { name: 'L1',   t_start: 0, t_end: 1, duration_s: 1, distance_m: 0, method: 'gps' },
      { name: 'L2',   t_start: 0, t_end: 1, duration_s: 1, distance_m: 0, method: 'gps' },
    ]
    expect(a.selectedLapIndex).toBe(0)
    a.cycleLap(1); expect(a.selectedLapIndex).toBe(1)
    a.cycleLap(1); expect(a.selectedLapIndex).toBe(2)
    a.cycleLap(1); expect(a.selectedLapIndex).toBe(0)
    a.cycleLap(-1); expect(a.selectedLapIndex).toBe(2)
  })

  it('setFilterOutliers toggles state', () => {
    const a = useAnalysisStore()
    a.setFilterOutliers(false)
    expect(a.filterOutliers).toBe(false)
    a.setFilterOutliers(true)
    expect(a.filterOutliers).toBe(true)
  })

  it('setActiveTab persists across calls', () => {
    const a = useAnalysisStore()
    a.setActiveTab('signals')
    expect(a.activeTab).toBe('signals')
    a.setActiveTab('imu')
    expect(a.activeTab).toBe('imu')
  })
})

/**
 * Telemetry query helpers used by the Analysis-Hall tabs. Thin wrapper
 * over DuckDB-wasm's prepared-statement API plus the lap-filter SQL
 * fragment from useAnalysisStore.
 */
import type { DuckRow } from '@/shared/lib/duckdb/duckdbStore'
import { useDuckDBStore } from '@/shared/lib/duckdb/duckdbStore'
import { useAnalysisStore } from '@/entities/analysis/model/analysisStore'

export type WidePoint = { x: number; y: number | null }

/** Convert a DuckDB BigInt timestamp value to a JS number. */
export function asNum(v: unknown): number | null {
  if (v == null) return null
  if (typeof v === 'number') return v
  if (typeof v === 'bigint') return Number(v)
  if (typeof v === 'string') {
    const n = parseFloat(v)
    return Number.isFinite(n) ? n : null
  }
  return null
}

/**
 * Stride-decimate an array down to ~target points. Returns a new array
 * so the caller can keep the original.
 */
export function decimate<T>(arr: T[], target: number): T[] {
  if (arr.length <= target) return arr
  const stride = Math.max(1, Math.floor(arr.length / target))
  const out: T[] = []
  for (let i = 0; i < arr.length; i += stride) out.push(arr[i])
  return out
}

/**
 * Pull one tall-store signal as a {x, y} series, time-zeroed against
 * the supplied `t0`. Applies the active lap filter automatically.
 */
export async function fetchSignalSeries(
  sessionId: string,
  signalName: string,
  t0: number,
  decimateTo = 3000,
): Promise<WidePoint[]> {
  const duck = useDuckDBStore()
  const analysis = useAnalysisStore()
  const lf = analysis.lapFilterSql('ts.t')
  const rows = await duck.rows<{ x: unknown; y: unknown }>(
    `SELECT ts.t - ? AS x, ts.value AS y
       FROM telemetry_signals ts
       JOIN signal_registry sr USING(signal_id)
      WHERE sr.name = ? AND ts.session_id = ?` + lf.sql + `
      ORDER BY ts.t`,
    [t0, signalName, sessionId, ...lf.params],
  )
  const out: WidePoint[] = rows.map((r) => ({
    x: asNum(r.x) ?? 0,
    y: asNum(r.y),
  }))
  return decimate(out, decimateTo)
}

/**
 * MIN(t) across the tall store. Used as the chart x-zero.
 */
export async function tallT0(): Promise<number> {
  const duck = useDuckDBStore()
  const v = await duck.scalar<unknown>('SELECT MIN(t) FROM telemetry_signals')
  return asNum(v) ?? 0
}

/**
 * Latest scalar value for a tall-store signal, optionally constrained
 * to the active lap window.
 */
export async function latestSignalValue(
  sessionId: string,
  signalName: string,
): Promise<number | null> {
  const duck = useDuckDBStore()
  const analysis = useAnalysisStore()
  const lf = analysis.lapFilterSql('ts.t')
  const v = await duck.scalar<unknown>(
    `SELECT ts.value FROM telemetry_signals ts
       JOIN signal_registry sr USING(signal_id)
      WHERE sr.name = ? AND ts.session_id = ?` + lf.sql + `
      ORDER BY ts.t DESC LIMIT 1`,
    [signalName, sessionId, ...lf.params],
  )
  return asNum(v)
}

/** Generic typed row fetcher with lap-filter helper not applied. */
export async function fetchRows<T extends DuckRow = DuckRow>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const duck = useDuckDBStore()
  return duck.rows<T>(sql, params)
}

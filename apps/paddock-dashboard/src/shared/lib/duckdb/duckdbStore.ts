import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import * as duckdb from '@duckdb/duckdb-wasm'
import { bridge } from '@/shared/api/bridge'

// Bundle DuckDB-wasm assets locally via Vite. Loading the worker from a
// cross-origin URL (jsdelivr) is blocked by Chrome for Worker construction
// since the worker script must be same-origin. The `?url` suffix tells Vite
// to emit each file as a hashed asset under dist/ and return its served URL.
import duckdb_wasm     from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url'
import duckdb_wasm_eh  from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'
import mvp_worker_url  from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url'
import eh_worker_url   from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url'

const DUCKDB_BUNDLES: duckdb.DuckDBBundles = {
  mvp: { mainModule: duckdb_wasm,    mainWorker: mvp_worker_url },
  eh:  { mainModule: duckdb_wasm_eh, mainWorker: eh_worker_url  },
}

/**
 * The three parquet tables we materialise per session. The bridge
 * exposes each via /session/<sid>/export.parquet?table=<name>.
 *
 *   - telemetry         · wide canonical frames (11 cols, ~50 Hz)
 *   - telemetry_signals · tall (signal_id, t, value) store
 *   - signal_registry   · catalog (signal_id, name, units, "group")
 */
type ParquetTable = 'telemetry' | 'telemetry_signals' | 'signal_registry'

const FILE_SUFFIX: Record<ParquetTable, string> = {
  telemetry: 'telemetry.parquet',
  telemetry_signals: 'signals.parquet',
  signal_registry: 'registry.parquet',
}

/**
 * Common row shape DuckDB returns via Arrow `.toArray()`.
 */
export type DuckRow = Record<string, unknown>

export const useDuckDBStore = defineStore('duckdb', {
  state: () => ({
    db: null as duckdb.AsyncDuckDB | null,
    cachedSessionIds: markRaw(new Set<string>()),
    /** sessions whose 3-table bundle has been materialised */
    cachedFullSessionIds: markRaw(new Set<string>()),
  }),
  actions: {
    async init() {
      if (this.db) return

      // Resolve the best-fit bundle (mvp / eh) from the locally-bundled set.
      // `selectBundle` feature-detects WebAssembly exception handling, etc.
      const bundle = await duckdb.selectBundle(DUCKDB_BUNDLES)

      // Worker is a classic script (the dist .worker.js files start with
      // "use strict";), so no `{ type: 'module' }`. The URL is now same-origin
      // (served by Vite under /assets/), satisfying the browser's worker CSP.
      const worker = new Worker(bundle.mainWorker!)
      const logger = new duckdb.ConsoleLogger()
      this.db = new duckdb.AsyncDuckDB(logger, worker)

      await this.db.instantiate(bundle.mainModule!, bundle.pthreadWorker)
    },

    /**
     * Original single-table loader retained for callers that only want
     * wide telemetry (e.g. existing telemetry-replay code paths).
     */
    async ensureSession(sid: string) {
      if (this.cachedSessionIds.has(sid)) return
      const root = await navigator.storage.getDirectory()
      const dir = await root.getDirectoryHandle('sessions', { create: true })

      try {
        const fh = await dir.getFileHandle(`${sid}.parquet`)
        const file = await fh.getFile()
        const buf = new Uint8Array(await file.arrayBuffer())
        await this.db!.registerFileBuffer(`${sid}.parquet`, buf)
      } catch {
        const buf = await bridge.getBuffer(`/session/${sid}/export.parquet?table=telemetry`)
        await this.db!.registerFileBuffer(`${sid}.parquet`, buf)

        const fh = await dir.getFileHandle(`${sid}.parquet`, { create: true })
        const ws = await fh.createWritable()
        await ws.write(buf.buffer as ArrayBuffer)
        await ws.close()
      }

      const conn = await this.db!.connect()
      await conn.query(`CREATE OR REPLACE VIEW telemetry AS SELECT * FROM '${sid}.parquet'`)
      await conn.close()

      this.cachedSessionIds.add(sid)
    },

    /**
     * Register all three session parquets and expose them as DuckDB
     * views named `telemetry`, `telemetry_signals`, `signal_registry`.
     * Each file is OPFS-cached under `<sid>.<table>.parquet`.
     *
     * Throws if any of the three downloads fail — tabs render an
     * "unavailable" empty state rather than silently degrading.
     */
    async ensureSessionFull(sid: string) {
      if (this.cachedFullSessionIds.has(sid)) return
      await this.init()

      const root = await navigator.storage.getDirectory()
      const dir = await root.getDirectoryHandle('sessions', { create: true })

      const tables: ParquetTable[] = ['telemetry', 'telemetry_signals', 'signal_registry']
      for (const table of tables) {
        const fname = `${sid}.${FILE_SUFFIX[table]}`
        let buf: Uint8Array | null = null

        // 1. Try OPFS first
        try {
          const fh = await dir.getFileHandle(fname)
          const file = await fh.getFile()
          buf = new Uint8Array(await file.arrayBuffer())
        } catch {
          // 2. Pull from bridge
          buf = await bridge.getBuffer(
            `/session/${sid}/export.parquet?table=${table}`,
          )
          // 3. Persist to OPFS
          try {
            const fh = await dir.getFileHandle(fname, { create: true })
            const ws = await fh.createWritable()
            await ws.write(buf.buffer as ArrayBuffer)
            await ws.close()
          } catch (e) {
            // OPFS write is best-effort; in-memory view still works.
            console.warn(`[duckdb] OPFS write failed for ${fname}:`, e)
          }
        }

        await this.db!.registerFileBuffer(fname, buf)
        const conn = await this.db!.connect()
        try {
          await conn.query(
            `CREATE OR REPLACE VIEW ${table} AS SELECT * FROM '${fname}'`,
          )
        } finally {
          await conn.close()
        }
      }

      this.cachedFullSessionIds.add(sid)
    },

    /**
     * Execute a SQL string against the current DuckDB connection.
     * Returns the Arrow result table; callers should call .toArray()
     * for a plain row array. Parameter substitution mirrors DuckDB's
     * positional `$N` placeholders.
     */
    async query(sql: string, params?: unknown[]) {
      if (!this.db) throw new Error('DuckDB not initialized')
      const conn = await this.db.connect()
      try {
        if (params && params.length) {
          const stmt = await conn.prepare(sql)
          try {
            return await stmt.query(...params)
          } finally {
            await stmt.close()
          }
        }
        return await conn.query(sql)
      } finally {
        await conn.close()
      }
    },

    /**
     * Convenience: run `sql` and return rows as plain JS objects.
     */
    async rows<T = DuckRow>(sql: string, params?: unknown[]): Promise<T[]> {
      const result = await this.query(sql, params)
      // Arrow's .toArray() yields proxy objects — spread into plain
      // objects so callers can treat them as POJOs.
      const arr = result.toArray() as Array<Record<string, unknown>>
      return arr.map((r) => ({ ...r })) as T[]
    },

    /**
     * Convenience: return the first column of the first row, or null.
     */
    async scalar<T = unknown>(sql: string, params?: unknown[]): Promise<T | null> {
      const rs = await this.rows(sql, params)
      if (!rs.length) return null
      const first = rs[0]
      const keys = Object.keys(first)
      if (!keys.length) return null
      const v = first[keys[0]]
      return (v ?? null) as T | null
    },
  },
})

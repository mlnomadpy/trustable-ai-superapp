"""bridge.db — Schema DDL, connection factory, and signal helpers.

Backend-portable: uses DuckDB when available (Mac dev — fast columnar scans,
COPY TO PARQUET), falls back to SQLite when DuckDB isn't installed (Termux /
Android, where DuckDB and pyarrow have no aarch64 wheels). The SQL surface
used by pitwall is portable across both: only DDL identity/sequence syntax
and the Parquet-COPY shortcut differ.

Owns all table creation, the signal registry seeder, capability computation,
LLM friction sink, and the interpolation helpers used by the signal
synchroniser (ADR-015 Phase 3).
"""

import json
import logging
import os
from contextlib import contextmanager

from pitwall.state import state, SIM_DIR


log = logging.getLogger(__name__)


# ── Backend detection ──────────────────────────────────────────────────────────
# Prefer DuckDB when present; fall back to SQLite. Both ship with Python's
# stdlib (sqlite3 always present) or via pip (duckdb when wheels available).

_BACKEND: str
_DUCKDB_ERROR: type

try:
    import duckdb as _duckdb  # type: ignore[import-untyped]
    # Smoke-test connectability — guards against stub modules or broken
    # platform wheels. Use a path that does NOT exist (DuckDB rejects
    # opening an existing zero-byte file as "not a valid DuckDB database").
    import tempfile as _tmp
    _p = os.path.join(_tmp.gettempdir(), f"_pitwall_db_probe_{os.getpid()}.duckdb")
    try:
        _c = _duckdb.connect(_p)
        _c.close()
        _BACKEND = "duckdb"
        _DUCKDB_ERROR = _duckdb.Error
    except Exception as _e:  # noqa: BLE001
        log.info("duckdb importable but not runnable (%s) — falling back to sqlite", _e)
        raise ImportError("duckdb stub or broken wheel") from _e
    finally:
        for _suffix in ("", ".wal", ".tmp"):
            try:
                os.unlink(_p + _suffix)
            except OSError:
                pass
except ImportError:
    import sqlite3 as _sqlite
    _BACKEND = "sqlite"
    _DUCKDB_ERROR = _sqlite.Error  # kept name for back-compat across blueprints

log.info("db backend: %s", _BACKEND)


class DuckDbUnavailable(RuntimeError):
    """Raised when no embedded SQL backend is reachable. Name kept for
    back-compat with blueprints that catch it; the underlying backend
    may actually be SQLite."""


def db_backend() -> str:
    """Return 'duckdb' or 'sqlite' — the live backend name."""
    return _BACKEND


def iso(v):
    """Backend-portable ISO-string conversion for TIMESTAMP-typed cells.

    DuckDB returns TIMESTAMP columns as `datetime`/`date` objects.
    SQLite returns them as strings (because we don't set
    `detect_types=PARSE_DECLTYPES`). Blueprints called `.isoformat()`
    unconditionally; this helper takes the union and returns a string
    (or None) regardless of backend.
    """
    if v is None:
        return None
    iso_fn = getattr(v, "isoformat", None)
    if callable(iso_fn):
        return iso_fn()
    return str(v)


# ── Constants ──────────────────────────────────────────────────────────────────

# pitwall → edge-daemon → apps → repo root. data/ lives at the repo root
# post-V2-consolidation (was one level short, seeding 0 signals).
REGISTRY_SEED_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "registry", "obd2_pids.json",
))

# Wide-table columns that double as registry signals — used by capability
# computation to advertise canonical fields without round-tripping through
# the tall store.
WIDE_SIGNAL_NAMES = (
    "distance_m", "speed_ms", "g_lat", "g_long", "combo_g",
    "brake_bar", "throttle_pct", "steering_deg", "rpm", "lat", "lon",
)


# ── Schema DDL ─────────────────────────────────────────────────────────────────
# Two flavours: DuckDB uses `CREATE SEQUENCE` + `nextval()` for auto-PK and
# `now()` for timestamps; SQLite uses `INTEGER PRIMARY KEY AUTOINCREMENT`
# and `CURRENT_TIMESTAMP`. Everything else is portable.

_DUCKDB_DDL = """
        CREATE SEQUENCE IF NOT EXISTS laps_id_seq;
        CREATE TABLE IF NOT EXISTS laps (
            id            INTEGER PRIMARY KEY DEFAULT nextval('laps_id_seq'),
            session_id    VARCHAR,
            lap_number    INTEGER,
            lap_time_s    DOUBLE,
            best_sector   DOUBLE,
            avg_speed_kmh DOUBLE,
            max_combo_g   DOUBLE,
            coast_pct     DOUBLE,
            recorded_at   TIMESTAMP DEFAULT now()
        );
        CREATE SEQUENCE IF NOT EXISTS notes_id_seq;
        CREATE TABLE IF NOT EXISTS coaching_notes (
            id            INTEGER PRIMARY KEY DEFAULT nextval('notes_id_seq'),
            session_id    VARCHAR,
            burst_id      INTEGER,
            distance_m    DOUBLE,
            text          VARCHAR,
            source        VARCHAR,
            recorded_at   TIMESTAMP DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS telemetry (
            session_id   VARCHAR,
            frame_idx    INTEGER,
            timestamp    DOUBLE,
            distance_m   DOUBLE,
            speed_ms     DOUBLE,
            g_lat        DOUBLE,
            g_long       DOUBLE,
            combo_g      DOUBLE,
            brake_bar    DOUBLE,
            throttle_pct DOUBLE,
            steering_deg DOUBLE,
            rpm          DOUBLE,
            lat          DOUBLE,
            lon          DOUBLE
        );
        CREATE INDEX IF NOT EXISTS idx_telemetry_session
            ON telemetry(session_id, frame_idx);
        CREATE TABLE IF NOT EXISTS video_frames (
            session_id    VARCHAR,
            timestamp     DOUBLE,
            avitime_ms    BIGINT,
            file_path     VARCHAR,
            file_offset_s DOUBLE,
            width         INTEGER,
            height        INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_video_frames_session_t
            ON video_frames(session_id, timestamp);

        CREATE SEQUENCE IF NOT EXISTS signal_registry_id_seq;
        CREATE TABLE IF NOT EXISTS signal_registry (
            signal_id     INTEGER PRIMARY KEY DEFAULT nextval('signal_registry_id_seq'),
            name          VARCHAR UNIQUE NOT NULL,
            units         VARCHAR,
            semantics     VARCHAR,
            "group"       VARCHAR,
            expected_hz   DOUBLE,
            min_useful_hz DOUBLE,
            discovery     VARCHAR,
            obd2_pid      VARCHAR,
            discovered_at TIMESTAMP DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS telemetry_signals (
            session_id  VARCHAR NOT NULL,
            signal_id   INTEGER NOT NULL,
            t           DOUBLE  NOT NULL,
            value       DOUBLE  NOT NULL,
            PRIMARY KEY (session_id, signal_id, t)
        );
        CREATE INDEX IF NOT EXISTS idx_signals_sess_sig_t
            ON telemetry_signals (session_id, signal_id, t);
        CREATE TABLE IF NOT EXISTS session_capabilities (
            session_id  VARCHAR NOT NULL,
            signal_id   INTEGER NOT NULL,
            n_samples   INTEGER NOT NULL,
            mean_hz     DOUBLE  NOT NULL,
            t_start     DOUBLE  NOT NULL,
            t_end       DOUBLE  NOT NULL,
            PRIMARY KEY (session_id, signal_id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id    VARCHAR PRIMARY KEY,
            driver        VARCHAR,
            driver_level  VARCHAR,
            track         VARCHAR,
            car           VARCHAR,
            started_at    TIMESTAMP DEFAULT now(),
            ended_at      TIMESTAMP,
            note          VARCHAR
        );

        CREATE SEQUENCE IF NOT EXISTS llm_friction_id_seq;
        CREATE TABLE IF NOT EXISTS llm_friction (
            id               INTEGER PRIMARY KEY DEFAULT nextval('llm_friction_id_seq'),
            session_id       VARCHAR,
            role             VARCHAR,
            mode             VARCHAR,
            backend          VARCHAR,
            prompt_chars     INTEGER,
            completion_chars INTEGER,
            latency_ms       DOUBLE,
            truncated        BOOLEAN,
            fell_back        BOOLEAN,
            error            VARCHAR,
            emotion          VARCHAR,
            ts               TIMESTAMP DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_llm_friction_session_ts
            ON llm_friction (session_id, ts);

        CREATE SEQUENCE IF NOT EXISTS conversations_id_seq;
        CREATE TABLE IF NOT EXISTS conversations (
            id           INTEGER PRIMARY KEY DEFAULT nextval('conversations_id_seq'),
            session_id   VARCHAR,
            driver_id    VARCHAR,
            role         VARCHAR,
            text         TEXT,
            focus_items  VARCHAR,
            emotion      VARCHAR,
            recorded_at  TIMESTAMP DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_session
            ON conversations(session_id, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_conversations_driver
            ON conversations(driver_id, recorded_at);

        CREATE SEQUENCE IF NOT EXISTS agent_traces_id_seq;
        CREATE TABLE IF NOT EXISTS agent_traces (
            id          INTEGER PRIMARY KEY DEFAULT nextval('agent_traces_id_seq'),
            trace_id    VARCHAR,
            pitwall_sid VARCHAR,
            agent_name  VARCHAR,
            event_type  VARCHAR,
            detail      VARCHAR,
            latency_ms  DOUBLE,
            success     BOOLEAN DEFAULT true,
            ts          TIMESTAMP DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_agent_traces_trace
            ON agent_traces(trace_id, ts);
        CREATE INDEX IF NOT EXISTS idx_agent_traces_agent
            ON agent_traces(agent_name, ts);
"""


_SQLITE_DDL = """
        CREATE TABLE IF NOT EXISTS laps (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT,
            lap_number    INTEGER,
            lap_time_s    REAL,
            best_sector   REAL,
            avg_speed_kmh REAL,
            max_combo_g   REAL,
            coast_pct     REAL,
            recorded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS coaching_notes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT,
            burst_id      INTEGER,
            distance_m    REAL,
            text          TEXT,
            source        TEXT,
            recorded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS telemetry (
            session_id   TEXT,
            frame_idx    INTEGER,
            timestamp    REAL,
            distance_m   REAL,
            speed_ms     REAL,
            g_lat        REAL,
            g_long       REAL,
            combo_g      REAL,
            brake_bar    REAL,
            throttle_pct REAL,
            steering_deg REAL,
            rpm          REAL,
            lat          REAL,
            lon          REAL
        );
        CREATE INDEX IF NOT EXISTS idx_telemetry_session
            ON telemetry(session_id, frame_idx);
        CREATE TABLE IF NOT EXISTS video_frames (
            session_id    TEXT,
            timestamp     REAL,
            avitime_ms    INTEGER,
            file_path     TEXT,
            file_offset_s REAL,
            width         INTEGER,
            height        INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_video_frames_session_t
            ON video_frames(session_id, timestamp);

        CREATE TABLE IF NOT EXISTS signal_registry (
            signal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT UNIQUE NOT NULL,
            units         TEXT,
            semantics     TEXT,
            "group"       TEXT,
            expected_hz   REAL,
            min_useful_hz REAL,
            discovery     TEXT,
            obd2_pid      TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS telemetry_signals (
            session_id  TEXT    NOT NULL,
            signal_id   INTEGER NOT NULL,
            t           REAL    NOT NULL,
            value       REAL    NOT NULL,
            PRIMARY KEY (session_id, signal_id, t)
        );
        CREATE INDEX IF NOT EXISTS idx_signals_sess_sig_t
            ON telemetry_signals (session_id, signal_id, t);
        CREATE TABLE IF NOT EXISTS session_capabilities (
            session_id  TEXT    NOT NULL,
            signal_id   INTEGER NOT NULL,
            n_samples   INTEGER NOT NULL,
            mean_hz     REAL    NOT NULL,
            t_start     REAL    NOT NULL,
            t_end       REAL    NOT NULL,
            PRIMARY KEY (session_id, signal_id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id    TEXT PRIMARY KEY,
            driver        TEXT,
            driver_level  TEXT,
            track         TEXT,
            car           TEXT,
            started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at      TIMESTAMP,
            note          TEXT
        );

        CREATE TABLE IF NOT EXISTS llm_friction (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id       TEXT,
            role             TEXT,
            mode             TEXT,
            backend          TEXT,
            prompt_chars     INTEGER,
            completion_chars INTEGER,
            latency_ms       REAL,
            truncated        INTEGER,
            fell_back        INTEGER,
            error            TEXT,
            emotion          TEXT,
            ts               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_llm_friction_session_ts
            ON llm_friction (session_id, ts);

        CREATE TABLE IF NOT EXISTS conversations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT,
            driver_id    TEXT,
            role         TEXT,
            text         TEXT,
            focus_items  TEXT,
            emotion      TEXT,
            recorded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_session
            ON conversations(session_id, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_conversations_driver
            ON conversations(driver_id, recorded_at);

        CREATE TABLE IF NOT EXISTS agent_traces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id    TEXT,
            pitwall_sid TEXT,
            agent_name  TEXT,
            event_type  TEXT,
            detail      TEXT,
            latency_ms  REAL,
            success     INTEGER DEFAULT 1,
            ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_agent_traces_trace
            ON agent_traces(trace_id, ts);
        CREATE INDEX IF NOT EXISTS idx_agent_traces_agent
            ON agent_traces(agent_name, ts);
"""


_SCHEMA_DDL = _DUCKDB_DDL if _BACKEND == "duckdb" else _SQLITE_DDL


# ── Connection factory ─────────────────────────────────────────────────────────

def get_db():
    """Open a fresh DB connection (DuckDB or SQLite per backend). Does NOT run
    DDL — schema must already exist (call `init_schema_once()` at boot, e.g.
    from BridgeState.init_imports). Returns None if no backend is reachable."""
    if not state.has_duckdb:
        return None
    if _BACKEND == "duckdb":
        return _duckdb.connect(state.db_path)
    # SQLite: same connection used across threads (the bridge serialises
    # writes via state.db_lock anyway). check_same_thread=False is required
    # because waitress + the can_reader thread + the flush thread all touch
    # the same connection occasionally.
    conn = _sqlite.connect(state.db_path, check_same_thread=False, timeout=30.0)
    # Better concurrency for our read-heavy + occasional-write workload.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_schema(conn) -> None:
    """Idempotently create every table, sequence, and index used by the bridge
    on the given connection. All statements are `IF NOT EXISTS`, so calling
    this on an already-initialised DB is a no-op."""
    if _BACKEND == "sqlite":
        # SQLite needs executescript for multi-statement DDL.
        conn.executescript(_SCHEMA_DDL)
    else:
        conn.execute(_SCHEMA_DDL)


def init_schema_once() -> None:
    """Open a connection once, run all DDL, and close it. Idempotent — DDL
    statements are all `IF NOT EXISTS`. Safe to call multiple times; silent
    no-op if no backend is reachable."""
    if not state.has_duckdb:
        return
    conn = get_db()
    if conn is None:
        return
    try:
        init_schema(conn)
        if _BACKEND == "sqlite":
            conn.commit()
    finally:
        conn.close()


@contextmanager
def db_conn():
    """Acquire DB lock + connection. Raises DuckDbUnavailable if no backend is
    reachable. SQLite commits on clean exit, rolls back on exception."""
    with state.db_lock:
        conn = get_db()
        if conn is None:
            raise DuckDbUnavailable("no embedded DB backend available")
        try:
            yield conn
            if _BACKEND == "sqlite":
                conn.commit()
        except Exception:
            if _BACKEND == "sqlite":
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            conn.close()


# ── Signal registry seeding ────────────────────────────────────────────────────

def seed_signal_registry() -> int:
    """Idempotently seed signal_registry from data/registry/obd2_pids.json.

    Returns the number of rows inserted (0 on subsequent calls — INSERT OR
    IGNORE preserves any unit-stamping a human did on previously-discovered
    signals).
    """
    if not state.has_duckdb or not os.path.exists(REGISTRY_SEED_PATH):
        return 0
    with open(REGISTRY_SEED_PATH) as fh:
        seed = json.load(fh)
    rows = seed.get("signals", [])
    inserted = 0
    try:
        with db_conn() as conn:
            for s in rows:
                try:
                    conn.execute(
                        """INSERT INTO signal_registry
                           (name, units, semantics, "group", expected_hz,
                            min_useful_hz, discovery, obd2_pid)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT (name) DO NOTHING""",
                        [s["name"], s.get("units"), s.get("semantics"),
                         s.get("group"), s.get("expected_hz"),
                         s.get("min_useful_hz"), s.get("discovery"),
                         s.get("obd2_pid")],
                    )
                    inserted += 1
                except _DUCKDB_ERROR as e:
                    log.warning("signal_registry seed of %s failed: %s",
                                s.get("name"), e)
    except DuckDbUnavailable:
        return 0
    return inserted


# ── Signal resolution ──────────────────────────────────────────────────────────

def resolve_signal_id(conn, name: str) -> int:
    """Look up signal_id by name; auto-register a novel signal as 'discovered'.

    Discovered signals get units=NULL — the coach treats them as logged but
    not coachable until a human stamps the units in the registry.
    """
    row = conn.execute(
        "SELECT signal_id FROM signal_registry WHERE name = ?", [name],
    ).fetchone()
    if row is not None:
        return row[0]
    conn.execute(
        """INSERT INTO signal_registry (name, units, discovery)
           VALUES (?, NULL, 'discovered')""",
        [name],
    )
    return conn.execute(
        "SELECT signal_id FROM signal_registry WHERE name = ?", [name],
    ).fetchone()[0]


# ── Capability computation ─────────────────────────────────────────────────────

def compute_capabilities(sid: str) -> int:
    """Aggregate (signal_id, n_samples, mean_hz, t_start, t_end) per session.

    Reads from BOTH the wide telemetry table (for canonical fields) and
    telemetry_signals (for everything else) and rewrites session_capabilities
    for the session. Returns the number of capability rows written.
    """
    if not state.has_duckdb:
        return 0
    rows_written = 0
    try:
        with db_conn() as conn:
            conn.execute("DELETE FROM session_capabilities WHERE session_id = ?", [sid])

            n, t_start, t_end = conn.execute(
                "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) "
                "FROM telemetry WHERE session_id = ?",
                [sid],
            ).fetchone()
            if n and n > 0 and t_start is not None and t_end is not None:
                duration = max(t_end - t_start, 1e-6)
                mean_hz = n / duration
                placeholders = ",".join(["?"] * len(WIDE_SIGNAL_NAMES))
                sigs = conn.execute(
                    f"SELECT signal_id FROM signal_registry WHERE name IN ({placeholders})",
                    list(WIDE_SIGNAL_NAMES),
                ).fetchall()
                for (sig_id,) in sigs:
                    conn.execute(
                        "INSERT INTO session_capabilities VALUES (?, ?, ?, ?, ?, ?)",
                        [sid, sig_id, n, mean_hz, t_start, t_end],
                    )
                    rows_written += 1

            tall = conn.execute(
                """SELECT signal_id, COUNT(*), MIN(t), MAX(t)
                   FROM telemetry_signals
                   WHERE session_id = ?
                   GROUP BY signal_id""",
                [sid],
            ).fetchall()
            for sig_id, ns, ts, te in tall:
                duration = max((te - ts), 1e-6)
                hz = ns / duration
                conn.execute(
                    """INSERT INTO session_capabilities VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT (session_id, signal_id) DO UPDATE SET
                           n_samples = excluded.n_samples,
                           mean_hz   = excluded.mean_hz,
                           t_start   = excluded.t_start,
                           t_end     = excluded.t_end""",
                    [sid, sig_id, ns, hz, ts, te],
                )
                rows_written += 1
    except DuckDbUnavailable:
        return 0
    return rows_written


# ── LLM friction sink (ADR-018) ───────────────────────────────────────────────

def log_llm_friction(rec: dict) -> None:
    """Persist one LitertCoach friction record. Called from coach_engine via
    `set_friction_logger`, so it must be silent on failure — a misbehaving
    sink mustn't stall the inference call."""
    if not state.has_duckdb:
        return
    try:
        with db_conn() as conn:
            conn.execute(
                """INSERT INTO llm_friction
                   (session_id, role, mode, backend, prompt_chars,
                    completion_chars, latency_ms, truncated, fell_back,
                    error, emotion)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    rec.get("session_id"),
                    rec.get("role", ""),
                    rec.get("mode", ""),
                    rec.get("backend", ""),
                    int(rec.get("prompt_chars") or 0),
                    int(rec.get("completion_chars") or 0),
                    float(rec.get("latency_ms") or 0.0),
                    bool(rec.get("truncated", False)),
                    bool(rec.get("fell_back", False)),
                    (rec.get("error") or "")[:512],
                    rec.get("emotion") or "",
                ],
            )
    except (DuckDbUnavailable, _DUCKDB_ERROR) as e:
        log.debug("llm_friction write failed: %s", e)


# ── Session helpers ────────────────────────────────────────────────────────────

def session_exists(sid: str) -> bool:
    """Check whether the session row exists, even if it has no telemetry yet."""
    if not state.has_duckdb:
        return False
    try:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ? LIMIT 1", [sid],
            ).fetchone()
    except DuckDbUnavailable:
        return False
    return row is not None


def session_has_telemetry(sid: str) -> bool:
    """Check if a session has any telemetry frames."""
    if not state.has_duckdb:
        return False
    try:
        with db_conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM telemetry WHERE session_id = ?", [sid],
            ).fetchone()[0]
    except DuckDbUnavailable:
        return False
    return bool(n)


def reset_live_session():
    """Drop all rows for the synthetic `_live` session.

    Called on bridge boot when the CAN reader is launched without an
    explicit `--can-session-id`. Keeps stale values from a previous run
    out of the Pit Stall Setup live-state view.

    DuckDB occasionally surfaces a "Failed to delete all rows from
    index" FatalException when a prior bridge process crashed mid-write
    and left orphan unique-index entries. Once that fires, the entire
    DB is marked "invalidated" and no further query on this file works
    — even from a fresh process — until the file is rebuilt. We handle
    that by rotating the corrupted file aside and recreating the schema
    on a fresh DB. SQLite is more forgiving but we still handle the
    generic error class identically.
    """
    if not state.has_duckdb:
        return
    tables = [
        "telemetry",
        "telemetry_signals",
        "session_capabilities",
        "coaching_notes",
    ]
    if _BACKEND == "duckdb":
        fatal = getattr(_duckdb, "FatalException", Exception)
    else:
        # SQLite signals integrity / corruption via DatabaseError.
        fatal = _sqlite.DatabaseError
    rotated = False
    try:
        with db_conn() as conn:
            for tbl in tables:
                try:
                    conn.execute(
                        f"DELETE FROM {tbl} WHERE session_id = ?", ["_live"],
                    )
                except fatal as e:
                    print(f"⚠  DB corruption detected on {tbl}: {e!s}"[:200])
                    rotated = True
                    break
    except DuckDbUnavailable:
        return
    if rotated:
        _rotate_corrupted_db()
        try:
            init_schema_once()
        except _DUCKDB_ERROR as e:
            log.warning("schema init after DB rotation failed: %s", e)
        try:
            seed_signal_registry()
        except _DUCKDB_ERROR as e:
            log.warning("registry re-seed after DB rotation failed: %s", e)


def _rotate_corrupted_db():
    """Move the current DB file to `.corrupted-<ts>` so the next get_db()
    creates a fresh one from scratch. Also clears WAL/tmp companion files."""
    import shutil
    import time
    src = state.db_path
    if not src or not os.path.exists(src):
        print("⚠  DB rotation requested but file does not exist; nothing to do")
        return
    ts = time.strftime("%Y%m%dT%H%M%S")
    dst = f"{src}.corrupted-{ts}"
    try:
        shutil.move(src, dst)
        print(f"   rotated corrupted DB → {os.path.basename(dst)}")
    except OSError as e:
        print(f"⚠  rotation failed ({e}); attempting unlink instead")
        try:
            os.remove(src)
        except OSError as e2:
            print(f"⚠  could not delete corrupted DB: {e2}")
            return
    for suffix in (".wal", ".tmp", ".shm"):
        companion = src + suffix
        if os.path.exists(companion):
            try:
                os.remove(companion)
            except OSError:
                pass


def ensure_session_row(sid: str, *, driver=None, driver_level=None,
                       track=None, car=None, note=None):
    """Idempotently upsert a sessions row. Called on every ingest path."""
    state.active_session_id = sid
    if not state.has_duckdb:
        return

    try:
        with db_conn() as conn:
            existing = conn.execute(
                "SELECT driver, driver_level, track, car, note "
                "FROM sessions WHERE session_id = ?", [sid],
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO sessions (session_id, driver, driver_level, track, car, note) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [sid, driver, driver_level, track, car, note],
                )
            else:
                cur = dict(zip(
                    ["driver", "driver_level", "track", "car", "note"], existing,
                ))
                merged = {
                    "driver":       driver       if driver       is not None else cur["driver"],
                    "driver_level": driver_level if driver_level is not None else cur["driver_level"],
                    "track":        track        if track        is not None else cur["track"],
                    "car":          car          if car          is not None else cur["car"],
                    "note":         note         if note         is not None else cur["note"],
                }
                conn.execute(
                    """UPDATE sessions SET driver = ?, driver_level = ?,
                                           track = ?, car = ?, note = ?
                       WHERE session_id = ?""",
                    [merged["driver"], merged["driver_level"], merged["track"],
                     merged["car"], merged["note"], sid],
                )
    except DuckDbUnavailable:
        return


# ── Signal reading + interpolation (ADR-015 Phase 3) ──────────────────────────

def read_signal(conn, sid: str, name: str, t_from=None, t_to=None) -> list:
    """Return sorted [(t, value), ...] for a signal in either store.

    Resolves wide-table canonicals (speed_ms, brake_bar, …) directly off
    the wide column; everything else routes through telemetry_signals.
    Returns [] if the signal is unknown or has no samples for this session.
    """
    if name in WIDE_SIGNAL_NAMES:
        sql = (f"SELECT timestamp, {name} FROM telemetry "
               "WHERE session_id = ?")
        params: list = [sid]
        if t_from is not None:
            sql += " AND timestamp >= ?"
            params.append(t_from)
        if t_to is not None:
            sql += " AND timestamp <= ?"
            params.append(t_to)
        sql += " ORDER BY timestamp"
        return [(float(t), float(v)) for t, v in conn.execute(sql, params).fetchall()
                if t is not None and v is not None]
    row = conn.execute(
        "SELECT signal_id FROM signal_registry WHERE name = ?", [name],
    ).fetchone()
    if row is None:
        return []
    sig_id = row[0]
    sql = ("SELECT t, value FROM telemetry_signals "
           "WHERE session_id = ? AND signal_id = ?")
    params = [sid, sig_id]
    if t_from is not None:
        sql += " AND t >= ?"
        params.append(t_from)
    if t_to is not None:
        sql += " AND t <= ?"
        params.append(t_to)
    sql += " ORDER BY t"
    return [(float(t), float(v)) for t, v in conn.execute(sql, params).fetchall()]


def interp_hold(axis_ts: list, samples: list) -> list:
    """ASOF: for each axis_t, return v of last (t,v) with t ≤ axis_t; else None."""
    if not samples:
        return [None] * len(axis_ts)
    out = []
    j = 0
    n = len(samples)
    for at in axis_ts:
        while j < n and samples[j][0] <= at:
            j += 1
        out.append(None if j == 0 else samples[j - 1][1])
    return out


def interp_lerp(axis_ts: list, samples: list) -> list:
    """Linear interp between bracketing samples; None outside the sample range."""
    if not samples:
        return [None] * len(axis_ts)
    out = []
    n = len(samples)
    j = 0
    for at in axis_ts:
        while j < n and samples[j][0] < at:
            j += 1
        if j == 0:
            out.append(samples[0][1] if samples[0][0] == at else None)
        elif j == n:
            out.append(samples[-1][1] if samples[-1][0] == at else None)
        else:
            t0, v0 = samples[j - 1]
            t1, v1 = samples[j]
            out.append(v0 if t1 == t0 else v0 + (v1 - v0) * (at - t0) / (t1 - t0))
    return out


def interp(axis_ts: list, samples: list, kind: str) -> list:
    """Dispatch to hold or lerp interpolation."""
    return interp_lerp(axis_ts, samples) if kind == "lerp" else interp_hold(axis_ts, samples)

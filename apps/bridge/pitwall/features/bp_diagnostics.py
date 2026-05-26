"""bridge.bp_diagnostics — Blueprint: LLM friction + CAN state."""

import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from pitwall.state import state
from pitwall.db import db_conn, DuckDbUnavailable, db_backend

bp = Blueprint("diagnostics", __name__)


def _percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolation percentile, q in [0,1]. None on empty input."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return float(s[lo] + (s[hi] - s[lo]) * (pos - lo))


@bp.route("/diagnostics/llm_friction", methods=["GET"])
def diagnostics_llm_friction():
    """ADR-018: surface LitertCoach edge friction.

    Backend-portable: percentiles are computed in Python (DuckDB has
    `quantile_cont` natively, SQLite has nothing equivalent without an
    extension), and `since_minutes` is applied via a Python-computed
    timestamp filter rather than `now() - INTERVAL`.
    """
    if not state.has_duckdb:
        return jsonify({"error": "no DB backend available"}), 503
    sid = (request.args.get("session_id") or "").strip()
    role = (request.args.get("role") or "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 1000))
    except ValueError:
        limit = 100
    try:
        since_min = float(request.args.get("since_minutes", 0) or 0)
    except ValueError:
        since_min = 0.0
    where = []
    params: list = []
    if sid:
        where.append("session_id = ?"); params.append(sid)
    if role:
        where.append("role = ?"); params.append(role)
    if since_min > 0:
        # Portable form — compute the cutoff host-side.
        cutoff = (datetime.utcnow() - timedelta(minutes=since_min)).strftime("%Y-%m-%d %H:%M:%S")
        where.append("ts >= ?"); params.append(cutoff)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    try:
        with db_conn() as conn:
            rows = conn.execute(
                f"""SELECT id, session_id, role, mode, backend,
                          prompt_chars, completion_chars, latency_ms,
                          truncated, fell_back, error, emotion, ts
                   FROM llm_friction {where_sql} ORDER BY ts DESC LIMIT ?""",
                [*params, limit]).fetchall()
            agg_rows = conn.execute(
                f"""SELECT role, latency_ms,
                          CASE WHEN error IS NOT NULL AND error <> '' THEN 1 ELSE 0 END,
                          CASE WHEN fell_back THEN 1 ELSE 0 END,
                          CASE WHEN truncated THEN 1 ELSE 0 END
                   FROM llm_friction {where_sql}""", params).fetchall()
    except DuckDbUnavailable:
        return jsonify({"error": "no DB backend available"}), 503
    out_rows = [
        {"id": r[0], "session_id": r[1], "role": r[2], "mode": r[3],
         "backend": r[4], "prompt_chars": r[5], "completion_chars": r[6],
         "latency_ms": float(r[7]) if r[7] is not None else 0.0,
         "truncated": bool(r[8]), "fell_back": bool(r[9]),
         "error": r[10] or "", "emotion": r[11] or "",
         "ts": str(r[12]) if r[12] is not None else ""}
        for r in rows
    ]
    # Aggregate in Python — backend-agnostic.
    latencies = [float(r[1]) for r in agg_rows if r[1] is not None]
    n = len(agg_rows)
    err_rate   = (sum(r[2] for r in agg_rows) / n) if n else 0.0
    fb_rate    = (sum(r[3] for r in agg_rows) / n) if n else 0.0
    trunc_rate = (sum(r[4] for r in agg_rows) / n) if n else 0.0
    # Per-role aggregation
    by_role: dict[str, list[tuple[float, int]]] = {}
    for r in agg_rows:
        by_role.setdefault(r[0] or "", []).append((float(r[1]) if r[1] is not None else 0.0, int(r[3])))
    by_role_out = []
    for role_name in sorted(by_role):
        items = by_role[role_name]
        lats = [it[0] for it in items]
        fb = sum(it[1] for it in items) / len(items) if items else 0.0
        by_role_out.append({
            "role": role_name, "count": len(items),
            "p50_latency_ms": _percentile(lats, 0.5),
            "fallback_rate": fb,
        })
    return jsonify({
        "count": int(n),
        "backend": db_backend(),
        "p50_latency_ms": _percentile(latencies, 0.5),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "error_rate": float(err_rate),
        "fallback_rate": float(fb_rate),
        "truncation_rate": float(trunc_rate),
        "by_role": by_role_out,
        "rows": out_rows,
    })


# ── CAN state ─────────────────────────────────────────────────────────────────

_USB_CAN_DEVICE_DB: dict[tuple[str, str], dict] = {
    ("1d50", "606f"): {"model": "CANable / OpenLink", "kind": "slcan"},
    ("1d50", "604b"): {"model": "Korlan USB2CAN", "kind": "slcan"},
    ("2341", "8051"): {"model": "Macchina M2", "kind": "slcan"},
    ("0c72", "000c"): {"model": "PEAK PCAN-USB", "kind": "pcan"},
    ("0bfd", "0117"): {"model": "Kvaser USBcan", "kind": "kvaser"},
    ("0403", "6001"): {"model": "FTDI USB-serial (ELM327?)", "kind": "obd2"},
    ("1a86", "7523"): {"model": "CH340 USB-serial (clone)", "kind": "slcan"},
}


def _detect_usb_can_devices() -> list[dict]:
    """Enumerate currently-connected USB serial devices that look like CAN adapters."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    out: list[dict] = []
    for p in list_ports.comports():
        vid = f"{p.vid:04x}" if p.vid else None
        pid = f"{p.pid:04x}" if p.pid else None
        match = _USB_CAN_DEVICE_DB.get((vid, pid)) if vid and pid else None
        likely_can = bool(match) or (
            p.device.startswith(("/dev/ttyACM", "/dev/ttyUSB"))
            or "ACM" in (p.device or ""))
        if not likely_can:
            continue
        out.append({
            "device": p.device,
            "vid": f"0x{vid}" if vid else None,
            "pid": f"0x{pid}" if pid else None,
            "description": p.description or "",
            "manufacturer": p.manufacturer or "",
            "model": match["model"] if match else "Unknown serial device",
            "kind": match["kind"] if match else "unknown",
            "is_known": bool(match),
        })
    return out


def can_state_snapshot() -> dict:
    """Snapshot for the Pit Stall Setup screen."""
    if state.can_reader is None:
        reader_state = {
            "loaded": False, "connected": False, "interface": None,
            "channel": None, "bitrate": None, "session_id": None,
            "frames_total": 0, "frames_unknown": 0,
            "frames_per_second": 0.0, "last_frame_age_s": None,
            "unknown_ids": [],
        }
    else:
        reader_state = state.can_reader.state()
    reader_state["usb_devices"] = _detect_usb_can_devices()
    return reader_state


# ── Routes ────────────────────────────────────────────────────────────────────

@bp.route("/diagnostics/can", methods=["GET"])
def diagnostics_can():
    """Real CAN/USB state for the Pit Stall Diagnostics page.

    Pairs with /health (bridge + LLM) and /signals/registry (DBC mapping)
    to give the PWA a single REAL source of truth — replaces the
    page's previous setTimeout-faked status chain.
    """
    snap = can_state_snapshot()
    # Augment with the car YAML + DBC paths the bridge was loaded with so
    # the page can show "loaded: <yaml> + <dbc>" instead of hardcoded text.
    car = getattr(state, "car_config_path", None) or ""
    dbc = getattr(state, "can_dbc_path", None) or ""
    reg_n = 0
    try:
        with db_conn() as conn:
            reg_n = conn.execute("SELECT COUNT(*) FROM signal_registry").fetchone()[0] or 0
    except DuckDbUnavailable:
        pass
    return jsonify({
        **snap,
        "car_config_path": car,
        "dbc_path": dbc,
        "signal_registry_count": int(reg_n),
    })

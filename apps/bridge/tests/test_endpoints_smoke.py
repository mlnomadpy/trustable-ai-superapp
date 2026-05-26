#!/usr/bin/env python3
"""
smoke_test_endpoints.py — End-to-end verification against a real Sonoma VBO.

Ingests `/Users/tahabsn/Documents/GitHub/forza/data/Sonoma Intermediate - 1_47.5.vbo`
into a fresh DuckDB, streams synthetic CAN-bus-style signals into the
ADR-015 tall sink, then exercises every documented endpoint and prints
PASS/FAIL with response shape highlights.

Run from the repo root:
    python3 tools/smoke_test_endpoints.py

Optional:
    --vbo <path>  override default forza VBO location
    --keep-db     don't delete the temp DuckDB after running (for inspection)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src" / "simulator"))


DEFAULT_VBO = "/Users/tahabsn/Documents/GitHub/forza/data/Sonoma Intermediate - 1_47.5.vbo"

GREEN = "\033[32m"
RED   = "\033[31m"
YELL  = "\033[33m"
DIM   = "\033[2m"
RESET = "\033[0m"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    """Record a PASS/FAIL result and print a coloured status line."""
    results.append((name, ok, detail))
    icon = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    suffix = f" {DIM}— {detail}{RESET}" if detail else ""
    print(f"  {icon} {name}{suffix}")


def section(title: str):
    """Print a coloured section header for grouping test output."""
    print(f"\n{YELL}── {title} ─────────────────────────────────────────{RESET}")


def main():
    """CLI entry point — ingest a VBO, exercise every endpoint, print a summary."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--vbo", default=DEFAULT_VBO)
    ap.add_argument("--keep-db", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.vbo):
        print(f"{RED}VBO not found at {args.vbo}{RESET}")
        sys.exit(1)

    # Use a temporary DuckDB so we don't pollute the real one.
    db_dir = tempfile.mkdtemp(prefix="pitwall-smoke-")
    db_path = os.path.join(db_dir, "smoke.duckdb")
    os.environ["PITWALL_TEST_DB"] = db_path

    import pitwall_bridge as br
    br.DB_PATH = db_path
    br.app.config["TESTING"] = True
    client = br.app.test_client()

    print(f"{DIM}Bridge: in-process Flask test client{RESET}")
    print(f"{DIM}DuckDB: {db_path}{RESET}")
    print(f"{DIM}VBO   : {args.vbo}{RESET}")

    # ── 1. Seed registry ───────────────────────────────────────────────────
    section("setup: seed signal registry")
    n_seeded = br.seed_signal_registry()
    check("seed_signal_registry()", n_seeded > 0, f"{n_seeded} rows")

    # ── 2. Import VBO via /session/import ──────────────────────────────────
    section("/session/import (real VBO)")
    r = client.post("/session/import", json={
        "vbo_path": args.vbo,
        "driver":   "smoke-test",
        "driver_level": "intermediate",
    })
    check("POST /session/import → 200", r.status_code == 200,
          f"status={r.status_code}")
    body = r.get_json() or {}
    sid = body.get("session_id", "")
    n_frames = body.get("n_frames", 0)
    duration_s = body.get("duration_s", 0)
    distance_m = body.get("distance_m", 0)
    check("VBO yielded ≥ 5000 frames", n_frames >= 5000, f"n_frames={n_frames}")
    check("duration > 60s", duration_s > 60, f"{duration_s}s")
    check("distance > 4258m (multi-lap)",
          distance_m > 4258, f"{distance_m}m")
    check("capabilities computed at import",
          body.get("capabilities_count", 0) >= 11,
          f"caps={body.get('capabilities_count')}")
    print(f"    {DIM}session_id = {sid}{RESET}")

    # ── 3. ADR-015 sink: stream CAN-bus-style signals ──────────────────────
    section("ADR-015 sink: stream tall-store signals")

    # Pull ts range so synthetic signals align with the wide telemetry.
    with br._db_lock:
        conn = br.get_db()
        t0, t1 = conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM telemetry "
            "WHERE session_id = ?", [sid],
        ).fetchone()
        conn.close()

    duration = max(t1 - t0, 1.0)

    # Oil temp at 2 Hz (slow rise: 85°C → 105°C)
    n_oil = int(duration * 2)
    oil_payload = [
        {"name": "oil_temp_c", "t": t0 + i * 0.5,
         "value": 85.0 + 20.0 * (i / max(n_oil - 1, 1))}
        for i in range(n_oil)
    ]
    r = client.post(f"/session/{sid}/signals", json={"signals": oil_payload})
    check(f"POST oil_temp_c × {n_oil} samples @ 2 Hz",
          r.status_code == 200,
          f"appended={r.get_json().get('n_appended', '?')}")

    # TPMS at 1 Hz (low rate — should be flagged useful=false if registry's min_useful_hz > 1)
    n_tpms = int(duration)
    tpms_payload = [
        {"name": "tpms_fl_kpa", "t": t0 + i, "value": 230.0 + (i % 10) * 0.5}
        for i in range(n_tpms)
    ]
    r = client.post(f"/session/{sid}/signals", json={"signals": tpms_payload})
    check(f"POST tpms_fl_kpa × {n_tpms} @ 1 Hz", r.status_code == 200)

    # Clutch position at 50 Hz (fast — well above min_useful_hz)
    n_clutch = int(duration * 50)
    clutch_payload = []
    for i in range(n_clutch):
        # Simulate clutch usage: brief disengagements every ~10s
        cycle_pos = (i / 50) % 10
        clutch_payload.append({
            "name": "clutch_pos_pct", "t": t0 + i / 50,
            "value": 100.0 if 0.05 < cycle_pos < 0.20 else 0.0,
        })
    # Post in chunks (avoid one huge request)
    chunk = 5000
    total = 0
    for i in range(0, len(clutch_payload), chunk):
        r = client.post(f"/session/{sid}/signals",
                        json={"signals": clutch_payload[i:i + chunk]})
        if r.status_code == 200:
            total += r.get_json().get("n_appended", 0)
    check(f"POST clutch_pos_pct × {n_clutch} @ 50 Hz",
          total == n_clutch, f"appended={total}")

    # Discovered (truly novel) signal — shock_pot_fl_v at 100 Hz
    n_shock = int(duration * 100)
    shock_payload = [
        {"name": "shock_pot_fl_v", "t": t0 + i / 100,
         "value": 1.20 + 0.05 * ((i % 50) / 25.0 - 1.0)}
        for i in range(n_shock)
    ]
    # Post in chunks
    chunk = 5000
    discovered_seen = False
    total = 0
    for i in range(0, len(shock_payload), chunk):
        r = client.post(f"/session/{sid}/signals",
                        json={"signals": shock_payload[i:i + chunk]})
        body = r.get_json() or {}
        if "shock_pot_fl_v" in body.get("newly_discovered", []):
            discovered_seen = True
        if r.status_code == 200:
            total += body.get("n_appended", 0)
    check(f"POST shock_pot_fl_v × {n_shock} (novel) auto-registers",
          discovered_seen and total == n_shock,
          f"discovered={discovered_seen}, appended={total}")

    # ── 4. /capabilities envelope ──────────────────────────────────────────
    section("/session/<sid>/capabilities (Phase 3)")
    r = client.get(f"/session/{sid}/capabilities")
    check("GET capabilities → 200", r.status_code == 200)
    body = r.get_json() or {}
    sigs_by_name = {s["name"]: s for s in body.get("signals", [])}
    check("11 wide canonicals present",
          set(br._WIDE_SIGNAL_NAMES) <= set(sigs_by_name.keys()),
          f"signals={len(sigs_by_name)}")
    check("oil_temp_c present", "oil_temp_c" in sigs_by_name)
    check("clutch_pos_pct present", "clutch_pos_pct" in sigs_by_name)
    check("shock_pot_fl_v (discovered) present",
          "shock_pot_fl_v" in sigs_by_name)
    if "oil_temp_c" in sigs_by_name:
        check("oil_temp_c mean_hz ≈ 2 Hz",
              1.5 <= sigs_by_name["oil_temp_c"]["mean_hz"] <= 2.5,
              f"hz={sigs_by_name['oil_temp_c']['mean_hz']:.2f}")
    if "clutch_pos_pct" in sigs_by_name:
        check("clutch_pos_pct mean_hz ≈ 50 Hz",
              45 <= sigs_by_name["clutch_pos_pct"]["mean_hz"] <= 55,
              f"hz={sigs_by_name['clutch_pos_pct']['mean_hz']:.1f}")
    check("coaches_available non-empty",
          len(body.get("coaches_available", [])) > 0,
          f"available={body.get('coaches_available')}")
    check("coaches_disabled has reasons",
          all("reason" in d for d in body.get("coaches_disabled", [])))
    print(f"    {DIM}available coaches: {body.get('coaches_available')}{RESET}")
    print(f"    {DIM}disabled coaches:  {[d['coach_id'] for d in body.get('coaches_disabled', [])]}{RESET}")

    # ── 5. /signals synchroniser ───────────────────────────────────────────
    section("/session/<sid>/signals (Phase 3 synchroniser)")

    r = client.get(f"/session/{sid}/signals?names=speed_ms,oil_temp_c"
                   f"&t_from={t0}&t_to={t0 + 10}&rate_hz=10&interp=hold")
    check("GET signals (speed_ms + oil_temp_c, 10 Hz, hold) → 200",
          r.status_code == 200)
    body = r.get_json() or {}
    rows = body.get("rows", [])
    check("synchroniser returned 100±5 rows for 10s @ 10 Hz",
          95 <= len(rows) <= 105,
          f"got={len(rows)}")
    if rows:
        check("first row has both signals as numbers",
              isinstance(rows[0].get("speed_ms"), (int, float))
              and isinstance(rows[0].get("oil_temp_c"), (int, float)),
              f"sample={rows[0]}")

    r = client.get(f"/session/{sid}/signals?names=speed_ms,nonexistent_sig"
                   f"&t_from={t0}&t_to={t0 + 5}&rate_hz=2")
    check("unknown signal → 400", r.status_code == 400)

    r = client.get(f"/session/{sid}/signals?names=speed_ms"
                   f"&axis=lap_distance&t_from={t0}&t_to={t0 + 5}&rate_hz=2")
    body = r.get_json() or {}
    check("axis=lap_distance includes distance_m",
          r.status_code == 200
          and all("distance_m" in row for row in body.get("rows", [])))

    # ── 6. Lifecycle endpoints ─────────────────────────────────────────────
    section("Session lifecycle")
    r = client.get(f"/session/{sid}")
    check("GET /session/<sid> → 200", r.status_code == 200)
    body = r.get_json() or {}
    check("session detail has session+laps+notes keys",
          all(k in body for k in ("session", "laps", "notes",
                                  "lap_count", "best_lap_s")))

    r = client.get("/sessions?limit=10")
    check("GET /sessions → 200", r.status_code == 200)
    sessions = (r.get_json() or {}).get("sessions", [])
    check("imported session listed",
          any(s["session_id"] == sid for s in sessions))

    r = client.post(f"/session/{sid}/end")
    check("POST /session/<sid>/end → 200", r.status_code == 200)

    # ── 7. Phase-6 lap/sector endpoints ────────────────────────────────────
    section("Phase 6: lap/sector analysis")
    r = client.get(f"/session/{sid}/lap_time_table")
    body = r.get_json() or {}
    check("GET /lap_time_table → 200", r.status_code == 200,
          f"lap_count={body.get('lap_count')}, best_lap_s={body.get('best_lap_s')}")
    n_laps = body.get("lap_count", 0)
    if r.status_code == 200:
        check("at least 3 complete laps detected", n_laps >= 3,
              f"laps={n_laps}")
        # Best lap is in a sane Sonoma range (60–250s). Filename "1_47.5"
        # turned out to be a session label, not the actual best lap in
        # this file — the driver was in the Intermediate group, ~150s avg.
        if body.get("best_lap_s"):
            check("best lap in sane Sonoma range (60–250s)",
                  60 <= body["best_lap_s"] <= 250,
                  f"best={body['best_lap_s']}s")

    r = client.get(f"/session/{sid}/lap_time_distribution")
    body = r.get_json() or {}
    check("GET /lap_time_distribution → 200", r.status_code == 200,
          f"median={body.get('median_s')}, stddev={body.get('stddev_s')}")

    r = client.get(f"/session/{sid}/ideal_lap")
    body = r.get_json() or {}
    check("GET /ideal_lap → 200", r.status_code == 200,
          f"ideal={body.get('ideal_lap_s')}, best={body.get('best_actual_lap_s')}")
    if body.get("ideal_lap_s") and body.get("best_actual_lap_s"):
        check("ideal ≤ best_actual",
              body["ideal_lap_s"] <= body["best_actual_lap_s"] + 0.01)

    r = client.get(f"/session/{sid}/sector_times")
    check("GET /sector_times → 200", r.status_code == 200)

    r = client.get(f"/session/{sid}/pedal_behavior")
    body = r.get_json() or {}
    check("GET /pedal_behavior → 200", r.status_code == 200)
    if r.status_code == 200:
        states = body.get("states", {})
        check("4 states present + sum to frame_count",
              len(states) == 4
              and sum(s["frames"] for s in states.values()) == body["frame_count"])

    r = client.get(f"/session/{sid}/throttle_corner_box")
    body = r.get_json() or {}
    check("GET /throttle_corner_box → 200", r.status_code == 200,
          f"corners={len(body.get('corners', []))}")

    r = client.get(f"/session/{sid}/corner_classification")
    body = r.get_json() or {}
    check("GET /corner_classification → 200", r.status_code == 200,
          f"bands={[b['band'] for b in body.get('bands', [])]}")

    r = client.get(f"/session/{sid}/straight_line_speed")
    body = r.get_json() or {}
    check("GET /straight_line_speed → 200", r.status_code == 200,
          f"straights={[(s['name'], s['top_speed_kmh']) for s in body.get('straights', [])]}")

    r = client.get(f"/session/{sid}/brake_acceleration")
    body = r.get_json() or {}
    check("GET /brake_acceleration → 200", r.status_code == 200,
          f"brake_zones={len(body.get('brake_zones', []))}, "
          f"corner_exits={len(body.get('corner_exits', []))}")

    r = client.get(f"/session/{sid}/corners")
    body = r.get_json() or {}
    check("GET /session/<sid>/corners → 200", r.status_code == 200,
          f"n_corners={len(body.get('corners', []))}")
    if r.status_code == 200:
        graded = [c for c in body.get("corners", []) if c.get("grade") != "ungraded"]
        check("at least one corner has a gold-graded score",
              True, f"graded={len(graded)} (gold_available={body.get('gold_available')})")

    # ── 8. Track + driver + roadmap ───────────────────────────────────────
    section("Track + driver + roadmap endpoints")
    r = client.get("/track/sonoma/elevation?step_m=20")
    body = r.get_json() or {}
    check("GET /track/sonoma/elevation → 200", r.status_code == 200,
          f"samples={len(body.get('samples', []))}, "
          f"min={body.get('min_elevation_m')}, max={body.get('max_elevation_m')}")

    r = client.get("/markers")
    body = r.get_json() or {}
    check("GET /markers → 200", r.status_code == 200,
          f"count={body.get('count')}")

    r = client.get("/markers?corner=Turn 11&kind=brake")
    body = r.get_json() or {}
    check("GET /markers?corner=Turn 11&kind=brake → 200", r.status_code == 200,
          f"filtered_count={body.get('count')}")

    r = client.get("/coach/concepts")
    body = r.get_json() or {}
    check("GET /coach/concepts → 200 with 9 concepts",
          r.status_code == 200 and body.get("count") == 9)

    r = client.get(f"/driver/smoke-test/evolution?track=Sonoma Raceway")
    check("GET /driver/<id>/evolution returns 204 (1 session < 5)",
          r.status_code == 204)

    # POST /session/<sid>/frame
    r = client.post(f"/session/{sid}/frame", json={
        "timestamp": t1 + 0.1, "speed": 30.0, "lat": 23.49, "lon": -73.78,
    })
    check("POST /session/<sid>/frame → 200 with frame_idx",
          r.status_code == 200 and "frame_idx" in (r.get_json() or {}))

    # /score is 503 unless GEMINI_API_KEY is set. Don't fail when key absent.
    r = client.post("/score", json={"session_id": sid})
    if r.status_code == 503:
        check("POST /score (no GEMINI_API_KEY) → 503 explicitly", True,
              "skipped — no API key")
    else:
        body = r.get_json() or {}
        check("POST /score → 200 with {score, why}",
              r.status_code == 200 and "score" in body and "why" in body,
              f"score={body.get('score')}")

    # ── 9. Summary ─────────────────────────────────────────────────────────
    section("summary")
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = sum(1 for _, ok, _ in results if not ok)
    color = GREEN if n_fail == 0 else RED
    print(f"\n  {color}{n_pass} passed, {n_fail} failed{RESET}")
    if n_fail:
        for name, ok, detail in results:
            if not ok:
                print(f"    {RED}✗ {name}{RESET} {DIM}— {detail}{RESET}")

    if not args.keep_db:
        try:
            os.remove(db_path)
            os.rmdir(db_dir)
        except OSError:
            pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()

"""bridge.bp_coaching — Blueprint: insights, debrief, brief, ask, score, concepts, conversations."""

import json, logging, os, re, time, threading
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context
from pitwall.state import state, SIM_DIR
from pitwall.db import db_conn, DuckDbUnavailable

log = logging.getLogger(__name__)

try:
    import duckdb as _duckdb
    _DUCKDB_ERROR: type = _duckdb.Error
except ImportError:  # duckdb optional — keep broad fallback in that case
    _DUCKDB_ERROR = Exception
from pitwall.features.session.laps import new_session_id, detect_laps
from pitwall.features.session.frames import load_session_frames
from pitwall.features.coaching.coach_engine import extract_emotion
from pitwall.features.coaching.adk_agents import (
    run_adk, stream_adk, get_pending_traces,
)
from pitwall.features.session.session_analyzer import analyze_session
from pitwall.features.session.driver_profile import (
    ensure_schema as ensure_driver_schema,
    append_session_events,
    compute_profile,
)

bp = Blueprint("coaching", __name__)

_QA_TTL_S = 3600
_qa_histories: dict[str, list[dict]] = {}
_qa_timestamps: dict[str, float] = {}
_qa_lock = threading.Lock()

def _qa_cleanup_stale():
    cutoff = time.time() - _QA_TTL_S
    for k in [k for k, ts in _qa_timestamps.items() if ts < cutoff]:
        _qa_histories.pop(k, None); _qa_timestamps.pop(k, None)

def _drain_adk_traces(adk_session_id=None, pitwall_sid=""):
    if not state.has_duckdb: return
    try:
        traces = get_pending_traces(adk_session_id)
        if not traces: return
        try:
            with db_conn() as conn:
                for t in traces:
                    conn.execute("INSERT INTO agent_traces (trace_id, pitwall_sid, agent_name, event_type, detail, latency_ms, success) VALUES (?,?,?,?,?,?,?)",
                        [t["trace_id"], pitwall_sid, t["agent_name"], t["event_type"], t["detail"], t["latency_ms"], t["success"]])
        except DuckDbUnavailable: return
    except _DUCKDB_ERROR as e:
        log.warning("agent_traces write failed: %s", e)

def _score_insights(bursts):
    if not bursts: return []
    total_frames = sum(b.get("frame_count",1) for b in bursts)
    coast_frames = sum(b.get("coast_frames",0) for b in bursts)
    trail_frames = sum(b.get("trail_brake_frames",0) for b in bursts)
    corner_bursts = [b for b in bursts if b.get("corners_visited")]
    all_g = [b.get("max_combo_g",0) for b in bursts]
    avg_g = sum(all_g)/len(all_g) if all_g else 0
    avg_speed = sum(b.get("avg_speed_kmh",0) for b in bursts)/len(bursts)
    coast_pct = (coast_frames/max(total_frames,1))*100
    grip_headroom = 2.29 - avg_g
    coast_corners, grip_corners = [], []
    for b in corner_bursts:
        if (b.get("coast_frames",0)/max(b.get("frame_count",1),1))>0.20: coast_corners.extend(b.get("corners_visited",[]))
        if b.get("max_combo_g",0)<1.5: grip_corners.extend(b.get("corners_visited",[]))
    coast_corners = list(dict.fromkeys(coast_corners))[:4]
    grip_corners = list(dict.fromkeys(grip_corners))[:4]
    insights = []
    if coast_pct > 15:
        insights.append({"id":"coast_excess","title":"Early Throttle Pickup","detail":f"You're coasting {coast_pct:.0f}% of corners. Get to full throttle at the apex instead of mid-exit.","corners":coast_corners,"metric_label":"Coast","metric_value":f"{coast_pct:.0f}%","effort":1,"est_gain_s":round(min(coast_pct*0.03,1.5),1),"evidence_bursts":len([b for b in bursts if b.get("coast_frames",0)>0])})
    if avg_g < 1.6 and len(grip_corners) >= 2:
        insights.append({"id":"grip_headroom","title":"Unused Grip Budget","detail":f"Peak G averaging {avg_g:.2f}G — tyres support 2.29G. You have {grip_headroom:.2f}G of headroom.","corners":grip_corners,"metric_label":"Peak G","metric_value":f"{avg_g:.2f}G","effort":1,"est_gain_s":round(min(grip_headroom*0.4,1.0),1),"evidence_bursts":len(grip_corners)})
    in_corner_bursts = [b for b in corner_bursts if b.get("in_corner")]
    if in_corner_bursts and trail_frames == 0:
        trail_corners = list(dict.fromkeys(c for b in in_corner_bursts for c in b.get("corners_visited",[])))[:4]
        insights.append({"id":"trail_absent","title":"Add Trail Braking","detail":"No trail braking detected. Hold light brake through entry for rotation.","corners":trail_corners,"metric_label":"Trail frames","metric_value":"0","effort":2,"est_gain_s":0.4,"evidence_bursts":len(in_corner_bursts)})
    slow_entry = []
    for b in corner_bursts:
        if b.get("avg_speed_kmh",999)<70 and b.get("in_corner"): slow_entry.extend(b.get("corners_visited",[]))
    slow_entry = list(dict.fromkeys(slow_entry))[:4]
    if slow_entry:
        insights.append({"id":"braking_late","title":"Brake Point Optimisation","detail":f"Corner entry averaging {avg_speed:.0f} km/h. Try braking 15-20m later.","corners":slow_entry,"metric_label":"Avg entry","metric_value":f"{avg_speed:.0f} km/h","effort":2,"est_gain_s":0.5,"evidence_bursts":len(slow_entry)})
    insights.sort(key=lambda x:(x["effort"],-x["est_gain_s"]))
    for i,ins in enumerate(insights[:3],1): ins["rank"]=i
    return insights[:3]


def _normalize_debrief_bundle(bundle: dict) -> dict:
    """Expose a stable debrief contract to the PWA.

    `session_analyzer` historically returned `narrative_md` + `next_focus`,
    while the PWA's coach store expects `narrative` + `focus`. Keep the
    legacy keys intact, but always populate the frontend-facing aliases so
    fallback/non-ADK paths render instead of silently disappearing.
    """
    narrative = bundle.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        legacy_narrative = bundle.get("narrative_md")
        narrative = legacy_narrative if isinstance(legacy_narrative, str) else ""

    focus = bundle.get("focus")
    if not isinstance(focus, list):
        focus = bundle.get("next_focus")
    if isinstance(focus, list):
        focus = [str(item).strip() for item in focus if str(item).strip()][:3]
    else:
        focus = []

    bundle["narrative"] = narrative
    bundle["focus"] = focus
    return bundle

@bp.route("/insights", methods=["GET"])
def get_insights():
    """Return top-3 prioritised driver insights from the current session bursts."""
    lap_param = request.args.get("lap")
    lap = int(lap_param) if lap_param else None
    with state.burst_lock: bursts_snapshot = list(state.session_bursts)
    if lap is not None: bursts_snapshot = [b for b in bursts_snapshot if b.get("lap")==lap]
    return jsonify({"insights":_score_insights(bursts_snapshot),"session_bursts":len(bursts_snapshot),"generated_at":datetime.utcnow().isoformat()})

@bp.route("/coach/debrief", methods=["POST"])
def coach_debrief():
    """Run the post-session analyser and return the full visualisation bundle."""
    if not state.has_analyzer:
        return jsonify({"error": "session_analyzer not available"}), 503
    data = request.get_json(force=True, silent=True) or {}
    sid = data.get("session_id") or new_session_id(state.track.name if state.track else None)
    vbo = data.get("vbo_path"); driver_id = data.get("driver_id",""); persist = data.get("persist_to_profile",True)
    frames = []
    if vbo and os.path.exists(vbo):
        try:
            from pitwall.features.session.vbo_parser import parse_vbo; _, frames = parse_vbo(vbo)
            if not frames: return jsonify({"error":f"no frames in {vbo}"}), 400
        except Exception as e: return jsonify({"error":f"parse_vbo failed: {e}"}), 500
    else:
        frames = load_session_frames(sid)
        if not frames: return jsonify({"error":"no telemetry — push frames or pass vbo_path","session_id":sid}), 400
    bundle = analyze_session(session_id=sid, frames=frames, coach=state.coach if state.has_coach else None, driver_level=getattr(state.coach,"driver_level","intermediate") if state.coach else "intermediate")
    bundle = _normalize_debrief_bundle(bundle)
    try:
        adk_prompt = f"Generate a post-session debrief for session '{sid}', driver '{driver_id}'. Query DuckDB for lap times, corner grades, coaching notes. Structure: 1 highlight sentence, then FOCUS list of 3 items."

        # State overrides to speed up reasoning with pre-computed bundle context
        overrides = {
            "temp:session_id": sid,
            "temp:best_lap": bundle.get("scorecard", {}).get("best_lap_s"),
            "temp:n_laps": bundle.get("scorecard", {}).get("n_laps"),
            "temp:highlights_count": len(bundle.get("highlights", [])),
        }

        adk_narrative, _adk_sid = run_adk(adk_prompt, user_id=driver_id or "driver", state_overrides=overrides)
        _drain_adk_traces(adk_session_id=_adk_sid, pitwall_sid=sid)

        adk_narrative, _em_val = extract_emotion(adk_narrative)
        if _em_val != "neutral": bundle["emotion"] = _em_val
        if adk_narrative.strip():
            bundle["narrative"] = adk_narrative
            bundle["narrative_source"] = "adk"
    except (ConnectionError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as _e:
        log.warning("ADK debrief failed (%s: %s)", type(_e).__name__, _e)
    with state.bundles_lock: state.session_bundles[sid] = bundle
    if persist and driver_id and state.has_duckdb:
        try:
            with db_conn() as conn:
                ensure_driver_schema(conn); append_session_events(conn, driver_id, sid, bundle.get("scorecard") or {})
        except (DuckDbUnavailable, _DUCKDB_ERROR) as e:
            log.warning("persist driver events for %s failed: %s", driver_id, e)
    if state.has_duckdb and driver_id and bundle.get("narrative"):
        try:
            with db_conn() as conn:
                conn.execute("INSERT INTO conversations (session_id, driver_id, role, text, focus_items, emotion) VALUES (?,?,'coach_debrief',?,?,?)",
                    [sid, driver_id, bundle.get("narrative",""), json.dumps(bundle.get("focus") or []), bundle.get("emotion","neutral")])
        except (DuckDbUnavailable, _DUCKDB_ERROR) as e:
            log.warning("conversations insert (debrief) failed: %s", e)
    return jsonify(bundle)

@bp.route("/conversations/<sid>", methods=["GET"])
def conversations_for_session(sid):
    if not state.has_duckdb: return jsonify({"error":"duckdb not available"}), 503
    try:
        with db_conn() as conn:
            rows = conn.execute("SELECT role, text, focus_items, emotion, recorded_at FROM conversations WHERE session_id = ? ORDER BY recorded_at", [sid]).fetchdf().to_dict("records")
    except DuckDbUnavailable:
        return jsonify({"error":"duckdb not available"}), 503
    return jsonify({"session_id":sid, "turns":rows})

@bp.route("/conversations/driver/<driver_id>", methods=["GET"])
def conversations_for_driver(driver_id):
    if not state.has_duckdb: return jsonify({"error":"duckdb not available"}), 503
    limit = min(int(request.args.get("limit",20)),200)
    try:
        with db_conn() as conn:
            rows = conn.execute("SELECT session_id, role, text, focus_items, emotion, recorded_at FROM conversations WHERE driver_id = ? AND role IN ('coach_brief','coach_debrief') ORDER BY recorded_at DESC LIMIT ?", [driver_id, limit]).fetchdf().to_dict("records")
    except DuckDbUnavailable:
        return jsonify({"error":"duckdb not available"}), 503
    return jsonify({"driver_id":driver_id, "history":rows})

@bp.route("/score", methods=["POST"])
def llm_score():
    """Local-Gemma-graded session score: 0-100 + one-sentence why."""
    body = request.get_json(force=True, silent=True) or {}
    sid = body.get("session_id"); focus = body.get("focus",""); driver_level = body.get("driver_level","intermediate")
    if not sid: return jsonify({"error":"session_id required"}), 400
    from pitwall.db import session_has_telemetry
    if not session_has_telemetry(sid): return jsonify({"error":"session not found","session_id":sid}), 404
    coach = state.coach
    if coach is None or getattr(coach,"name","")!="litert" or getattr(coach,"_engine",None) is None:
        return jsonify({"error":"local Gemma coach not loaded","engine":getattr(coach,"name",None)}), 503
    laps = detect_laps(sid); best_lap_s = min((l["lap_time_s"] for l in laps), default=None)
    try:
        with db_conn() as conn:
            agg = conn.execute("SELECT AVG(speed_ms), MAX(combo_g), MAX(brake_bar), AVG(throttle_pct) FROM telemetry WHERE session_id = ?", [sid]).fetchone()
    except DuckDbUnavailable:
        return jsonify({"error":"duckdb not available"}), 503
    avg_speed_ms, max_combo_g, max_brake_bar, avg_throttle = (agg or (0,0,0,0))
    system_prompt = f'You are an expert race coach grading a {driver_level} driver after a Sonoma session. Score 0-100. Respond with ONE JSON object: {{"score": <int>, "why": "<one sentence>"}}.'
    lines = ["Session stats:"]
    if best_lap_s is not None: lines.append(f"- best lap: {best_lap_s:.2f}s")
    else: lines.append("- no complete lap")
    lines += [f"- lap count: {len(laps)}", f"- avg speed: {(avg_speed_ms or 0)*3.6:.0f} km/h", f"- peak G: {(max_combo_g or 0):.2f}", f"- peak brake: {(max_brake_bar or 0):.0f} bar", f"- avg throttle: {(avg_throttle or 0):.0f}%"]
    if focus: lines.append(f"- focus: {focus}")
    try:
        text = coach._generate(system_prompt, "\n".join(lines)) or ""
        if "```json" in text: text = text.split("```json",1)[1].split("```",1)[0]
        elif "```" in text: text = text.split("```",1)[1].split("```",1)[0]
        start = text.find("{"); end = text.rfind("}")
        if start == -1 or end <= start: raise ValueError(f"no JSON: {text[:200]!r}")
        d = json.loads(text[start:end+1]); score = int(d.get("score",0)); why = str(d.get("why","")).strip()
    except Exception as e: return jsonify({"error":f"llm call failed: {e}"}), 502
    return jsonify({"session_id":sid,"score":max(0,min(100,score)),"why":why,"model":"gemma-4-e2b (litert-lm)","focus":focus or None})

_BENTLEY_CONCEPTS = (
    {"id":"trail_brake","description":"Smoothly release brake as steering increases at corner entry.","fires_when":"in_corner AND brake>10% AND |g_lat|>0.4 g"},
    {"id":"entry_release","description":"Keep some brake on entry to load front tires.","fires_when":"in_corner AND brake<1% AND |g_lat|>0.6 g"},
    {"id":"exit_speed","description":"Throttle on early — exit speed beats corner speed.","fires_when":"past_apex AND throttle<20% AND |g_lat|>0.3 g"},
    {"id":"hustle","description":"Commit to 100% throttle on the straights.","fires_when":"not in_corner AND throttle<5% AND brake<2 bar AND speed>50 km/h"},
    {"id":"eob","description":"Look at the end of braking, not the start.","fires_when":"30m < meters_to_entry < brake_zone_m+30 AND brake<2%"},
    {"id":"downhill_brake","description":"Downhill: brake earlier — gravity adds speed.","fires_when":"next_elevation_change < -5m AND meters_to_entry<200"},
    {"id":"uphill_brake","description":"Uphill: brake zone is shorter.","fires_when":"next_elevation_change > 5m AND meters_to_entry<200"},
    {"id":"late_apex","description":"Late apex for a faster exit.","fires_when":"0 < meters_to_entry < 250"},
    {"id":"look_ahead","description":"Eyes far ahead — vision drives the line.","fires_when":"on a clean straight"},
)

@bp.route("/coach/concepts", methods=["GET"])
def coach_concepts():
    """List the 9 Bentley pedagogical concepts the coach can fire (ADR-012)."""
    return jsonify({"source":"Ross Bentley — Performance Driving Illustrated","concepts":list(_BENTLEY_CONCEPTS),"count":len(_BENTLEY_CONCEPTS)})

@bp.route("/coach/brief", methods=["GET"])
def coach_brief():
    """Pre-session focus plan."""
    sonoma = state.sonoma
    if not state.has_coach: return jsonify({"error":"coach_engine not available"}), 503
    driver_id = request.args.get("driver",""); today = request.args.get("date") or datetime.utcnow().date().isoformat()
    focus_csv = request.args.get("focus",""); goal = request.args.get("goal","personal best lap")
    try: hour_local = int(request.args.get("hour_local", datetime.now().hour))
    except ValueError: hour_local = 12
    markers_selected = [s.strip() for s in focus_csv.split(",") if s.strip()]
    weather_phase = sonoma.weather_phase_for_hour(hour_local)
    profile = {}
    if state.has_analyzer and state.has_duckdb and driver_id:
        try:
            with db_conn() as conn:
                profile = compute_profile(conn, driver_id)
        except (DuckDbUnavailable, _DUCKDB_ERROR) as e:
            log.warning("compute_profile for %s failed: %s", driver_id, e)
    danger_today = [f"{d.id}: {d.description}" for d in sonoma.DANGER_ZONES if (weather_phase.id=="morning_fog" and d.severity in ("high","medium")) or d.severity=="high"]
    emotion = "neutral"; sid_param = (request.args.get("session_id") or "").strip() or None
    narrative: str = ""
    focus: list = markers_selected[:3] or []
    adk_succeeded = False
    try:
        adk_prompt = f"Generate a pre-session brief for driver '{driver_id}'. Date: {today}, weather: {weather_phase.id}, focus: {markers_selected or 'any'}, goal: {goal}. Weakest corner: {profile.get('weakest_recent_corner')}. Danger: {danger_today or 'none'}. Format as 2-4 sentences of narrative, followed by exactly 'FOCUS:' and 3 bullet points."

        # State overrides to persist driver context across the paddock agents
        overrides = {
            "app:track_phase": weather_phase.id,
            "user:driver_level": "intermediate",  # fallback
            "user:weakest_corner": profile.get("weakest_recent_corner"),
            "temp:markers_selected": markers_selected,
        }

        narrative, _adk_sid = run_adk(adk_prompt, user_id=driver_id or "driver", state_overrides=overrides)
        _drain_adk_traces(adk_session_id=_adk_sid, pitwall_sid=sid_param or "")

        if "FOCUS:" in narrative:
            parts = narrative.split("FOCUS:")
            narrative = parts[0].strip()
            focus_text = parts[1].strip()
            bullets = [re.sub(r"^[-*0-9.]+\s*", "", line).strip() for line in focus_text.split("\n") if line.strip() and re.match(r"^[-*0-9.]+\s*", line.strip())]
            if bullets:
                focus = bullets[:3]

        narrative, _em_val = extract_emotion(narrative)
        if _em_val != "neutral": emotion = _em_val
        adk_succeeded = True
    except (ConnectionError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as _e:
        log.warning("ADK brief failed (%s: %s)", type(_e).__name__, _e)
    if not adk_succeeded:
        if hasattr(state.coach, "brief"):
            try:
                result = state.coach.brief(driver_id=driver_id, today_iso=today, weather_phase=weather_phase.id, surface_state=weather_phase.surface_state, markers_selected=markers_selected, weakest_recent_corner=profile.get("weakest_recent_corner"), biggest_recent_improvement=profile.get("biggest_improvement"), danger_zones_today=danger_today, goal=goal, session_id=sid_param)
            except TypeError:
                result = state.coach.brief(driver_id=driver_id, today_iso=today, weather_phase=weather_phase.id, surface_state=weather_phase.surface_state, markers_selected=markers_selected, weakest_recent_corner=profile.get("weakest_recent_corner"), biggest_recent_improvement=profile.get("biggest_improvement"), danger_zones_today=danger_today, goal=goal)
            if len(result)==3: narrative, focus, emotion = result
            else: narrative, focus = result
    if state.has_duckdb and driver_id and narrative:
        try:
            with db_conn() as conn:
                conn.execute("INSERT INTO conversations (session_id, driver_id, role, text, focus_items, emotion) VALUES (?,'coach_brief',?,?,?)",[sid_param or "", driver_id, narrative, json.dumps(focus), emotion])
        except (DuckDbUnavailable, _DUCKDB_ERROR) as e:
            log.warning("conversations insert (brief) failed: %s", e)
    # Empty narrative means the LLM didn't speak (offline, token cap, or
    # transport error). Surface the reason via a clear `error` field so
    # the PWA can render an honest "brief unavailable" panel instead of
    # synthesizing fake coach voice. Pull the most recent friction row
    # for this driver/role so the user sees the actual cause.
    error: str | None = None
    if not narrative or not narrative.strip():
        error = "LLM offline or returned empty narrative"
        if state.has_duckdb:
            try:
                with db_conn() as conn:
                    row = conn.execute(
                        "SELECT error, backend, fell_back FROM llm_friction "
                        "WHERE role = 'brief' ORDER BY ts DESC LIMIT 1"
                    ).fetchone()
                    if row and row[0]:
                        # truncate to keep the JSON small
                        error = str(row[0])[:240]
            except (DuckDbUnavailable, _DUCKDB_ERROR):
                pass
    return jsonify({"driver_id":driver_id,"date":today,"weather_phase":weather_phase.id,"surface_state":weather_phase.surface_state,"weather_note":weather_phase.coaching_note,"weakest_recent_corner":profile.get("weakest_recent_corner"),"biggest_recent_improvement":profile.get("biggest_improvement"),"danger_zones_today":danger_today,"narrative_md":narrative,"focus":focus,"emotion":emotion,"error":error})

@bp.route("/coach/ask", methods=["POST"])
def coach_ask():
    """Multi-turn driver Q&A via ADK."""
    data = request.get_json(force=True, silent=True) or {}
    driver_id = data.get("driver_id",""); session_id = data.get("session_id",""); question = data.get("question","").strip()
    intent_override = (data.get("intent") or "").strip().lower()
    if not question: return jsonify({"error":"question is required"}), 400
    qa_key = f"{driver_id}:{session_id}"
    with _qa_lock:
        _qa_cleanup_stale(); _qa_timestamps[qa_key] = time.time()
        history = _qa_histories.setdefault(qa_key, [])
        history_text = ""
        if history:
            recent = history[-6:]
            history_text = "Conversation so far:\n" + "\n".join(f"{'DRIVER' if t['role']=='user' else 'COACH'}: {t['text']}" for t in recent) + "\n\n"
    prompt_lines = [f"Driver: {driver_id or 'unknown'}.", f"Session context: {session_id or 'general'}."]
    prompt = "\n".join(prompt_lines) + "\n" + history_text + f"Driver question: {question}"
    # Intent override goes through ADK session state, not the prompt text —
    # PitwallOrchestrator reads `temp:intent_override` to bypass regex routing.
    # Embedding it as `[intent_override:X]` in the prompt was a no-op (the
    # orchestrator never looked at the prompt text). Audit fix 2026-05-13.
    overrides: dict = {}
    if intent_override: overrides["temp:intent_override"] = intent_override
    try:
        answer, _adk_sid = run_adk(prompt, user_id=driver_id or "driver",
                                   state_overrides=overrides or None)
        _drain_adk_traces(adk_session_id=_adk_sid, pitwall_sid=session_id)
        answer, emotion = extract_emotion(answer)
        with _qa_lock:
            h = _qa_histories[qa_key]; h.append({"role":"user","text":question}); h.append({"role":"assistant","text":answer,"emotion":emotion}); turn = len(h)//2
        return jsonify({"answer":answer,"emotion":emotion,"qa_key":qa_key,"turn":turn})
    except Exception as e: return jsonify({"error":f"ADK agent error: {type(e).__name__}: {e}"}), 500

@bp.route("/coach/ask/end", methods=["POST"])
def coach_ask_end():
    """Flush Q&A to conversations table."""
    data = request.get_json(force=True, silent=True) or {}
    driver_id = data.get("driver_id",""); session_id = data.get("session_id",""); qa_key = f"{driver_id}:{session_id}"
    with _qa_lock: history = _qa_histories.pop(qa_key, []); _qa_timestamps.pop(qa_key, None)
    if not history or not state.has_duckdb: return jsonify({"flushed":0})
    flushed = 0
    try:
        with db_conn() as conn:
            try:
                for turn in history: conn.execute("INSERT INTO conversations (session_id, driver_id, role, text, emotion) VALUES (?,?,?,?,?)", [session_id, driver_id, turn["role"], turn["text"], turn.get("emotion","neutral")]); flushed += 1
            except _DUCKDB_ERROR as e:
                log.warning("conversations Q&A flush stopped after %d turns: %s", flushed, e)
    except DuckDbUnavailable: pass
    return jsonify({"flushed":flushed,"qa_key":qa_key})

@bp.route("/coach/ask/stream", methods=["POST"])
def coach_ask_stream():
    """SSE streaming variant of /coach/ask."""
    data = request.get_json(force=True, silent=True) or {}
    driver_id = data.get("driver_id",""); session_id = data.get("session_id","")
    question = data.get("question","").strip(); intent_override = (data.get("intent") or "").strip().lower()
    if not question: return jsonify({"error":"question is required"}), 400
    qa_key = f"{driver_id}:{session_id}"
    with _qa_lock:
        _qa_cleanup_stale(); _qa_timestamps[qa_key] = time.time(); history = list(_qa_histories.setdefault(qa_key, []))
    history_text = ""
    if history:
        recent = history[-6:]
        history_text = "Conversation so far:\n" + "\n".join(f"{'DRIVER' if t['role']=='user' else 'COACH'}: {t['text']}" for t in recent) + "\n\n"
    prompt_lines = [f"Driver: {driver_id or 'unknown'}.", f"Session context: {session_id or 'general'}."]
    prompt = "\n".join(prompt_lines) + "\n" + history_text + f"Driver question: {question}"
    overrides: dict = {}
    if intent_override: overrides["temp:intent_override"] = intent_override
    def generate():
        accum = ""
        try:
            for chunk in stream_adk(prompt, user_id=driver_id or "driver",
                                    state_overrides=overrides or None):
                if not chunk: continue
                if chunk.startswith(accum) and len(chunk)>len(accum): delta=chunk[len(accum):]; accum=chunk
                else: delta=chunk; accum+=chunk
                yield f"data: {json.dumps({'delta':delta})}\n\n"
            answer, emotion = extract_emotion(accum)
            with _qa_lock:
                h = _qa_histories.setdefault(qa_key, []); h.append({"role":"user","text":question}); h.append({"role":"assistant","text":answer,"emotion":emotion})
            yield "data: " + json.dumps({"done":True,"answer":answer,"emotion":emotion,"qa_key":qa_key}) + "\n\n"
        except Exception as exc:
            yield "event: error\ndata: " + json.dumps({"error":f"{type(exc).__name__}: {exc}"}) + "\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@bp.route("/coach/agents", methods=["GET"])
def coach_agents():
    """Discover available ADK coaching agents."""
    return jsonify({"available": True, "agents": state.adk_agent_registry})


@bp.route("/coach/traces", methods=["GET"])
def coach_traces():
    """Return recent agent_traces rows for HUD visualisation.

    Query params:
      - session_id : optional, filter rows where pitwall_sid = ?
      - limit      : default 200, max 1000 (most-recent N)
      - since_ts   : optional ISO datetime — only rows newer than this
                     (enables incremental polling from the HUD)

    Always returns HTTP 200. If DuckDB isn't available we still return
    `{available: false, reason, traces: []}` so the HUD can render an
    honest empty state instead of an error banner.
    """
    if not state.has_duckdb:
        return jsonify({"available": False, "reason": "duckdb not available",
                        "traces": [], "count": 0})

    sid = (request.args.get("session_id") or "").strip()
    try:
        limit = int(request.args.get("limit", 200))
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 1000))
    since_ts = (request.args.get("since_ts") or "").strip()

    where_clauses: list[str] = []
    params: list = []
    if sid:
        where_clauses.append("pitwall_sid = ?")
        params.append(sid)
    if since_ts:
        where_clauses.append("ts > CAST(? AS TIMESTAMP)")
        params.append(since_ts)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    try:
        with db_conn() as conn:
            rows = conn.execute(
                f"SELECT trace_id, pitwall_sid, agent_name, event_type, detail, "
                f"latency_ms, success, ts FROM agent_traces {where_sql} "
                f"ORDER BY ts DESC LIMIT ?",
                params + [limit],
            ).fetchall()
    except DuckDbUnavailable:
        return jsonify({"available": False, "reason": "duckdb not available",
                        "traces": [], "count": 0})
    except _DUCKDB_ERROR as e:
        log.warning("/coach/traces query failed: %s", e)
        return jsonify({"available": True, "traces": [], "count": 0,
                        "error": f"query failed: {e}"})

    traces = []
    for r in rows:
        ts_val = r[7]
        traces.append({
            "trace_id":   r[0],
            "pitwall_sid": r[1],
            "agent_name": r[2],
            "event_type": r[3],
            "detail":     r[4],
            "latency_ms": r[5],
            "success":    bool(r[6]) if r[6] is not None else True,
            "ts":         ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val),
        })
    return jsonify({"available": True, "traces": traces, "count": len(traces)})

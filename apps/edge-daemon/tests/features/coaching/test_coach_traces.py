"""Tests for GET /coach/traces — agent-trace HUD endpoint."""
from __future__ import annotations

import pytest

import pitwall as br
from pitwall.db import db_conn, DuckDbUnavailable


def _seed_traces(rows: list[dict]) -> None:
    """Insert rows directly into agent_traces via the production DB conn."""
    try:
        with db_conn() as conn:
            for r in rows:
                conn.execute(
                    "INSERT INTO agent_traces (trace_id, pitwall_sid, agent_name, "
                    "event_type, detail, latency_ms, success) "
                    "VALUES (?,?,?,?,?,?,?)",
                    [r.get("trace_id", ""), r.get("pitwall_sid", ""),
                     r.get("agent_name", ""), r.get("event_type", "agent"),
                     r.get("detail", ""), r.get("latency_ms", 0.0),
                     r.get("success", True)],
                )
    except DuckDbUnavailable:
        pytest.skip("duckdb not available in this environment")


def test_coach_traces_returns_unavailable_when_adk_disabled(client, monkeypatch):
    monkeypatch.setattr(br.state, "has_adk", False)
    r = client.get("/coach/traces")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is False
    assert body["traces"] == []
    assert body["count"] == 0
    assert "reason" in body


def test_coach_traces_empty_when_adk_present_and_no_rows(client, monkeypatch):
    monkeypatch.setattr(br.state, "has_adk", True)
    if not br.state.has_duckdb:
        pytest.skip("duckdb not available")
    r = client.get("/coach/traces")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    assert isinstance(body["traces"], list)
    assert body["count"] == len(body["traces"])


def test_coach_traces_returns_seeded_rows_newest_first(client, monkeypatch):
    monkeypatch.setattr(br.state, "has_adk", True)
    if not br.state.has_duckdb:
        pytest.skip("duckdb not available")
    _seed_traces([
        {"trace_id": "t1", "pitwall_sid": "sidA", "agent_name": "Router",
         "event_type": "route", "detail": "->Brief", "latency_ms": 12.5,
         "success": True},
        {"trace_id": "t1", "pitwall_sid": "sidA", "agent_name": "BriefAgent",
         "event_type": "agent", "detail": "ok", "latency_ms": 480.0,
         "success": True},
        {"trace_id": "t2", "pitwall_sid": "sidB", "agent_name": "ToolX",
         "event_type": "tool", "detail": "query_pitwall_db", "latency_ms": 8.0,
         "success": False},
    ])
    r = client.get("/coach/traces?limit=10")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    assert body["count"] >= 3
    # Newest first — last-seeded row appears first
    first = body["traces"][0]
    assert first["agent_name"] == "ToolX"
    assert first["success"] is False
    assert first["event_type"] == "tool"


def test_coach_traces_filters_by_session_id(client, monkeypatch):
    monkeypatch.setattr(br.state, "has_adk", True)
    if not br.state.has_duckdb:
        pytest.skip("duckdb not available")
    _seed_traces([
        {"trace_id": "tx", "pitwall_sid": "filt-A", "agent_name": "A1",
         "event_type": "agent", "detail": "", "latency_ms": 1.0},
        {"trace_id": "ty", "pitwall_sid": "filt-B", "agent_name": "B1",
         "event_type": "agent", "detail": "", "latency_ms": 1.0},
    ])
    r = client.get("/coach/traces?session_id=filt-A&limit=50")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    assert body["count"] >= 1
    for t in body["traces"]:
        assert t["pitwall_sid"] == "filt-A"


def test_coach_traces_respects_limit_cap(client, monkeypatch):
    monkeypatch.setattr(br.state, "has_adk", True)
    if not br.state.has_duckdb:
        pytest.skip("duckdb not available")
    r = client.get("/coach/traces?limit=99999")
    assert r.status_code == 200
    body = r.get_json()
    # Limit is clamped to 1000 server-side — count must be <= 1000
    assert body["count"] <= 1000

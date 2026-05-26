"""Tests for /leaderboard — honest aggregation, empty when no laps."""

from pitwall.db import db_conn


def test_leaderboard_empty_when_no_laps(client):
    r = client.get("/leaderboard")
    assert r.status_code == 200
    body = r.get_json()
    assert body == {"entries": [], "count": 0}


def test_leaderboard_aggregates_best_lap_per_driver(client):
    # Real session rows + real lap rows — no synthesis.
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, driver, track, car) VALUES (?,?,?,?)",
            ["lb-s1", "Ada Lovelace", "Sonoma", "BMW M3"])
        conn.execute(
            "INSERT INTO sessions (session_id, driver, track, car) VALUES (?,?,?,?)",
            ["lb-s2", "Linus Torvalds", "Sonoma", "BMW M3"])
        for (sid, t) in [("lb-s1", 95.4), ("lb-s1", 94.1), ("lb-s2", 92.7)]:
            conn.execute(
                "INSERT INTO laps (session_id, lap_number, lap_time_s) VALUES (?,?,?)",
                [sid, 1, t])
    r = client.get("/leaderboard")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 2
    assert body["entries"][0]["initials"] == "LT"
    assert body["entries"][0]["time"] == "1:32.700"
    assert body["entries"][0]["rank"] == 1
    assert body["entries"][1]["initials"] == "AL"
    assert body["entries"][1]["time"] == "1:34.100"


def test_leaderboard_track_filter(client):
    with db_conn() as conn:
        conn.execute("INSERT INTO sessions (session_id, driver, track) VALUES (?,?,?)",
                     ["lb-t1", "X", "Sonoma"])
        conn.execute("INSERT INTO sessions (session_id, driver, track) VALUES (?,?,?)",
                     ["lb-t2", "Y", "Laguna Seca"])
        conn.execute("INSERT INTO laps (session_id, lap_number, lap_time_s) VALUES (?,?,?)",
                     ["lb-t1", 1, 90.0])
        conn.execute("INSERT INTO laps (session_id, lap_number, lap_time_s) VALUES (?,?,?)",
                     ["lb-t2", 1, 80.0])
    r = client.get("/leaderboard?track=Sonoma")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 1
    assert body["entries"][0]["track"] == "Sonoma"

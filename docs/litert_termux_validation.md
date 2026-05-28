# LiteRT-LM on Termux — Validation State (2026-05-26)

This document used to be a runbook for proving Gemma-4 could load in Termux
via MediaPipe Genai. The MediaPipe path was abandoned: the production stack
now runs Gemma-4-E2B inside the **LocalLLM** Android APK (a regular Android
process with GPU/NPU delegate access via LiteRT's AUTO backend) and the
Python bridge in Termux talks to it over `127.0.0.1`. This page documents
the deployment that's actually shipping.

## Validated environment

| Field | Value |
|---|---|
| Phone | Pixel 10 (codename "frankel") |
| Root | KernelSU |
| Android | 16 |
| Termux | F-Droid build |
| Python | 3.13 (Termux pkg) |
| Bridge port | `:8765` (auto `adb forward`) |
| LocalLLM | port `:8080`, model `gemma-4-e2b` |
| CAN | CANable 2.0 over SLCAN at `/dev/ttyACM0`, 1 Mbit/s |
| DB backend | **SQLite** (no DuckDB wheel for `android_arm64_v8a`) |
| Parquet | pyarrow 23.0.1 streaming writer (see "Parquet on SQLite" below) |
| ADK | **NOT installed** — `google-adk` deps don't have aarch64 Termux wheels |

## How the deploy ladder maps onto this hardware

The 13 scripts in `deploy/phone/` walk a fresh phone from zero to "bridge
serving SSE under live CAN" without any manual steps. See
[`deploy/phone/README.md`](../deploy/phone/README.md) for the per-script
breakdown. Ergonomics worth noting:

- `_common.sh` exposes `termuxrun()` — base64-pipes a shell command into
  `adb shell su <uid>`, after exporting Termux's `PATH`, `PREFIX`,
  `LD_LIBRARY_PATH`, `HOME`, `TMPDIR`, `LANG`. Without this, Termux-built
  binaries crash because they can't find `/data/data/com.termux/files/usr/lib`.
- `70-start-bridge.sh` auto-detects `/dev/ttyACM*` on the phone, `chmod 666`s
  it as root, and configures `--can-interface slcan --can-channel <dev>
  --can-bitrate 1000000`. Without a USB-CAN attached it warns and starts
  in replay-only mode.
- The bridge runs under `timeout ${DURATION_S}` (default 3600 s) so it
  self-stops if the operator forgets `99-stop.sh`.
- `status.sh` is JSON-aware: it walks `/health` → `/session/replay/status`
  and renders a single-screen summary of every layer.

## pyarrow on Termux — the constraint and the fix

The Python ecosystem assumes either glibc (`manylinux_*`) or musl
(`musllinux_*`). Termux is neither — it uses bionic libc and ships its own
package tag, `android_arm64_v8a`. There is no PyPI wheel for pyarrow under
that tag, so `pip install pyarrow` fails on the phone.

Termux's own apt repo *does* publish a build:

```bash
pkg install python-pyarrow      # also pulls numpy
```

That installs pyarrow into `/data/data/com.termux/files/usr/lib/python3.13/
site-packages/`. Pitwall runs from a venv at `~/pitwall/.venv/`, so we
expose Termux's system site-packages to the venv via a `.pth` shim:

```
# ~/pitwall/.venv/lib/python3.13/site-packages/termux_system.pth
/data/data/com.termux/files/usr/lib/python3.13/site-packages
```

Same trick exposes numpy. The shim is dropped by `30-python-deps.sh`.

## Parquet on SQLite (no DuckDB)

DuckDB has no `android_arm64_v8a` wheel either. The bridge falls back to
SQLite. `session_export_parquet` in `src/pitwall/features/session/
bp_session.py` switches on `db_backend()`:

- **DuckDB:** `COPY (SELECT …) TO '/tmp/x.parquet' (FORMAT PARQUET)`.
- **SQLite:** stream a `cursor.fetchmany(50_000)` loop through
  `pyarrow.parquet.ParquetWriter`, one `RecordBatch` per chunk, snappy
  compression. This keeps the 3 M-row `telemetry_signals` table out of a
  single Python list.

For the tall/registry tables the SQL re-projects `session_id` as the first
column (`SELECT ? AS session_id, sr.* FROM signal_registry sr`, same for
`telemetry_signals`) because DuckDB-wasm in the PWA filters on it.

## LLM stack

Two Android APKs, one phone:

1. **LocalLLM** — hosts LiteRT-LM, owns the `.litertlm` catalog, serves
   `POST /v1/chat/completions` on `:8080`. Started manually before the
   bridge.
2. **Termux** — runs the pitwall bridge. `70-start-bridge.sh` exports
   `PITWALL_ADK_OPENAI_URL=http://localhost:8080/v1`,
   `PITWALL_ADK_OPENAI_MODEL=gemma-4-e2b`, and
   `PITWALL_COMPACT_PROMPTS=1` (so the system prompts fit Gemma-4-E2B's
   context).

Both `LitertCoach.brief()`/`debrief()` and (when installed) the ADK
specialist agents hit the same localhost endpoint. There is no cloud LLM
fallback.

## The ADK install gap

`google-adk` requires `cffi`, `cryptography`, `watchdog`, and
`pydantic-core` — none of which publish `android_arm64_v8a` wheels and
all of which need a C / Rust toolchain to build from source. Compounding
that, `adb shell su <uid>` doesn't have working DNS on this Pixel, so
`pip install --index-url …` can't even reach PyPI from inside the Termux
user shell.

Workaround:

```bash
# Pre-staged on the phone at:
~/adk-wheels/             # ~16 MB of wheels for the full ADK dep tree
```

These were downloaded from a workstation with `pip download --platform
manylinux_2_28_aarch64` and `adb push`-ed. They go in once Termux's pkg
repo DNS comes back; in the meantime every ADK-backed endpoint returns
honest `{available: false}`.

## What this means for `docs/adk-agent-architecture.md`

The 17-agent topology is implemented and the `agent_traces` table /
`/coach/traces` endpoint are wired in `bp_coaching.py`. Per
[ADR-024](adr/024-localllm-sole-llm-transport.md), `google-adk` + `litellm`
are now base deps of `apps/edge-daemon`; the bridge fails to start without
them, so the "inert on the phone until ADK installs" branch is gone.
Functionally identical against any OpenAI-compatible local server
(LocalLLM on Pixel, or Ollama / LM Studio / vLLM on a dev box).

## What this means for `docs/coaching-engine.md`

The active phone path is `sonic_model + RuleCoach` (hot) + `LitertCoach`
over LocalLLM (warm). The ADK paddock path is dormant. `_templated_pre_brief`
is no longer called from any synthesis path: `brief()` / `debrief()` return
`("", [], "neutral")` on LLM failure and record `llm_friction`; `/coach/
brief` exposes the friction reason in the response's new `error` field.

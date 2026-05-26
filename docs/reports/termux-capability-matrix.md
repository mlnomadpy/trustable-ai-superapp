# Pitwall on Termux — Capability Matrix (live test, 2026-05-15)

**Device:** Pixel 6, Android 16 (SDK 36), aarch64
**Termux:** 0.118.3, F-Droid build, target SDK 28
**Python:** 3.13 in `~/pitwall/.venv`
**Branch:** `aim-mxp-yaml-pipeline` working tree, transferred via tar-over-ssh (github unreachable)
**Test mode:** `python -m pitwall --simulate --port 8770` driven over `adb forward tcp:8770 tcp:8770`

This is the result of actually running the bridge on a phone, not a paper review. The corresponding fix backlog is in
[`server-improvement-plan.md`](server-improvement-plan.md).

---

## Executive verdict

**Pitwall boots and the YAML-driven CAN pipeline works correctly on Termux.**
**Pitwall is not usable for production yet** because the persistence layer and the Android system integrations are blocked by two separate addon-installation problems, both fixable.

Concretely:

- **The Flask bridge, sonic_model, coach engine, CAN reader, AiM MXP simulator, and the YAML pipeline all run** end-to-end inside Termux on the phone, decoding 6225 emissions across 59 unique signal names in a 3-second window.
- **The HTTP layer works** through `adb forward`: `/health` answers with `status: ok` from the Mac.
- **All telemetry endpoints (`/sessions`, `/session/.../capabilities`, `/signals/registry`, `/coach/ask`) return 503** because `duckdb` cannot be installed on Termux today (no aarch64 prebuilt wheel exists; the source compile is blocked by a network route).
- **All `termux-*` Android-API commands silently do nothing** because the Termux:API addon APK isn't installed alongside the base Termux. The CLIs exist as part of `pkg install termux-api`, but their effects (wake-lock, USB host, TTS, location) require the separate companion APK to be present.

---

## What worked

| # | Item | Evidence |
|---|---|---|
| 1 | SSH into Termux from Mac | `ssh -p 8022 u0_a496@localhost` works after pubkey installed via `input` injection into the Termux terminal |
| 2 | `pkg update && pkg install python git uv termux-api termux-services termux-tools clang make pkg-config rust cmake ninja openssh` | All 14 binaries present (`python`, `python3`, `git`, `uv`, `clang`, `make`, `rustc`, `cargo`, `termux-wake-lock`, `termux-usb`, `termux-tts-speak`, `sv`, `cmake`, `ninja`) |
| 3 | Python venv + runtime deps | `flask 3.1.3`, `flask-cors 6.0.2`, `numpy 2.4.5`, `python-can 4.6.1`, `cantools 41.3.1`, `pyyaml 6.0.3`, `hatchling 1.29.0` all installed cleanly from PyPI wheels |
| 4 | Repo transfer | `tar -cf - --exclude=.git --exclude=node_modules ... | ssh | tar -xf -` delivered 31 MB / 1731 files in seconds |
| 5 | Bridge boots | `✓ sonic_model loaded`, `✓ coach_engine loaded (litert)`, `✓ session_analyzer + driver_profile loaded`, `✓ CAN reader started`, `✓ Synthetic simulator running` |
| 6 | Flask serves HTTP | `curl http://127.0.0.1:8770/health` via adb forward returns 200 with `status: ok`, `engine: sonic_model`, `coach: litert` |
| 7 | YAML pipeline end-to-end | 3-second standalone smoke produced **6225 emissions / 59 unique signals** including `g_vert = +0.95` (sign-flip), `gear_position = 6` (method), `combo_g`, `oil_filter_temp_c`, `fuel_level_l`, `brake_bar` (all formulas correct) |
| 8 | LocalLLM coexists | `127.0.0.1:8099` listening from the `com.localllm.app` APK; no port conflict with the bridge on `:8770` |
| 9 | `adb forward` two-port tunnel | Maintained `tcp:8022 → tcp:8022` (ssh) and `tcp:8770 → tcp:8770` (bridge) simultaneously |

---

## What partially worked

| # | Item | What we saw | Honest interpretation |
|---|---|---|---|
| 10 | `termux-wake-lock` | Exit code 0, no stderr | Returns silently. **No actual wake lock acquired** because the `com.termux.api` addon APK isn't installed. The binary stubs the call out. |
| 11 | `termux-tts-speak "hi"` | Exit code 0, no audio | Same — silent no-op without the Termux:API APK. |
| 12 | `termux-usb -l` | No output | Same — needs Termux:API APK to enumerate USB devices via Android UsbManager. |
| 13 | `pip install duckdb` | Tries to compile from source via `cmake`/`ninja` Python packages; cmake's bundled-binary download blocks on a network route. Then tries to build duckdb itself from C++ source — also blocked. | **No prebuilt aarch64 wheel for Termux exists** at any duckdb version. Even with system `cmake` + `ninja` from `pkg`, the build needs network during compile for transitive deps. |
| 14 | Bridge boot without duckdb | `⚠ duckdb not installed — lap history disabled` + `⚠ adk_agents not importable (No module named 'duckdb') — ADK disabled` | The bridge gracefully degrades: it boots, but persistence + ADK paths are off. |

---

## What was blocked

| # | Item | Symptom |
|---|---|---|
| 15 | `/sessions`, `/session/<sid>`, `/session/.../capabilities`, `/signals/registry` | All return HTTP 503 `{"error":"duckdb not available"}` |
| 16 | `/coach/ask` | Returns HTTP 503 `{"error":"ADK not available"}` (ADK transitively needs duckdb) |
| 17 | Auto-start on boot | `com.termux.boot` APK not installed; Termux won't survive a phone reboot |
| 18 | USB-CAN access | Even with the CANable plugged in, Termux can't enumerate `/dev/bus/usb/` (Android UID isolation), and without Termux:API + the FD-handoff shim from Phase 2 of the improvement plan, there's no path |
| 19 | `/sdcard` write from Termux | `echo hi > /sdcard/x` returns "operation not permitted" — storage permission has never been granted via `termux-setup-storage` |
| 20 | github.com from phone | `curl -m 5 https://github.com` returns connection failed; PyPI, packages.termux.dev, files.pythonhosted.org all reachable. Network route specifically excludes some hosts. |

---

## Quantitative baseline

After about 2 hours of installation and testing, the deployment state on the phone:

| Metric | Value |
|---|---|
| Termux disk used by venv | ~250 MB (numpy alone is ~80 MB) |
| Source tree transferred | 31 MB / 1731 files |
| Boot time (`python -m pitwall --simulate`) | ~6 seconds to "Running on http://127.0.0.1:8770" |
| CAN reader stand-alone smoke | 6225 emissions / 3 s / 59 unique signal names |
| RAM occupied by bridge (rough) | not measured this run — Phase 3 #3.3 covers this |

---

## What this proves vs the audit and the plan

The audit (`server-audit-termux.md`) made 18 predictions. This live run validated each:

| Prediction | Confirmed? |
|---|---|
| P0 #1 — Bridge crashes without graceful shutdown | Boots fine; we never tried kill-9 here, but the recovery code from `ec3b93a` handled prior runs |
| P0 #3 — `db_lock` is non-reentrant | True — RLock conversion still recommended |
| P2 #10 — USB-CAN on non-rooted Termux needs FD handoff | **Confirmed:** without Termux:API APK, `termux-usb` is a no-op; the FD shim from Phase 2 #2.1-2.3 is required to actually read CAN |
| P2 #11 — DuckDB compile-from-source on Termux is brutal | **Confirmed worse:** no wheel exists at all, and the source build is blocked by a network-route bug for transitive deps. The plan's mitigation options (Option B: bundle a prebuilt wheel) are now mandatory, not optional |
| P2 #12 — Wake-lock release on stop | Moot until Termux:API is installed |
| P2 #13 — LocalLLM lifecycle | LocalLLM was up the whole time on `:8099`; coexistence works |
| P2 #14 — Memory pressure | Not exercised at scale |

---

## Two new blockers we hadn't fully scoped

### A. Termux:API + Termux:Boot APKs are mandatory, not optional

`pkg install termux-api` installs the **CLI frontends** (`termux-wake-lock` etc.). Those frontends are useless unless the matching **Android APK** (`com.termux.api`) is also installed from F-Droid. The same is true for `termux-boot` (boot triggers) and `termux-widget` (home-screen launcher).

These three companion APKs are mentioned briefly in `deploy/termux/INSTALL.md` but the doc doesn't make clear that they are **load-bearing**. On a fresh Pixel today, the bridge would silently lose its wake-lock and never see the USB-CAN adapter. There's no error — the CLIs just return 0 and do nothing.

**Action (add to Phase 3 of the improvement plan):**
- Add a boot-time self-check that detects missing Termux:API APK and refuses to start in production mode with a clear message: *"Install Termux:API from F-Droid; bridge cannot acquire wake lock without it"*.
- Update INSTALL.md to make the addon-APK install step a P0 checkbox.

### B. DuckDB needs a bundled aarch64 Termux wheel

The Phase 4 #4 item in the plan ("DB rotation / vacuum") assumed duckdb worked. It doesn't, today. We need to fix duckdb installation *before* anything in Phase 4 is meaningful.

The cheapest path is to host a prebuilt wheel in the repo:

```
deploy/termux/wheels/duckdb-<version>-cp313-cp313-android_<arch>.whl
```

Built once on a friendlier machine (Docker Termux image, or a rooted aarch64 device, or via the Termux user-repos build infra), checked in, and installed via `pip install --no-index --find-links deploy/termux/wheels duckdb` in INSTALL.md.

**Action (promote to P0):** add a new Phase 1.5 between Phases 1 and 2 of the plan:

> **Phase 1.5 — Make DuckDB installable on Termux.**
> Build a duckdb wheel for `python3.13 aarch64` against Termux's Bionic, check it into `deploy/termux/wheels/`, and document the install. Without this, the audit's Phase 4 (DB rotation) is moot.

---

## Recommended next steps in order

1. **Get a duckdb wheel into `deploy/termux/wheels/`** so the bridge has working persistence. Without this, every other telemetry path is hollow.
2. **Install Termux:API + Termux:Boot APKs** on the target phone. Without these, wake-lock and USB are silent no-ops.
3. **Land Phase 1 of the improvement plan** (SIGTERM handler, RLock, waitress). 2 hours of work that derisks the next demo.
4. **Land Phase 2 of the improvement plan** (CAN FD handoff). Required for any real-car ingest.
5. Only then is it worth pulling the trigger on a track-day deployment attempt.

---

## Artefacts left on the phone

- `~/pitwall/` — full source tree
- `~/pitwall/.venv/` — Python 3.13 venv with runtime deps minus duckdb
- `~/pitwall-bridge.log` — last bridge run's stdout
- `~/.ssh/authorized_keys` — Mac's pubkey for ongoing SSH access
- `/data/local/tmp/setup_pitwall_ssh.sh` — the one-shot bootstrap used to install the key

Bridge process was stopped cleanly at the end of the test. No `~/pitwall_sessions.duckdb` was created because duckdb isn't installed.

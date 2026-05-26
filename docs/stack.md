# Tech stack

Ground truth: `pyproject.toml` (Python) and `src/pwa/package.json` (PWA).
Versions below are pinned by the lockfiles (`uv.lock`, `package-lock.json`).

## Python — bridge

Python 3.12+ required (`requires-python = ">=3.12"`).

### Runtime (always installed)

| Package      | Version  | Purpose                                                  |
| ------------ | -------- | -------------------------------------------------------- |
| `flask`      | `>=3.0`  | HTTP server                                              |
| `flask-cors` | `>=4.0`  | CORS for the PWA dev origin                              |
| `waitress`   | `>=3.0`  | production WSGI server                                   |
| `duckdb`     | `>=1.0`  | x86 storage backend (skipped on aarch64 Termux)          |
| `numpy`      | `>=1.26` | math; on phone installed via Termux `pkg`                |
| `pyyaml`     | `>=6.0`  | parses `data/cars/*.yaml`                                |

`pyarrow` is **not** in `pyproject.toml` — it's installed via Termux
`pkg install python-pyarrow` on the phone (Android wheel tag) and via
`pip install pyarrow` (laptop) when streaming parquet from SQLite. The
parquet branch in `bp_session.py` imports it lazily.

### Optional extras

| Extra      | Packages                                  | When                                  |
| ---------- | ----------------------------------------- | ------------------------------------- |
| `can`      | `python-can>=4.3`, `cantools>=39.0`       | live CAN ingest                       |
| `ops`      | `psutil>=5.9`                             | RSS-monitor thread                    |
| `adk`      | `google-adk>=0.1`                         | paddock Q&A — not installable on phone |
| `dev`      | `pytest>=8.0`, `pytest-cov>=5.0`          | tests                                 |
| `all`      | all of the above                          | laptop dev                            |

```bash
pip install -e .[can,ops,dev]      # laptop
pip install -e .[can,ops,adk,dev]  # laptop with ADK
```

LocalLLM (the on-phone LLM server) is an **external** Apache-2.0 Android
APK, not a Python package. Pitwall reaches it via `POST /v1/chat/completions`
over `http://localhost:8080`.

## PWA — Vue 3

`src/pwa/package.json`. Bundler is Vite 8.

### Dependencies

| Package                  | Version          | Purpose                                          |
| ------------------------ | ---------------- | ------------------------------------------------ |
| `vue`                    | `^3.5.32`        | reactivity + components                          |
| `vue-router`             | `^5.0.6`         | routing                                          |
| `pinia`                  | `^3.0.4`         | state stores                                     |
| `@duckdb/duckdb-wasm`    | `^1.33.1-dev45`  | client-side parquet SQL (Analysis Hall)          |
| `chart.js`               | `^4.4.0`         | telemetry charts                                 |
| `chartjs-plugin-zoom`    | `^2.0.1`         | pan/zoom on lap traces                           |
| `leaflet`                | `^1.9.4`         | track map (Analysis Hall, Track Atlas)           |
| `hammerjs`               | `^2.0.8`         | touch gestures (used by chartjs-plugin-zoom)     |
| `howler`                 | `^2.2.4`         | audio playback (coach voice clips)               |
| `idb-keyval`             | `^6.2.2`         | small KV in IndexedDB (PWA caches, settings)     |

### Dev dependencies

| Package                          | Version          | Purpose                          |
| -------------------------------- | ---------------- | -------------------------------- |
| `vite`                           | `^8.0.10`        | bundler                          |
| `@vitejs/plugin-vue`             | `^6.0.6`         | Vue SFC support                  |
| `vite-plugin-pwa`                | `^1.2.0`         | manifest + service worker        |
| `typescript`                     | `~6.0.2`         | TS compiler                      |
| `vue-tsc`                        | `^3.2.7`         | Vue type-check                   |
| `@vue/tsconfig`                  | `^0.9.1`         | tsconfig preset                  |
| `tailwindcss`                    | `^4.2.4`         | utility-first CSS                |
| `@tailwindcss/vite`              | `^4.2.4`         | Tailwind v4 Vite plugin          |
| `eslint`                         | `^10.3.0`        | linter                           |
| `eslint-plugin-vue`              | `^10.9.0`        | Vue lint rules                   |
| `typescript-eslint`              | `^8.59.1`        | TS lint rules                    |
| `@vue/eslint-config-typescript`  | `^14.7.0`        | shared ESLint config             |
| `prettier`                       | `^3.8.3`         | formatter                        |
| `vitest`                         | `^4.1.5`         | unit tests                       |
| `@vue/test-utils`                | `^2.4.10`        | Vue test harness                 |
| `happy-dom`                      | `^20.9.0`        | DOM for vitest                   |
| `@playwright/test`               | `^1.60.0`        | e2e tests                        |
| `@types/howler`                  | `^2.2.12`        | types                            |
| `@types/leaflet`                 | `^1.9.0`         | types                            |
| `@types/node`                    | `^24.12.2`       | types                            |

### Scripts

```bash
npm run dev            # vite dev server :5173, proxies /api → :8765
npm run build          # vite build → dist/
npm run build:check    # vue-tsc -b && vite build
npm run preview        # serve dist/
npm run typecheck      # vue-tsc --noEmit
npm run lint           # eslint
npm run test           # vitest run
npm run e2e            # playwright (chromium)
```

## On-phone packages (Termux)

Installed by `deploy/phone/10-termux-packages.sh` via `pkg install`
(Termux's package manager — these are aarch64 builds outside the venv,
exposed via a `termux_system.pth` shim):

- `python` (3.12 series)
- `python-pyarrow`
- `python-numpy`
- `git`, `rsync`, `curl`, `nodejs` (for `npm run build` on phone if needed)

The phone venv (`~/pitwall/.venv`) holds `flask`, `flask-cors`,
`waitress`, `pyyaml`, `python-can`, `cantools`, `psutil` — installed
from PyPI via `pip` in `30-python-deps.sh`. `duckdb` is intentionally
not installed (no aarch64 wheel); `google-adk` is intentionally not
installed (manylinux wheels don't match Termux's android tag).

## Hardware-side software

- **LocalLLM** — Apache-2.0 Android APK,
  [github.com/mlnomadpy/localllm](https://github.com/mlnomadpy/localllm).
  Hosts LiteRT-LM in a native Android process, exposes
  `http://127.0.0.1:8080/v1/chat/completions` with SSE streaming.
- **KernelSU** — root manager on the Pixel 10.
- **Termux** — terminal + package ecosystem.

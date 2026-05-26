# 07 — Stores, Composables & Libraries

## Pinia Stores

### saveStore.ts
- 🟡 **`hydrate()` silently returns `null` for missing slots** — No validation on loaded data. If IndexedDB has corrupted data, it's treated as valid.
- 🟡 **No auto-save** — `save()` must be called manually. Easy to forget after mutations.
- 🔵 **No migration system** — `schemaVersion: 1` exists in the type but no migration logic for when schema changes.
- 🔵 **`JSON.parse(JSON.stringify(slot))`** — Standard deep clone but loses `Date` objects. Consider `structuredClone()`.

### sessionStore.ts
- ⚪ Minimal and clean. Good start.
- 🔵 **No session persistence** — If app crashes mid-session, all data is lost.

### telemetryStore.ts
- ⚪ Good SSE reconnection logic with exponential backoff.
- 🟡 **Retry counter resets on ANY message** — A single heartbeat message resets `_retryCount`. If the server sends heartbeats but no real data, the client never gives up.
- 🔵 **No data buffering** — Each frame overwrites the previous. For replay/analysis, a ring buffer of recent frames would be valuable.

### coachStore.ts
- ⚪ Clean coach data definitions.

### spriteStore.ts
- 🟡 **`innerHTML +=`** fallback for keyframe injection — Comment says "for test runners" but this re-parses the entire stylesheet on each call. The `insertRule()` primary path is correct.
- 🟡 **`_injectedKeyframes` set grows forever** — No cleanup when components unmount. Over long sessions, hundreds of keyframes accumulate.
- 🔵 **Master sheet assumption** — All coaches are assumed to be 10×10 grid spritesheets. No validation that the PNG actually matches.

### audioStore.ts
- 🟡 **Howl instances never cleaned up** — `sfx`, `music`, `voice` maps grow forever. Old sounds stay in memory.
- 🟡 **`playVoice` stops ALL other voices** — Can't have overlapping voice cues (e.g., ambient + directed coaching).
- 🔵 **Volume settings from SaveSettings not applied** — `masterVolume`, `musicVolume`, etc. exist in the type but are never read by the store.

### cueStore.ts
- ⚪ Clean SSE-based cue system.
- 🟡 **Queue grows forever** — `this.queue.push(cue)` but nothing ever consumes/removes from the queue.

### bridgeStore.ts
- ⚪ Good polling implementation.

### notificationStore.ts
- ⚪ Clean notification management.

### pauseStore.ts
- ⚪ Simple toggle. Works.

### transitionStore.ts
- 🟡 **`play()` returns a Promise** that resolves after animation. If the animation CSS is missing or the element doesn't exist, the promise could hang forever. Add a timeout fallback.

### duckdbStore.ts
- 🟡 **`ensureSession` writes to OPFS** on every call — No check if the file already exists in OPFS. Re-downloads and re-writes on every page visit.
- 🟡 **`CREATE OR REPLACE VIEW`** — This replaces the view even if the same session is already loaded. Wasteful SQL round-trip.
- 🔵 **No OPFS cleanup** — Old session parquet files accumulate forever in OPFS storage.

---

## Composables

### useKeyboard.ts
- 🟡 **No priority/exclusivity system** — Multiple pages can register handlers simultaneously. When PauseMenu is open, the underlying page's handler still fires.
- 🔵 **No key mapping abstraction** — Hardcoded `e.key === 'ArrowDown'` everywhere. A central key-action mapping would allow rebinding.

### useReconnectingSSE.ts
- ⚪ Clean composable. Good pattern with auto-cleanup via `onUnmounted`.

### useSequence.ts
- 🟡 **`clearTimeout` and `clearInterval` mixed** — `sequenceTimeouts` stores both timeout and interval IDs. `clearTimeout` works on intervals in most browsers but it's not spec-guaranteed.
- ⚪ Otherwise clean animation sequencing tool.

### useTypewriter.ts
- ⚪ Clean. Good `complete()` method for skip support.

---

## Types

### save.ts
- ⚪ Comprehensive type definitions. Good use of branded types (`CoachId`, `TrackId`).
- 🔵 **No runtime validation** — Types are compile-time only. Bad IndexedDB data won't be caught.
- 🔵 **`avatarSlot: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8`** — Magic numbers. Should reference avatar IDs.

---

## Config

### api.ts
- ⚪ Simple `API_BASE` export. Clean.

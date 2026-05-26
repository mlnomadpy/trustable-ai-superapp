# Dataset Overview

**183 VBO files. 535,366 frames. 14.9 hours. 8 tracks. July–December 2025.**

---

## Summary

| Metric | Value |
|--------|-------|
| Total files | 183 |
| Total frames | 535,366 |
| Total duration | 14.9 hours (892 minutes) |
| Hot lap sessions | 52 (470,087 frames = 13.1 hours) |
| Transit / short sessions | 130 (not usable for coaching) |
| Distinct tracks | 8 (3 primary) |
| Max speed | 198 km/h (123 mph) |
| Max brake pressure | 104 bar |
| Max lateral G | 1.84G |
| Max combined G | 2.29G |

---

## Tracks

Sessions clustered by GPS median coordinates. 3 primary tracks = 95% of usable data.

| Track | GPS Center | Sessions | Hot Laps | Frames | Duration | Top Speed | Notes |
|-------|-----------|----------|----------|--------|----------|-----------|-------|
| **Track 1** (Sonoma) | 23.50°N, 73.79°W | 98 | 22 | 244,324 | 407 min | 190 km/h | Primary track. Sprint field test venue. 55m elevation delta. |
| **Track 2** | 24.20°N, 73.67°W | 37 | 17 | 134,858 | 225 min | 198 km/h | Fastest top speeds. VBOX0318 = heaviest braking (104 bar). |
| **Track 8** | 21.49°N, 72.21°W | 28 | 11 | 107,823 | 180 min | 190 km/h | Third validation track. VBOX0266 = longest session (128 min). |
| Track 3 | 22.59°N, 73.09°W | 13 | 2 | 23,113 | 39 min | 188 km/h | Limited hot lap data. |
| Track 4–7 | Various | 6 | 0 | 25,248 | 42 min | 133 km/h | Transit, warmup, street. Not for coaching. |

---

## Session Types

Auto-classified by driving intensity:

| Type | Criteria | Count | Frames | Duration | Use |
|------|----------|-------|--------|----------|-----|
| **hot_laps** | max gLat > 0.8G, speed > 140 km/h, frames > 500 | 52 | 470,087 | 13.1h | **ML training data** |
| warmup | max gLat 0.5–0.8G | 2 | 4,005 | 7 min | Warm-up detection training |
| transit | max gLat < 0.5G, speed < 140 km/h | 127 | 60,864 | 101 min | Negative examples — no coaching should fire |
| short | < 500 frames | 1 | 410 | 1 min | Discard |

---

## Top 10 Hot Lap Sessions

| File | Track | Frames | Duration | Max Speed | Max Brake | Max gLat | Notes |
|------|-------|--------|----------|-----------|-----------|----------|-------|
| VBOX0266 | Track 8 | 22,029 | 128 min | 182 km/h | 73 bar | 1.28G | Longest — multi-stint with pit stops |
| VBOX0318 | Track 2 | 17,827 | 50 min | **198 km/h** | **104 bar** | **1.84G** | **Fastest + hardest in entire dataset** |
| VBOX0229 | Track 1 | 14,672 | 41 min | 190 km/h | 91 bar | 1.66G | Sonoma — aggressive |
| VBOX0141 | Track 2 | 13,761 | 38 min | 194 km/h | 92 bar | 1.46G | Consistent pace |
| VBOX0290 | Track 8 | 12,856 | 36 min | 190 km/h | 84 bar | 1.62G | Good data quality |
| VBOX0208 | Track 1 | 12,163 | 34 min | 188 km/h | 100 bar | 1.79G | Sonoma — heavy braking |
| VBOX0226 | Track 1 | 12,049 | 33 min | 187 km/h | 75 bar | 1.67G | Sonoma — moderate |
| VBOX0212 | Track 1 | 12,002 | 100 min | 185 km/h | 71 bar | 1.66G | Long with breaks |
| VBOX0253 | Track 1 | 11,737 | 32 min | 187 km/h | 86 bar | 1.81G | High lateral G |
| VBOX0139 | Track 2 | 11,627 | 33 min | 193 km/h | 81 bar | 1.59G | Fast session |

---

## Recording Timeline

Data spans July 31, 2025 through December 15, 2025 across multiple track day events:

| Date Range | Files | Track | Notes |
|------------|-------|-------|-------|
| Jul 31 – Aug 1 | VBOX0133–0144 | Track 2 | First track day event |
| Aug 28 | VBOX0145–0165 | Track 3, 4 | Second event, includes transit |
| Sep 13–14 | VBOX0166–0217 | Track 1 (Sonoma) | Major Sonoma event — most Track 1 data |
| Oct 12–18 | VBOX0218–0242 | Track 1, 2 | Two events, both primary tracks |
| Nov 9–23 | VBOX0243–0293 | Track 1, 8 | Late season, Track 8 appears |
| Dec 13–15 | VBOX0294–0318 | Track 2, 8 | Final sessions of 2025 |

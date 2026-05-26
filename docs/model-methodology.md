# Model Methodology & Results

How we built the sequence predictor, what we tried, what worked, and why.

> **Historical record.** The training scripts referenced here (`lstm_predictor.py`, `lstm_predictor_v3.py`, `sequence_predictor.py`, `sonic_model_v2.py`) were removed as dead code in PR #30 once the three-tier coach architecture (ADR-017) committed to canonical phrases on the hot path. The model methodology and results below remain accurate for the era; the trained `.pt` artifacts are still on disk for future revival, but the training pipeline itself is no longer wired in. Real-time cueing now goes through `features/coaching/sonic_model.py` (rule-based) and `features/coaching/rule_coach.py`.

---

## Problem Statement

Given the last 3 seconds of driving telemetry (speed, G-forces, brake, throttle, steering, RPM), predict what will happen in the next 2 seconds. The gap between prediction and reality is the coaching signal — fired as audio tones to the driver in real time.

## Dataset

### Source

183 VBO files from a Racelogic VBVDHD2-V5 + OBDLink MX recording at 10Hz. July–December 2025. 535,366 total frames (14.9 hours). 52 hot lap sessions across 3 primary tracks.

### Held-Out Split (Not Random)

The split is by **session and by track** to test real-world generalization:

| Split | Data | Frames | Purpose |
|-------|------|--------|---------|
| **Train** | Sonoma (80% of sessions) + Track 2 | 292,944 | Learn patterns from 2 tracks |
| **Val** | Sonoma (20% of sessions) | 50,737 | Same track, different sessions — session-level generalization |
| **Test** | Track 8 (entirely held out) | 92,972 | **Different track** — track-level generalization |

This is a harder split than random. The test set is a completely unseen track with different corner geometry, elevation profile, and speed characteristics. Any model that performs well on test genuinely generalizes.

### Aggregate Signal Statistics (52 Hot Lap Sessions)

| Signal | Mean | P95 | Max | Coaching Relevance |
|--------|------|-----|-----|--------------------|
| Speed | 115 km/h | 170 km/h | 199 km/h | Primary outcome metric |
| Lateral G | 0.53G | 1.21G | 1.95G | Cornering intensity |
| Longitudinal G | -0.26G | -0.92G (braking) | +0.08G | Braking intensity |
| Brake pressure | 3.5 bar | 28.4 bar | 107 bar | Trail brake detection |
| Combined G | 0.63G | 1.20G | 2.86G | Friction circle usage |

### Driving Phase Distribution (456K frames)

| Phase | % of Time | Coaching Implication |
|-------|:-:|---|
| Cornering (powered) | 43.7% | Largest phase — corner speed and exit speed are primary targets |
| Straight | 14.5% | No coaching needed (full throttle) |
| Transition | 14.4% | Smoothness coaching |
| Cornering (coast) | 10.1% | Should be on throttle — coaching opportunity |
| Braking | 8.8% | Brake point and pressure coaching |
| **Coasting (wasted)** | **6.3%** | **#1 coaching target — ~6s per lap doing nothing** |
| Trail braking | 2.2% | Rare but highest-value technique |

### Track Profiles (Auto-Generated from GPS)

| Track | Length | Corners | Braking Corners | Elevation Delta |
|-------|--------|---------|----------------|----------------|
| Sonoma | 4,258m | 11 | 5 (Turn 3, 6, 9, 10, 11) | 48m |
| Track 2 | 3,974m | 9 | 9 (all require braking) | 30m |
| Track 8 | 4,846m | 11 | 10 (only Turn 7 is flat) | 4m (flat) |

Sonoma has the most elevation change (16% max uphill, 10% downhill) — elevation-aware coaching is critical there. Track 8 is flat but has more braking corners. Track 2 has no lift-only corners — every corner requires braking.

### Corner Passes

Models are trained on corner approach-to-exit sequences, not raw frames. Each "corner pass" starts 5 seconds before corner entry and ends 1 second after exit.

| Split | Corner Passes | Training Sequences |
|-------|--------------|-------------------|
| Train | 2,656 | 140,672 |
| Val | 497 | 25,583 |
| Test | 828 | 44,141 |

### Quality Weighting

Instead of training only on the best 20% of passes (v1/v2), v3 trains on **all passes** with quality weights. Each pass is scored 0.1–1.0 based on its corner time relative to the fastest pass at that corner. The loss function multiplies by this weight — best passes contribute 10x more than worst passes, but the model still sees the full spectrum.

---

## Features

### Per-Frame Features (22 dimensions)

**Raw signals (8):**

| # | Feature | Normalization | Source |
|---|---------|--------------|--------|
| 0 | speed | / 60.0 (→ ~0-1) | GPS velocity |
| 1 | g_lat | / 2.0 (→ ~-1 to 1) | Racelogic IMU |
| 2 | g_long | / 2.0 | Racelogic IMU |
| 3 | brake_pressure | / 100.0 (→ 0-1) | OBDLink CAN |
| 4 | throttle | / 100.0 (→ 0-1) | OBDLink CAN |
| 5 | steering | / 400.0, clipped ±1 | OBDLink CAN |
| 6 | combo_g | / 2.5 (→ 0-1) | Computed: sqrt(gLat² + gLong²) |
| 7 | rpm | / 9000.0 (→ 0-1) | OBDLink CAN |

**Derivative features (5):**

| # | Feature | Computation | Why |
|---|---------|------------|-----|
| 8 | heading_rate | d(heading)/dt / 50 | Yaw rate — how fast the car is turning. Critical for corner detection. |
| 9 | speed_dot | d(speed)/dt / 15 | Acceleration/deceleration rate. Distinguishes hard braking from trail braking. |
| 10 | brake_dot | d(brake)/dt / 200 | Brake application rate. Smooth squeeze vs stab. |
| 11 | throttle_dot | d(throttle)/dt / 300 | Throttle ramp rate. Smooth vs aggressive application. |
| 12 | steer_dot | d(steering)/dt / 500 | Steering rate. High = corrections/instability. Low = smooth. |

**Composite indicators (3):**

| # | Feature | Formula | Why |
|---|---------|---------|-----|
| 13 | friction_pct | combo_g / 2.29 | How much of the grip envelope is being used (0-1+). |
| 14 | trail_indicator | (brake/50) × (gLat/1.5), when brake > 3 and gLat > 0.3 | Continuous trail brake intensity. Zero when not trail braking. |
| 15 | coast_indicator | 1 - max(throttle/10, brake/2), when throttle < 10 and brake < 2 | Detects "wasted" time — neither braking nor accelerating. |

**Cross-signal features (6) — new in v3:**

| # | Feature | Formula | Why |
|---|---------|---------|-----|
| 16 | brake × gLat | brake_norm × abs(gLat_norm) | Trail brake intensity as a single number. |
| 17 | throttle × gLat | throttle_norm × abs(gLat_norm) | Powered cornering intensity. High = committed. |
| 18 | speed × heading_rate | speed_norm × abs(heading_rate) | Cornering speed — how fast through the turn. |
| 19 | brake × speed | brake_norm × speed_norm | Braking energy proxy. High speed + high brake = heavy braking event. |
| 20 | throttle × speed | throttle_norm × speed_norm | Acceleration power. High speed + high throttle = on a straight. |
| 21 | gLat × gLong | abs(gLat) × abs(gLong) | Friction circle quadrant — combined loading (trail brake or powered exit). |

### Track Context (8 dimensions)

| # | Feature | Description |
|---|---------|-------------|
| 0 | distance_to_corner | Normalized by track length. How far to the next corner entry. |
| 1 | corner_severity | 0-1 (mapped from 1-6 severity scale). |
| 2 | corner_direction | -1 (left), 0 (none), +1 (right). |
| 3 | distance_in_corner | 0 (entry) to 1 (exit). -1 if not in a corner. |
| 4 | past_apex | Binary: 1 if past the apex, 0 otherwise. |
| 5 | elevation | Normalized altitude at current track position. |
| 6 | in_brake_zone | 0-1: how deep into the expected brake zone (from track builder data). |
| 7 | track_position | 0-1: position around the lap. |

### Multi-Scale Input (new in v3)

Instead of one flat history window, the model receives three timescales:

| Scale | Frames | Resolution | Captures |
|-------|--------|-----------|----------|
| **Fine** | 10 frames (1 second) | Full 10Hz | Immediate dynamics: current brake/throttle/steering inputs |
| **Medium** | 10 frames (2 seconds) | 5Hz (downsampled 2x) | Corner approach pattern: braking onset, speed reduction |
| **Coarse** | 5 stat vectors (5 seconds) | Rolling statistics | Session context: avg speed, coast fraction, braking fraction |

### Corner Embedding (new in v3)

Each corner gets a **learned 12-dimensional embedding vector**. The model learns that Turn 1 (fast, gentle) needs a different speed/brake profile than Turn 10 (heavy braking, tight). This replaced the scalar "severity" feature which couldn't distinguish corners of the same severity.

### Prediction Targets (3 dimensions × 20 timesteps)

| Target | Normalization | Why This Target |
|--------|--------------|----------------|
| speed | / 60.0 (m/s → normalized) | The primary outcome — speed at each future point determines lap time |
| brake_pressure | / 100.0 (bar → normalized) | When and how hard to brake — the key coaching signal |
| throttle_relative | (throttle/100) / max(speed_norm, 0.1), then /3 | Throttle relative to speed — removes speed-dependence, models the driver's technique not the car's physics |

---

## Model Architecture Evolution

### v1: MLP Baseline

```
Input: flatten(30 frames × 8 features) + 5 context = 245 → MLP(128, 64, 64) → 60 outputs
```

**Problem:** Flattening destroys temporal structure. The model can't see that "brake going down while gLat going up" over 1 second IS trail braking. It only sees 240 independent numbers.

**Result:** 15.7 km/h speed MAE on val, 21.1 km/h on test. Speed bias of -51 km/h (predictions too slow) because the model averages across all corner types.

### v2: Bidirectional LSTM with Residual Connection

```
Input: (30, 16) → BiLSTM(96 hidden, 2 layers) + Attention → concat with context(32) → Decoder → 60 outputs
Key change: Residual — predict DELTA from last frame, not absolute values
```

**Residual connection:** Instead of predicting "speed will be 72 km/h", predict "speed will change by -3 km/h from current". This anchors predictions to the current state and eliminates the speed bias.

**Result:** 6.4 km/h speed MAE on val (-59%), 5.8 km/h on test (-72%). Bias reduced from -51 to -1.5 km/h. But still poor on throttle (20% MAE) and doesn't distinguish between corners.

### v3: Multi-Scale BiLSTM with All Improvements

```
Fine:   (10, 22) → BiLSTM(64, 2 layers) + Attention → 128-dim
Medium: (10, 22) → BiLSTM(48, 1 layer) → mean pool → 96-dim
Coarse: (5 × 8) → flatten → Linear → 32-dim
Context: (8) → Linear(48) → 32-dim
Corner: embedding(12) → 12-dim
                                        ↓
Concatenate: 128 + 96 + 32 + 32 + 12 = 300-dim
                                        ↓
Decoder: Linear(192) → ReLU → Linear(128) → ReLU → Linear(60)
                                        ↓
Residual: last_frame_targets + cumsum(deltas) → (20, 3)
```

**All improvements applied:**

1. Corner embedding (12-dim per corner ID)
2. Cross-signal features (6 new: brake×gLat, throttle×gLat, etc.)
3. Multi-scale input (fine 1s + medium 2s + coarse 5s)
4. Quality-weighted training on ALL passes (140K sequences vs 7.5K)
5. Relative throttle target (throttle/speed ratio)
6. Data augmentation (mirror left/right corners, noise injection)
7. Huber loss (robust to outliers)
8. Near-horizon weighting (0.5s predictions weighted 3x more than 2.0s)

**Parameters:** 272,073 (1.1 MB saved model)

---

## Training Details

| Parameter | Value |
|-----------|-------|
| Optimizer | AdamW (lr=0.0008, weight_decay=1e-4) |
| Scheduler | Cosine annealing over 100 epochs |
| Batch size | 128 |
| Loss | Smooth L1 (Huber), weighted by target importance and horizon |
| Target weights | speed=2.0, brake=1.5, throttle=1.0 |
| Horizon weights | Linear 1.5 (near) → 0.5 (far) |
| Gradient clipping | Max norm 1.0 |
| Early stopping | Patience 20 epochs on val loss |
| Training time | ~45 seconds on Apple MPS (M-series GPU) |
| Stopped at | Epoch 60 (early stopping) |
| Device | Apple MPS (Metal Performance Shaders) |

---

## Results

### Speed Prediction MAE (km/h) — The Core Metric

| Model | Val 0.5s | Val 1.0s | Val 2.0s | Test 0.5s | Test 1.0s | Test 2.0s |
|-------|---------|---------|---------|----------|----------|----------|
| MLP v1 | 13.7 | 15.7 | 19.7 | 20.2 | 21.1 | 25.7 |
| LSTM v2 (residual) | 3.5 | 6.4 | 12.7 | 3.3 | 5.8 | 11.7 |
| **LSTM v3 (all improvements)** | **1.6** | **3.0** | **5.9** | **1.6** | **3.3** | **7.5** |

### Brake Prediction MAE (bar)

| Model | Val 0.5s | Val 1.0s | Val 2.0s | Test 0.5s | Test 1.0s | Test 2.0s |
|-------|---------|---------|---------|----------|----------|----------|
| MLP v1 | 4.6 | 5.9 | 7.5 | 4.7 | 5.0 | 8.2 |
| LSTM v2 | 3.4 | 5.4 | 7.9 | 2.6 | 3.9 | 6.5 |
| **LSTM v3** | **1.9** | **2.6** | **3.2** | **1.8** | **2.7** | **3.9** |

### Improvement: v1 → v3 (1.0s horizon, unseen Track 8)

| Metric | MLP v1 | LSTM v3 | Factor |
|--------|--------|---------|--------|
| Speed MAE | 21.1 km/h | **3.3 km/h** | **6.4x** |
| Brake MAE | 5.0 bar | **2.7 bar** | **1.9x** |
| Speed bias | +15.3 km/h | **+0.9 km/h** | **17x** reduction |

### Speed Bias (Mean Prediction Error)

| Model | Train | Val | Test (unseen track) |
|-------|-------|-----|---------------------|
| MLP v1 | -51.0 km/h | -21.6 km/h | -19.1 km/h |
| LSTM v2 | -1.5 km/h | -0.4 km/h | -1.5 km/h |
| **LSTM v3** | **+0.6 km/h** | **+0.7 km/h** | **+0.9 km/h** |

Bias is near zero in v3 across all splits. The model is well-calibrated.

### Coaching Signal Distribution (Test set, 1.0s horizon)

| Finding | v1 | v3 | Interpretation |
|---------|----|----|---------------|
| >5 km/h too fast | 21.1% | **4.5%** | v3 only flags real overspeeds, not noise |
| >5 km/h too slow | 57.8% | **13.7%** | v1 flagged everything as slow (bias). v3 catches genuine pace loss. |

The v3 model is selective — it only flags 18.2% of sequences (4.5% + 13.7%) vs v1's 78.9%. Less noise, more signal.

---

## What Each Improvement Contributed

| Improvement | Speed MAE Impact (test 1.0s) | How We Know |
|-------------|------------------------------|-------------|
| **Residual connection** (v2) | 21.1 → 5.8 km/h | Ablation: v1 vs v2 |
| **Corner embedding** | ~-1.5 km/h | Corners of different types no longer averaged |
| **Cross-signal features** | ~-0.5 km/h on brake | Trail brake detection became explicit |
| **Multi-scale input** | ~-0.8 km/h at 2.0s | Coarse context helps long-horizon prediction |
| **Quality-weighted all passes** | Better generalization | 140K vs 7.5K sequences; model sees full spectrum |
| **Data augmentation** | Improved test vs val gap | Mirror augmentation helps with unseen corner directions |
| **Huber loss** | Robustness | Heavy braking outliers don't dominate gradient |
| **Near-horizon weighting** | 0.5s MAE -0.3 km/h | Model focuses on short-term accuracy for coaching |

---

## Failure Modes and Limitations

### Throttle Prediction Remains Weak

Throttle relative MAE is 0.25-0.33 (on a 0-3 scale). In absolute terms, throttle is predicted to ~20% accuracy. This is because:

- Two equally fast corner exits can have very different throttle traces (smooth ramp vs aggressive step)
- Throttle is the most "driver choice" signal — less physically constrained than speed or brake
- The relative throttle target helps but doesn't solve the fundamental ambiguity

### 2-Second Horizon Degrades

Speed MAE grows from 1.6 km/h at 0.5s to 7.5 km/h at 2.0s (4.7x). This is inherent — 2 seconds is a long time in racing. The model doesn't know if the driver will brake in 1.5 seconds or 2.0 seconds. Coaching should rely primarily on the 0.5-1.0s predictions.

### Track 2 Lap Detection Issues

The track builder's lap detection failed for Track 2 initially (produced 284m laps instead of ~4800m). Fixed by: using the fast-straight median position as S/F, adding cooldown to prevent double-triggers, and filtering outlier laps by median distance. Track 2 now produces correct 3,974m laps with 9 corners.

### Corner Embedding Doesn't Transfer

The corner embedding is track-specific (Turn 1 on Sonoma ≠ Turn 1 on Track 8). On the unseen test track, the embedding for "Turn 3" carries information from Sonoma's Turn 3, which may not match Track 8's Turn 3. The model still works because the other features (severity, speed, gLat) carry enough information, but the embedding is noisy on unseen tracks.

**Fix for production:** Either learn a universal corner representation from curvature/speed/elevation (not corner ID), or fine-tune the embedding on 2-3 laps of the new track.

---

## Model Files

```
models/
  lstm_v3.pt              1,075 KB   Best model (v3, all improvements)
  lstm_predictor.pt       1,543 KB   v2 (residual only)
  seq_predictor.pkl         —        v1 MLP (deprecated)
  phase_classifier.pkl    3,700 KB   XGBoost phase classifier (not used by sonic model v2)
  brake_predictor.pkl       436 B    Linear regression brake distance (superseded by LSTM)
  style_fingerprint.pkl      23 KB   K-Means 4-cluster driver style
```

---

## How It Drives Coaching

> Historical: at the time of writing, the sonic model v2 consumed LSTM v3 predictions. After ADR-017 (three-tier coach) and PR #30, the LSTM path was retired and the production sonic model is rule-driven (`features/coaching/sonic_model.py`).

Originally `sonic_model_v2` used the LSTM v3 predictions to generate continuous audio cues:

```
Every 0.5 seconds:
  LSTM predicts next 2 seconds of (speed, brake, throttle)

Every frame (100ms):
  Compare prediction[age] vs actual frame
  Compute delta: actual_speed - predicted_speed
  
  If delta > +5 km/h → rising pitch tone ("arriving hot")
  If delta < -5 km/h → low pitch pulse ("you have more pace")
  If predicted brake > 10 bar AND actual < 3 → brake pulse ("brake zone")
  If predicted speed drop > 20 km/h in 1s AND no brake → preemptive warning
```

The tone is continuous — its pitch IS the delta. The driver doesn't need to decode words. Rising pitch = faster than the model expects. Falling = slower. Silence = on the predicted line. The predictions come from the driver's own best laps, so the coaching is personal.

---

## Reproducibility

The training entry points (`lstm_predictor_v3.py`, `sequence_predictor.py`) were removed in PR #30. The recipe is preserved here for historical reference; reviving it requires restoring those files from git history.

```bash
# Historical — files no longer in the tree as of PR #30
cd pitwall-sprint/src/pitwall/features

# Build track definition from VBO files
python3 track_builder.py /path/to/vbo/*.vbo -n "Track Name" -o track.json

# Train the model (file deleted in PR #30 — recover from git history if reviving)
python3 lstm_predictor_v3.py train /path/to/data/ --track track.json --output models/

# Run the simulator (sonic model is now rule-based at features/coaching/sonic_model.py)
python3 simulator.py session.vbo --track track.json --speed 3
```

**Requirements at time of training:** Python 3.9+, PyTorch 2.x, scikit-learn 1.x, numpy

"""dead_reckoning.py — 1D Kalman filter for distance-along-track.

ADR-018 fix for the 10 Hz GPS dead-reckoning blocker raised in the Team 2
field-readiness review. At 130 mph (≈58 m/s) a single 100 ms GPS gap is
~5.8 m of unmeasured track — wider than most coaching markers ("the bridge",
"the bump"). This module fuses the always-available CAN bus signals
(speed_ms at 50–100 Hz, g_long at 50–200 Hz) with the slow but absolute
GPS-derived distance to produce a smooth `distance_m` at the CAN rate.

State vector ``x = [distance_m, speed_ms]``.

Process model between observations::

    d' = d + v·dt + ½·a·dt²
    v' = v + a·dt

with ``a = g_long · 9.81``.

The filter accepts three measurement streams::

    update_imu(t, g_long)        → drives the predict step
    update_speed(t, speed_ms)    → CAN bus speed
    update_distance(t, dist_m)   → GPS-derived cumulative distance

`distance_m` and `speed_ms` are read-back at any time. The implementation
uses NumPy directly — no external Kalman library — so the same module
runs on a Pixel under Termux.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


_G = 9.81


@dataclass
class DeadReckonerConfig:
    """Tunable noise parameters. Defaults are fitted to a Racelogic VBOX 3i
    + a USB-CAN adapter speed feed at Sonoma — the real on-track payload.
    Adjust per car/track once we have data to fit against."""
    sigma_a: float = 2.0          # process accel noise (m/s²)
    sigma_speed: float = 0.3      # CAN speed measurement noise (m/s)
    sigma_gps: float = 3.0        # GPS distance noise (m) — VBOX is ~1m,
                                  # consumer phones ~5m. 3 m is a safe Sonoma default.


class DeadReckoner:
    """Kalman filter on (distance_m, speed_ms).

    The filter is intentionally headless about *which* signal arrives next:
    callers feed predict (IMU) and either or both update streams (CAN +
    GPS) in any order, at any rate. Out-of-order timestamps are skipped
    rather than rewinding the state.
    """

    def __init__(self, config: Optional[DeadReckonerConfig] = None):
        self.cfg = config or DeadReckonerConfig()
        self.x = np.zeros(2)
        self.P = np.eye(2) * 1e3       # diffuse prior — first measurement dominates
        self.t: Optional[float] = None
        self.last_a = 0.0
        self.n_updates = 0

    # ── prediction ────────────────────────────────────────────────────────

    def update_imu(self, t: float, g_long: float) -> None:
        """Advance the filter to ``t`` using the measured longitudinal G as the
        control input. Call this on every IMU sample.

        ``g_long`` is in g (1 g = 9.81 m/s²). Negative values = braking.
        """
        a = g_long * _G
        self.last_a = a
        self._predict_to(t, a)

    def predict_to(self, t: float) -> None:
        """Advance to ``t`` using the last-seen accel (zero before any IMU
        sample). Useful when only CAN speed is available — the filter still
        propagates between speed updates."""
        self._predict_to(t, self.last_a)

    def _predict_to(self, t: float, a: float) -> None:
        if self.t is None:
            self.t = t
            return
        dt = t - self.t
        if dt <= 0:
            return                 # ignore out-of-order / duplicate timestamps
        F = np.array([[1.0, dt], [0.0, 1.0]])
        B = np.array([0.5 * dt * dt, dt])
        # Continuous-white-noise-acceleration process noise
        # (Bar-Shalom 2001, eq 6.3.1-4)
        sa2 = self.cfg.sigma_a ** 2
        Q = np.array([
            [0.25 * dt ** 4, 0.5 * dt ** 3],
            [0.5  * dt ** 3,        dt ** 2],
        ]) * sa2
        self.x = F @ self.x + B * a
        self.P = F @ self.P @ F.T + Q
        self.t = t

    # ── measurement updates ───────────────────────────────────────────────

    # Dimension-wise variance threshold above which we treat that state
    # element as "uninitialised" and adopt the next measurement directly
    # rather than running the Kalman update. Below this we trust the prior.
    _COLD_VAR = 100.0

    def update_speed(self, t: float, speed_ms: float) -> None:
        """Fuse a CAN speed measurement (m/s).

        While the speed axis is still in its diffuse prior (variance above
        `_COLD_VAR`), the value is adopted directly so a single cold-start
        reading appears verbatim downstream. Once the prior has tightened
        the standard Kalman update kicks in and produces smoothed output."""
        if self.t is None or self.P[1, 1] >= self._COLD_VAR:
            self.x[1] = speed_ms
            self.P[1, 1] = self.cfg.sigma_speed ** 2
            self.t = t
            self.n_updates += 1
            return
        self.predict_to(t)
        H = np.array([[0.0, 1.0]])
        R = self.cfg.sigma_speed ** 2
        self._kalman_update(H, R, speed_ms)

    def update_distance(self, t: float, distance_m: float) -> None:
        """Fuse a GPS-derived cumulative distance (m).

        Same cold-start adoption logic as `update_speed`: a fresh distance
        axis adopts the measurement verbatim, then smoothing kicks in."""
        if self.t is None or self.P[0, 0] >= self._COLD_VAR:
            self.x[0] = distance_m
            self.P[0, 0] = self.cfg.sigma_gps ** 2
            self.t = t
            self.n_updates += 1
            return
        self.predict_to(t)
        H = np.array([[1.0, 0.0]])
        R = self.cfg.sigma_gps ** 2
        self._kalman_update(H, R, distance_m)

    def _kalman_update(self, H: np.ndarray, R: float, z: float) -> None:
        # H is shape (1, 2); flatten to a 1-D vector once for cleaner ops.
        h = H.flatten()
        innovation = z - float(h @ self.x)
        S = float(h @ self.P @ h) + R
        K = (self.P @ h) / S                      # 2-vector Kalman gain
        self.x = self.x + K * innovation
        # Joseph form is unnecessary at 2-D; the symmetric form below stays
        # PD as long as R > 0, which we enforce in the config.
        I_KH = np.eye(2) - np.outer(K, h)
        self.P = I_KH @ self.P
        self.n_updates += 1

    # ── read-back ─────────────────────────────────────────────────────────

    @property
    def distance_m(self) -> float:
        return float(self.x[0])

    @property
    def speed_ms(self) -> float:
        return float(self.x[1])

    @property
    def covariance(self) -> np.ndarray:
        """Return a copy so callers can inspect uncertainty without mutating."""
        return self.P.copy()

    def reset(self) -> None:
        """Wipe state — used when a new lap session starts."""
        self.x = np.zeros(2)
        self.P = np.eye(2) * 1e3
        self.t = None
        self.last_a = 0.0
        self.n_updates = 0

    def seed(self, *, distance_m: float, speed_ms: float, t: float) -> None:
        """Set an initial high-confidence state. Useful when a session
        resumes mid-lap with a known marker (e.g. start/finish line GPS
        crossing)."""
        self.x = np.array([distance_m, speed_ms])
        self.P = np.diag([1.0, 0.5])         # tight prior — caller is asserting
        self.t = t

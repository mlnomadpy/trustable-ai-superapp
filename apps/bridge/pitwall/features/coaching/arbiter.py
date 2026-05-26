"""
CoachArbiter — lightweight priority + cooldown gate on coaching messages.
"""

from __future__ import annotations

from typing import Optional

from pitwall.features.coaching.engine_base import CoachingMessage


# ─── Arbiter (lightweight: cooldown + corner suppression) ─────────────────────


class CoachArbiter:
    """Per Pitwall ADR-002: P3 immediate; P2 only on straights; P1 queued.
    Cooldown 3 s between non-safety messages. Stale 5 s expiry.
    """

    def __init__(self, cooldown_s: float = 3.0, stale_s: float = 5.0):
        self.cooldown_s = cooldown_s
        self.stale_s = stale_s
        self._last_emit_t = 0.0
        self._queued: Optional[tuple[float, CoachingMessage]] = None

    def submit(
        self,
        msg: Optional[CoachingMessage],
        *,
        now: float,
        on_straight: bool,
    ) -> Optional[CoachingMessage]:
        # Drop stale queued message
        if self._queued and now - self._queued[0] > self.stale_s:
            self._queued = None

        if msg is None:
            # Maybe deliver a queued one if we're now on a straight
            if self._queued and on_straight \
                    and now - self._last_emit_t >= self.cooldown_s:
                _, m = self._queued
                self._queued = None
                self._last_emit_t = now
                return m
            return None

        # P3 always immediate
        if msg.priority >= 3:
            self._last_emit_t = now
            return msg

        # P2 needs a straight; otherwise hold
        if msg.priority == 2 and not on_straight:
            self._queued = (now, msg)
            return None

        # Cooldown
        if now - self._last_emit_t < self.cooldown_s:
            self._queued = (now, msg)
            return None

        self._last_emit_t = now
        return msg

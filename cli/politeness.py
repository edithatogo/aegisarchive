#!/usr/bin/env python3
"""
AegisArchive - Politeness engine (Python port of web/lib/politeness_engine.js)
Zero external dependencies (Python 3 standard library only).

Token bucket, decorrelated full-jitter back-off, EWMA latency with a median warm-up
baseline, circuit breaker (NOMINAL -> THROTTLED -> TRIPPED -> HALF_OPEN) and
RFC 9110 Retry-After handling (delta-seconds and HTTP-date, capped).

Licensed under the Apache License, Version 2.0.
"""

import math
import random
import threading
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse


class CircuitState:
    NOMINAL = "NOMINAL"
    THROTTLED = "THROTTLED"
    TRIPPED = "TRIPPED"
    HALF_OPEN = "HALF_OPEN"


def _host_of(url):
    try:
        return (urlparse(url).hostname or "").lower() or None
    except (TypeError, ValueError):
        return None


class PolitenessEngine:
    """Mirror of the browser engine. Times are seconds internally; the public API uses milliseconds."""

    def __init__(self, config=None, stop_event=None, clock=None, sleeper=None):
        config = config or {}
        self.min_delay_ms = config.get("min_delay_ms") or 1200
        self.max_delay_ms = config.get("max_delay_ms") or 3500
        self.jitter_distribution = config.get("jitter_distribution") or "gaussian"
        self.max_rpm = config.get("max_requests_per_minute") or 30
        self.burst_limit = config.get("burst_limit") or 5
        self.respect_retry_after = config.get("respect_retry_after", True) is not False
        self.adaptive_ewma = config.get("adaptive_ewma_backoff", True) is not False
        self.consecutive_error_tripwire = config.get("consecutive_error_tripwire") or 3
        self.cooldown_seconds = config.get("cooldown_seconds") or 60

        self.stop_event = stop_event or threading.Event()
        self._clock = clock or time.time      # returns seconds
        self._sleeper = sleeper               # optional: sleeper(seconds) -> bool (False = interrupted)

        # Token bucket
        self.tokens = float(self.burst_limit)
        self.last_token_refill = self._clock()
        self.token_fill_rate_per_ms = self.max_rpm / 60000.0

        # Latency EWMA + warm-up baseline
        self.ewma_alpha = 0.2
        self.ewma_latency_ms = None
        self.baseline_latency_ms = None
        self.warmup_size = 10
        self.warmup_samples = []
        self.baseline_drift_alpha = 0.02

        # Back-off and circuit breaker
        self.consecutive_errors = 0
        self.current_backoff_delay_ms = self.min_delay_ms
        self.circuit_state = CircuitState.NOMINAL
        self.circuit_trip_timestamp = None
        self.domain_cooldowns = {}  # host -> wake epoch (seconds)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def is_countable_failure(status):
        try:
            s = int(status)
        except (TypeError, ValueError):
            return False
        return s == 0 or s == 429 or 500 <= s <= 599

    def parse_retry_after(self, header_value):
        if not header_value:
            return None
        value = str(header_value).strip()
        if value.isdigit():
            return int(value) * 1000
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if dt is None:
            return None
        return max(1000, int((dt.timestamp() - self._clock()) * 1000))

    def _sleep(self, ms):
        """Interruptible sleep. Returns False when stop_event was set."""
        if ms <= 0:
            return not self.stop_event.is_set()
        if self._sleeper is not None:
            return bool(self._sleeper(ms / 1000.0))
        return not self.stop_event.wait(ms / 1000.0)

    def refill_tokens(self):
        now = self._clock()
        elapsed_ms = (now - self.last_token_refill) * 1000.0
        self.tokens = min(float(self.burst_limit), self.tokens + elapsed_ms * self.token_fill_rate_per_ms)
        self.last_token_refill = now

    def calculate_jitter(self, min_ms, max_ms):
        if self.jitter_distribution == "uniform":
            return int(min_ms + random.random() * (max_ms - min_ms))
        mean = (min_ms + max_ms) / 2.0
        std_dev = (max_ms - min_ms) / 6.0
        sample = int(round(random.gauss(mean, std_dev)))
        return max(min_ms, min(max_ms, sample))

    def calculate_decorrelated_backoff(self):
        base = self.min_delay_ms
        cap = max(30000, self.max_delay_ms * 10)
        upper = max(base, self.current_backoff_delay_ms * 3)
        self.current_backoff_delay_ms = min(cap, int(base + random.random() * (upper - base)))
        return self.current_backoff_delay_ms

    # -- recording -----------------------------------------------------------
    def record_success(self, url, latency_ms):
        self.consecutive_errors = 0
        self.current_backoff_delay_ms = self.min_delay_ms
        if self.ewma_latency_ms is None:
            self.ewma_latency_ms = latency_ms
        else:
            self.ewma_latency_ms = int(round(self.ewma_alpha * latency_ms + (1 - self.ewma_alpha) * self.ewma_latency_ms))
        if len(self.warmup_samples) < self.warmup_size:
            self.warmup_samples.append(latency_ms)
            if len(self.warmup_samples) == self.warmup_size:
                ordered = sorted(self.warmup_samples)
                self.baseline_latency_ms = ordered[len(ordered) // 2]
        else:
            self.baseline_latency_ms = int(round(
                (1 - self.baseline_drift_alpha) * self.baseline_latency_ms + self.baseline_drift_alpha * latency_ms
            ))
        if self.circuit_state in (CircuitState.HALF_OPEN, CircuitState.THROTTLED):
            self.circuit_state = CircuitState.NOMINAL

    def record_failure(self, url, status, retry_after_header=None):
        """Returns True when the failure counted toward the breaker (0/429/5xx), else False."""
        if not self.is_countable_failure(status):
            return False
        self.consecutive_errors += 1
        retry_ms = self.parse_retry_after(retry_after_header) if self.respect_retry_after else None
        if retry_ms:
            cap_ms = self.cooldown_seconds * 10 * 1000
            host = _host_of(url)
            if host:
                self.domain_cooldowns[host] = self._clock() + min(retry_ms, cap_ms) / 1000.0
        if self.consecutive_errors >= self.consecutive_error_tripwire:
            self.circuit_state = CircuitState.TRIPPED
            self.circuit_trip_timestamp = self._clock()
        else:
            self.circuit_state = CircuitState.THROTTLED
            self.calculate_decorrelated_backoff()
        return True

    # -- gate ----------------------------------------------------------------
    def acquire_permission(self, target_url):
        """Blocks until it is polite to send the next request. Returns {delay_ms, state, aborted}."""
        aborted = {"delay_ms": 0, "state": self.circuit_state, "aborted": True}
        if self.circuit_state == CircuitState.TRIPPED:
            remaining = self.cooldown_seconds - (self._clock() - self.circuit_trip_timestamp)
            if remaining > 0 and not self._sleep(remaining * 1000.0):
                return aborted
            self.circuit_state = CircuitState.HALF_OPEN
        host = _host_of(target_url)
        wake = self.domain_cooldowns.get(host)
        if wake and self._clock() < wake:
            if not self._sleep((wake - self._clock()) * 1000.0):
                return aborted
            self.domain_cooldowns.pop(host, None)
        self.refill_tokens()
        if self.tokens < 1.0:
            wait_ms = math.ceil((1.0 - self.tokens) / self.token_fill_rate_per_ms)
            if not self._sleep(wait_ms):
                return aborted
            self.refill_tokens()
        self.tokens -= 1.0
        delay = self.calculate_jitter(self.min_delay_ms, self.max_delay_ms)
        if self.adaptive_ewma and self.ewma_latency_ms and self.baseline_latency_ms:
            strain = self.ewma_latency_ms / max(50, self.baseline_latency_ms)
            if strain > 1.35:
                delay = int(round(delay * min(3.0, strain)))
                if self.circuit_state == CircuitState.NOMINAL:
                    self.circuit_state = CircuitState.THROTTLED
        if self.circuit_state == CircuitState.THROTTLED:
            delay = max(delay, self.current_backoff_delay_ms)
        if not self._sleep(delay):
            return aborted
        return {"delay_ms": delay, "state": self.circuit_state, "aborted": False}

    def get_telemetry(self):
        return {
            "circuit_state": self.circuit_state,
            "consecutive_errors": self.consecutive_errors,
            "ewma_latency_ms": self.ewma_latency_ms or 0,
            "baseline_latency_ms": self.baseline_latency_ms or 0,
            "available_tokens": round(self.tokens, 2),
            "max_rpm": self.max_rpm,
        }

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
import re
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
        self.next_permission_at = 0.0  # paced output slots (seconds)

    # -- helpers -------------------------------------------------------------
    def _state_config(self):
        return {key: getattr(self, attr) for key, attr in (
            ('min_delay_ms', 'min_delay_ms'), ('max_delay_ms', 'max_delay_ms'),
            ('jitter_distribution', 'jitter_distribution'), ('max_rpm', 'max_rpm'),
            ('burst_limit', 'burst_limit'), ('respect_retry_after', 'respect_retry_after'),
            ('adaptive_ewma', 'adaptive_ewma'), ('tripwire', 'consecutive_error_tripwire'),
            ('cooldown_seconds', 'cooldown_seconds'))}

    def export_state(self):
        """JSON pacing state only; epoch times are milliseconds, never credentials."""
        return dict(version=1, config=self._state_config(), saved_at_ms=self._clock() * 1000,
                    tokens=self.tokens, last_refill_ms=self.last_token_refill * 1000,
                    next_permission_ms=self.next_permission_at * 1000,
                    circuit_state=self.circuit_state,
                    circuit_until_ms=(None if self.circuit_trip_timestamp is None else
                                      (self.circuit_trip_timestamp + self.cooldown_seconds) * 1000),
                    domain_cooldowns={host: wake * 1000 for host, wake in self.domain_cooldowns.items()},
                    consecutive_errors=self.consecutive_errors,
                    backoff_ms=self.current_backoff_delay_ms,
                    ewma_ms=self.ewma_latency_ms, baseline_ms=self.baseline_latency_ms,
                    warmup_samples=list(self.warmup_samples))

    def restore_state(self, state):
        """Validate completely before mutation; merge outstanding waits conservatively."""
        def number(value, low=0, high=2**53 - 1, integer=False):
            if (type(value) not in (int, float) or not low <= value <= high
                    or not math.isfinite(value) or (integer and int(value) != value)):
                raise ValueError('Invalid pacing number')
            return value
        if (type(state) is not dict or set(state) != set(self.export_state())
                or type(state['version']) is not int or state['version'] != 1):
            raise ValueError('Invalid pacing state version or fields')
        config = state['config']
        expected = self._state_config()
        if (type(config) is not dict or set(config) != set(expected)
                or any(type(config[k]) is not type(v) or config[k] != v for k, v in expected.items())):
            raise ValueError('Incompatible pacing config')
        saved = number(state['saved_at_ms'])
        refill = number(state['last_refill_ms'], high=saved)
        next_at = number(state['next_permission_ms'])
        tokens = number(state['tokens'], high=self.burst_limit)
        errors = number(state['consecutive_errors'], integer=True)
        backoff = number(state['backoff_ms'], low=self.min_delay_ms,
                         high=max(30000, self.max_delay_ms * 10))
        circuit = state['circuit_state']
        if type(circuit) is not str or circuit not in ('NOMINAL', 'THROTTLED', 'TRIPPED', 'HALF_OPEN'):
            raise ValueError('Invalid circuit state')
        until = state['circuit_until_ms']
        if until is not None:
            number(until)
        if circuit == CircuitState.TRIPPED and until is None:
            raise ValueError('Missing circuit deadline')
        latency = [state['ewma_ms'], state['baseline_ms']]
        samples = state['warmup_samples']
        if type(samples) is not list or len(samples) > self.warmup_size:
            raise ValueError('Invalid warmup samples')
        for value in samples + [v for v in latency if v is not None]:
            number(value, high=86400000)
        if (len(samples) == self.warmup_size) != (latency[1] is not None):
            raise ValueError('Invalid warmup baseline')
        domains = state['domain_cooldowns']
        if type(domains) is not dict or len(domains) > 4096:
            raise ValueError('Invalid domain cooldowns')
        for host, wake in domains.items():
            if (type(host) is not str or len(host) > 253
                    or not re.fullmatch(r'[a-z0-9][a-z0-9.:-]*', host)):
                raise ValueError('Invalid cooldown host')
            number(wake)
        now = number(self._clock() * 1000)
        # Backwards jumps must not consume the remaining wait. Retain the original
        # absolute deadline too, so repeated restoration cannot shorten it.
        def deadline(value):
            return number(max(value, now + max(0, value - saved)) if now < saved else value)
        merged = dict(self.domain_cooldowns)
        for host, wake in domains.items():
            merged[host] = max(merged.get(host, 0), deadline(wake) / 1000)
        existing_until = (self.circuit_trip_timestamp + self.cooldown_seconds) * 1000 if self.circuit_trip_timestamp is not None else 0
        restored_until = max(existing_until, deadline(until) if until is not None else 0)
        restored_next = max(self.next_permission_at, deadline(next_at) / 1000)
        self.tokens = min(self.tokens, tokens)
        self.last_token_refill = min(now, refill) / 1000 if now >= saved else now / 1000
        self.next_permission_at = restored_next
        self.domain_cooldowns = merged
        rank = {'NOMINAL': 0, 'HALF_OPEN': 1, 'THROTTLED': 2, 'TRIPPED': 3}
        self.circuit_state = max((self.circuit_state, circuit), key=rank.get)
        self.circuit_trip_timestamp = (restored_until / 1000 - self.cooldown_seconds) if restored_until else None
        self.consecutive_errors = max(self.consecutive_errors, errors)
        self.current_backoff_delay_ms = max(self.current_backoff_delay_ms, backoff)
        self.ewma_latency_ms, self.baseline_latency_ms = latency
        self.warmup_samples = list(samples)
        return True

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
        if re.fullmatch(r'[0-9]+', value):
            return min(int(value[:18]) * 1000, 2**53 - 1)
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
        now = self._clock()
        self.next_permission_at = max(now, self.next_permission_at) + delay / 1000.0
        if not self._sleep((self.next_permission_at - now) * 1000.0):
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

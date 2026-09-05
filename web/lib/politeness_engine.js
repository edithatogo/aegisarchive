/**
 * AegisArchive - Server-Preserving Politeness & Anti-DDoS Flow Control Engine
 * 
 * Capabilities:
 * - Token-Bucket & Leaky-Bucket Rate Limiting with Host Isolation
 * - Decorrelated Full Jitter Exponential Back-Off
 * - Real-Time EWMA Latency Dynamic Adaptation
 * - Autonomous Circuit Breaker (Nominal -> Throttled -> Tripped -> Half-Open)
 * - RFC 9110 / RFC 7231 Compliant Retry-After Header Handling (Delta & Date)
 * 
 * Licensed under the Apache License, Version 2.0.
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.PolitenessEngine = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  const CircuitState = {
    NOMINAL: 'NOMINAL',       // Operating within standard parameters
    THROTTLED: 'THROTTLED',   // Latency or rate warnings; increased jitter delay
    TRIPPED: 'TRIPPED',       // Consecutive error ceiling reached; paused for cooldown
    HALF_OPEN: 'HALF_OPEN'    // Cooldown elapsed; issuing single probe request
  };

  class PolitenessEngine {
    constructor(config = {}) {
      this.minDelayMs = config.min_delay_ms || 1200;
      this.maxDelayMs = config.max_delay_ms || 3500;
      this.jitterDistribution = config.jitter_distribution || 'gaussian';
      this.maxRpm = config.max_requests_per_minute || 30;
      this.burstLimit = config.burst_limit || 5;
      this.respectRetryAfter = config.respect_retry_after !== false;
      this.adaptiveEwma = config.adaptive_ewma_backoff !== false;
      this.consecutiveErrorTripwire = config.consecutive_error_tripwire || 3;
      this.cooldownSeconds = config.cooldown_seconds || 60;

      // Token bucket state
      this.tokens = this.burstLimit;
      this.lastTokenRefill = Date.now();
      this.tokenFillRatePerMs = this.maxRpm / 60000;

      // Latency EWMA state (alpha = 0.2)
      this.ewmaAlpha = 0.2;
      this.ewmaLatencyMs = null;
      this.baselineLatencyMs = null;
      this.warmupSize = 10;            // samples used for the median baseline
      this.warmupSamples = [];
      this.baselineDriftAlpha = 0.02;  // slow drift after warm-up

      // Back-off and Circuit Breaker state
      this.consecutiveErrors = 0;
      this.currentBackoffDelayMs = this.minDelayMs;
      this.circuitState = CircuitState.NOMINAL;
      this.circuitTripTimestamp = null;
      this.domainCooldowns = new Map(); // domain -> wakeEpochMs
      this.abortController = (typeof AbortController !== 'undefined') ? new AbortController() : null;

      // Telemetry callback
      this.onStateChange = config.onStateChange || null;
    }

    /** Interruptible sleep; resolves true when the delay elapsed, false when aborted (D4). */
    sleep(ms) {
      const signal = this.abortController ? this.abortController.signal : null;
      return new Promise(resolve => {
        if (signal && signal.aborted) return resolve(false);
        const onAbort = () => { clearTimeout(timer); resolve(false); };
        const timer = setTimeout(() => {
          if (signal) signal.removeEventListener('abort', onAbort);
          resolve(true);
        }, ms);
        if (signal) signal.addEventListener('abort', onAbort, { once: true });
      });
    }

    abort() { if (this.abortController) this.abortController.abort(); }

    resetAbort() {
      if (typeof AbortController !== 'undefined') this.abortController = new AbortController();
    }

    /**
     * Parses RFC 9110 / RFC 7231 Retry-After header.
     * Supports both delta-seconds ("120") and HTTP-date ("Wed, 21 Oct 2026 07:28:00 GMT").
     */
    parseRetryAfter(headerValue) {
      if (!headerValue) return null;
      const trimmed = headerValue.trim();
      // Case 1: Delta-seconds
      const deltaSec = parseInt(trimmed, 10);
      if (!isNaN(deltaSec) && deltaSec >= 0) {
        return deltaSec * 1000;
      }
      // Case 2: HTTP-date
      const parsedDate = Date.parse(trimmed);
      if (!isNaN(parsedDate)) {
        const diffMs = parsedDate - Date.now();
        return Math.max(1000, diffMs);
      }
      return null;
    }

    /**
     * Refills token bucket based on elapsed time.
     */
    refillTokens() {
      const now = Date.now();
      const elapsed = now - this.lastTokenRefill;
      const newTokens = elapsed * this.tokenFillRatePerMs;
      this.tokens = Math.min(this.burstLimit, this.tokens + newTokens);
      this.lastTokenRefill = now;
    }

    /**
     * Calculates Gaussian or Uniform random jitter between min and max.
     */
    calculateJitter(min, max) {
      if (this.jitterDistribution === 'uniform') {
        return Math.floor(min + Math.random() * (max - min));
      }
      // Box-Muller transform for Gaussian distribution centered between min and max
      let u = 0, v = 0;
      while (u === 0) u = Math.random();
      while (v === 0) v = Math.random();
      const num = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
      const mean = (min + max) / 2;
      const stdDev = (max - min) / 6; // 99.7% of values fall within [min, max]
      const sample = Math.round(mean + num * stdDev);
      return Math.max(min, Math.min(max, sample));
    }

    /**
     * Decorrelated Full Jitter back-off calculation (decorrelated jitter scheme).
     * Prevents thundering-herd retry storms against recovering servers.
     */
    calculateDecorrelatedBackoff() {
      const base = this.minDelayMs;
      const max = Math.max(30000, this.maxDelayMs * 10);
      const nextDelay = Math.min(max, Math.floor(base + Math.random() * (this.currentBackoffDelayMs * 3 - base)));
      this.currentBackoffDelayMs = nextDelay;
      return nextDelay;
    }

    /**
     * Records a successful request and updates EWMA latency.
     */
    recordSuccess(url, latencyMs) {
      this.consecutiveErrors = 0;
      this.currentBackoffDelayMs = this.minDelayMs;

      // Update EWMA
      if (this.ewmaLatencyMs === null) {
        this.ewmaLatencyMs = latencyMs;
      } else {
        this.ewmaLatencyMs = Math.round(this.ewmaAlpha * latencyMs + (1 - this.ewmaAlpha) * this.ewmaLatencyMs);
      }

      // Baseline: median of the first warmupSize samples, then slow drift (D1)
      if (this.warmupSamples.length < this.warmupSize) {
        this.warmupSamples.push(latencyMs);
        if (this.warmupSamples.length === this.warmupSize) {
          const sorted = this.warmupSamples.slice().sort((a, b) => a - b);
          this.baselineLatencyMs = sorted[Math.floor(sorted.length / 2)];
        }
      } else {
        this.baselineLatencyMs = Math.round(
          (1 - this.baselineDriftAlpha) * this.baselineLatencyMs + this.baselineDriftAlpha * latencyMs
        );
      }

      // Check if circuit was half-open or throttled, and restore to nominal
      if (this.circuitState === CircuitState.HALF_OPEN || this.circuitState === CircuitState.THROTTLED) {
        this.circuitState = CircuitState.NOMINAL;
        this.notifyState();
      }
    }

    /**
     * Only network errors (0), 429 and 5xx indicate server strain (D2).
     */
    static isCountableFailure(status) {
      const s = Number(status);
      return s === 0 || s === 429 || (s >= 500 && s <= 599);
    }

    /**
     * Records a failed request (429, 5xx, or network timeout) and updates circuit state.
     */
    recordFailure(url, status, retryAfterHeader = null) {
      if (!PolitenessEngine.isCountableFailure(status)) {
        return false; // informational 4xx: ledger only, no circuit change
      }
      this.consecutiveErrors++;

      // Check for explicit Retry-After
      const retryMs = this.respectRetryAfter ? this.parseRetryAfter(retryAfterHeader) : null;
      if (retryMs) {
        const capMs = this.cooldownSeconds * 10 * 1000; // never honour absurd Retry-After (D4)
        try {
          const domain = new URL(url).hostname;
          this.domainCooldowns.set(domain, Date.now() + Math.min(retryMs, capMs));
        } catch (e) {}
      }

      if (this.consecutiveErrors >= this.consecutiveErrorTripwire) {
        this.circuitState = CircuitState.TRIPPED;
        this.circuitTripTimestamp = Date.now();
        this.notifyState();
      } else {
        this.circuitState = CircuitState.THROTTLED;
        this.calculateDecorrelatedBackoff();
        this.notifyState();
      }
      return true;
    }

    notifyState() {
      if (typeof this.onStateChange === 'function') {
        this.onStateChange(this.getTelemetry());
      }
    }

    /**
     * Pre-flight gate: Waits until it is polite and safe to execute the next request.
     */
    async acquirePermission(targetUrl) {
      // 1. Check Circuit Breaker
      if (this.circuitState === CircuitState.TRIPPED) {
        const elapsedSinceTrip = Date.now() - this.circuitTripTimestamp;
        const cooldownMs = this.cooldownSeconds * 1000;
        if (elapsedSinceTrip < cooldownMs) {
          const waitRemaining = cooldownMs - elapsedSinceTrip;
          if (!(await this.sleep(waitRemaining))) return { delayMs: 0, state: this.circuitState, aborted: true };
        }
        // Advance to Half-Open probe state
        this.circuitState = CircuitState.HALF_OPEN;
        this.notifyState();
      }

      // 2. Check Domain-Specific Retry-After Cooldown
      try {
        const domain = new URL(targetUrl).hostname;
        const wakeEpoch = this.domainCooldowns.get(domain);
        if (wakeEpoch && Date.now() < wakeEpoch) {
          const sleepMs = wakeEpoch - Date.now();
          if (!(await this.sleep(sleepMs))) return { delayMs: 0, state: this.circuitState, aborted: true };
          this.domainCooldowns.delete(domain);
        }
      } catch (e) {}

      // 3. Token Bucket Gate (Rate Limit)
      this.refillTokens();
      if (this.tokens < 1.0) {
        const neededTokens = 1.0 - this.tokens;
        const waitMs = Math.ceil(neededTokens / this.tokenFillRatePerMs);
        if (!(await this.sleep(waitMs))) return { delayMs: 0, state: this.circuitState, aborted: true };
        this.refillTokens();
      }
      this.tokens -= 1.0;

      // 4. Calculate Dynamic Polite Delay (Human-Cadence + EWMA Adaptation)
      let calculatedDelay = this.calculateJitter(this.minDelayMs, this.maxDelayMs);

      // If EWMA indicates server strain (> 35% above baseline), adaptively stretch delay
      if (this.adaptiveEwma && this.ewmaLatencyMs && this.baselineLatencyMs) {
        const strainRatio = this.ewmaLatencyMs / Math.max(50, this.baselineLatencyMs);
        if (strainRatio > 1.35) {
          const stretchFactor = Math.min(3.0, strainRatio);
          calculatedDelay = Math.round(calculatedDelay * stretchFactor);
          if (this.circuitState === CircuitState.NOMINAL) {
            this.circuitState = CircuitState.THROTTLED;
            this.notifyState();
          }
        }
      }

      // If currently throttled by recent error, use decorrelated back-off delay
      if (this.circuitState === CircuitState.THROTTLED) {
        calculatedDelay = Math.max(calculatedDelay, this.currentBackoffDelayMs);
      }

      if (!(await this.sleep(calculatedDelay))) return { delayMs: 0, state: this.circuitState, aborted: true };
      return { delayMs: calculatedDelay, state: this.circuitState, aborted: false };
    }

    getTelemetry() {
      return {
        circuitState: this.circuitState,
        consecutiveErrors: this.consecutiveErrors,
        ewmaLatencyMs: this.ewmaLatencyMs || 0,
        baselineLatencyMs: this.baselineLatencyMs || 0,
        availableTokens: parseFloat(this.tokens.toFixed(2)),
        maxRpm: this.maxRpm
      };
    }
  }

  PolitenessEngine.CircuitState = CircuitState;
  return PolitenessEngine;
}));

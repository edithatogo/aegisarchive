import os
import sys
import threading
import time
import unittest
import copy
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
from politeness import CircuitState, PolitenessEngine  # noqa: E402


class TestPoliteness(unittest.TestCase):
    def test_durable_pacing_restore(self):
        now = [1000.0]
        config = {'min_delay_ms': 100, 'max_delay_ms': 100}
        engine = PolitenessEngine(config, clock=lambda: now[0])
        engine.tokens = 0
        for _ in range(3):
            engine.record_failure('http://h.test/', 429, '120')
        state = json.loads(json.dumps(engine.export_state()))
        now[0] = 990  # backward wall clock: replay remaining waits
        restored = PolitenessEngine(config, clock=lambda: now[0])
        restored.restore_state(state)
        self.assertEqual(restored.tokens, 0)
        self.assertEqual(restored.last_token_refill, 990)
        self.assertGreaterEqual(restored.domain_cooldowns['h.test'], 1120)
        self.assertEqual(restored.circuit_state, CircuitState.TRIPPED)
        waits = []
        restored._sleeper = lambda seconds: waits.append(seconds) or False
        self.assertTrue(restored.acquire_permission('http://h.test/')['aborted'])
        self.assertGreaterEqual(waits[0], 60)
        restored.domain_cooldowns['h.test'] = 2000
        restored.restore_state(state)
        self.assertEqual(restored.domain_cooldowns['h.test'], 2000)

    def test_restore_rejects_atomically(self):
        engine = PolitenessEngine(clock=lambda: 1000)
        original = engine.export_state()
        for field, value in [('tokens', float('nan')), ('consecutive_errors', True),
                             ('warmup_samples', [float('inf')]), ('version', 2)]:
            state = copy.deepcopy(original)
            state[field] = value
            with self.assertRaises(ValueError):
                engine.restore_state(state)
            self.assertEqual(engine.export_state(), original)
        state = copy.deepcopy(original)
        state['config']['burst_limit'] += 1
        with self.assertRaises(ValueError):
            engine.restore_state(state)

    def test_forward_restore_waits_until_deadline_without_new_burst(self):
        now = [1000.0]
        config = {'burst_limit': 1, 'max_requests_per_minute': 1,
                  'min_delay_ms': 100, 'max_delay_ms': 100}
        engine = PolitenessEngine(config, clock=lambda: now[0])
        engine.record_success('http://h.test/', 300)
        for _ in range(3):
            engine.record_failure('http://h.test/', 503, '120')
        engine.tokens = 0
        engine.next_permission_at = 1130
        state = engine.export_state()
        now[0] = 1010
        restored = PolitenessEngine(config, clock=lambda: now[0])
        restored.restore_state(state)
        self.assertEqual(restored.domain_cooldowns['h.test'], 1120)
        self.assertEqual(restored.next_permission_at, 1130)
        self.assertEqual(restored.ewma_latency_ms, 300)
        self.assertEqual(restored.warmup_samples, [300])
        self.assertEqual(restored.current_backoff_delay_ms, engine.current_backoff_delay_ms)
        waits = []
        def sleep(seconds):
            waits.append(seconds)
            now[0] += seconds
            return True
        restored._sleeper = sleep
        self.assertFalse(restored.acquire_permission('http://h.test/')['aborted'])
        self.assertEqual(waits[0], 50)
        self.assertGreaterEqual(now[0], 1130)
        self.assertEqual(restored.circuit_state, CircuitState.HALF_OPEN)
        # Immediate recovery of an empty bucket cannot regain constructor tokens.
        state['saved_at_ms'] = now[0] * 1000
        state['last_refill_ms'] = now[0] * 1000
        state['circuit_state'] = CircuitState.NOMINAL
        state['circuit_until_ms'] = None
        state['domain_cooldowns'] = {}
        fresh = PolitenessEngine(config, clock=lambda: now[0], sleeper=lambda seconds: False)
        fresh.restore_state(state)
        self.assertTrue(fresh.acquire_permission('http://h.test/')['aborted'])


    def test_latency_ewma_and_warmup_baseline(self):
        e = PolitenessEngine({})
        e.record_success("http://h.test/", 5)
        self.assertIsNone(e.baseline_latency_ms)

        for _ in range(9):
            e.record_success("http://h.test/", 300)

        self.assertEqual(e.baseline_latency_ms, 300)
        self.assertEqual(len(e.warmup_samples), 10)

        e.record_success("http://h.test/", 1000)
        self.assertEqual(e.baseline_latency_ms, 314)

    def test_circuit_breaker_failure_counting(self):
        f = PolitenessEngine({})
        for _ in range(3):
            f.record_failure("http://h.test/", 404)
        self.assertEqual(f.circuit_state, CircuitState.NOMINAL)
        self.assertEqual(f.consecutive_errors, 0)

        for _ in range(3):
            f.record_failure("http://h.test/", 503)
        self.assertEqual(f.circuit_state, CircuitState.TRIPPED)

    def test_retry_after_parsing_and_capping(self):
        g = PolitenessEngine({"cooldown_seconds": 60})
        g.record_failure("http://h.test/", 429, "999999")
        self.assertLessEqual(g.domain_cooldowns["h.test"] - time.time(), 600.5)

        self.assertEqual(g.parse_retry_after("120"), 120000)

        future_date = "Wed, 21 Oct 2099 07:28:00 GMT"
        parsed_future = g.parse_retry_after(future_date)
        self.assertIsNotNone(parsed_future)
        self.assertGreaterEqual(parsed_future, 1000)

        self.assertIsNone(g.parse_retry_after("not-a-date-or-number"))
        self.assertIsNone(g.parse_retry_after(""))
        self.assertIsNone(g.parse_retry_after(None))

    def test_stop_event_interrupts_acquire_permission(self):
        h = PolitenessEngine({"cooldown_seconds": 60})
        h.record_failure("http://h.test/", 429, "120")
        threading.Timer(0.05, h.stop_event.set).start()
        start = time.time()
        result = h.acquire_permission("http://h.test/")
        self.assertTrue(result["aborted"])
        self.assertLess(time.time() - start, 1.0)

    def test_token_bucket_wait_with_sleeper_stub(self):
        slept_durations = []

        def mock_sleeper(secs):
            slept_durations.append(secs)
            return True

        curr_time = [1000.0]

        def mock_clock():
            return curr_time[0]

        engine = PolitenessEngine(
            {
                "burst_limit": 1,
                "max_requests_per_minute": 60,
                "min_delay_ms": 100,
                "max_delay_ms": 100,
            },
            clock=mock_clock,
            sleeper=mock_sleeper,
        )

        res1 = engine.acquire_permission("http://h.test/")
        self.assertFalse(res1["aborted"])

        res2 = engine.acquire_permission("http://h.test/")
        self.assertFalse(res2["aborted"])
        self.assertTrue(any(0.9 <= dur <= 1.1 for dur in slept_durations))

    def test_get_telemetry_keys(self):
        engine = PolitenessEngine({"max_requests_per_minute": 45})
        telemetry = engine.get_telemetry()
        expected_keys = {
            "circuit_state",
            "consecutive_errors",
            "ewma_latency_ms",
            "baseline_latency_ms",
            "available_tokens",
            "max_rpm",
        }
        self.assertTrue(expected_keys.issubset(set(telemetry.keys())))
        self.assertEqual(telemetry["max_rpm"], 45)


if __name__ == "__main__":
    unittest.main()

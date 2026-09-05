import os
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
from politeness import CircuitState, PolitenessEngine  # noqa: E402


class TestPoliteness(unittest.TestCase):
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

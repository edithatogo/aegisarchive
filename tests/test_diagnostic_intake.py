import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.diagnostic_intake import ingest, main, transition, validate_ledger


def report():
    return {'schema_version': 1, 'coverage': {'captured': 0, 'failed': 1},
            'events': [
                {'stage': 'transport', 'error_type': 'TypeError', 'url': 'https://private.invalid/?token=secret',
                 'error': {'message': 'secret account and content'}, 'attempt': 1},
                {'stage': 'transport', 'error_type': 'TypeError', 'attempt': 2}]}


class DiagnosticIntakeTests(unittest.TestCase):
    def test_redacts_payload_and_untrusted_labels(self):
        source = report()
        source['events'].append({'stage': 'PrivatePerson', 'error_type': 'AccessToken123',
                                 'stack': 'sensitive secret', 'message': 'private'})
        ledger = ingest(source)
        serialized = json.dumps(ledger)
        for secret in ('https', 'private', 'secret', 'PrivatePerson', 'AccessToken123', 'stack', 'message'):
            self.assertNotIn(secret, serialized)
        self.assertEqual(len(ledger['findings']), 3)
        self.assertTrue(any(item['stage'] == 'unknown' for item in ledger['findings']))

    def test_deduplicates_retries_and_repeat_imports(self):
        source = report()
        ledger = ingest(source)
        self.assertEqual(ingest(source, ledger), ledger)
        finding = next(item for item in ledger['findings'] if item['stage'] == 'transport')
        self.assertEqual(finding['occurrences'], 2)
        second = report()
        second['session_id'] = 'different-session'
        combined = ingest(second, ledger)
        current = next(item for item in combined['findings'] if item['stage'] == 'transport')
        self.assertEqual(current['fingerprint'], finding['fingerprint'])
        self.assertEqual(current['occurrences'], 4)
        self.assertEqual(len(current['report_hashes']), 2)

    def test_http_failure_but_not_success_or_robots_policy(self):
        source = {'schema_version': 1, 'coverage': {}, 'events': [
            {'stage': 'http_response', 'status': 403},
            {'stage': 'captured', 'status': 200}, {'stage': 'robots', 'status': -1}]}
        findings = ingest(source)['findings']
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['error_type'], 'HTTPError')

    def test_exported_nested_coverage_produces_zero_saved_finding(self):
        data = {'schema_version': 1, 'coverage': {'counts': {'captured': 0, 'failed': 1}}, 'events': []}
        result = ingest(data)
        self.assertEqual(result['findings'][0]['error_type'], 'no_resources_saved')

    def test_lifecycle_preserved_and_new_occurrence_flagged(self):
        ledger = ingest(report())
        key = ledger['findings'][0]['fingerprint']
        with self.assertRaises(ValueError):
            transition(ledger, key, 'verified', b'ci passed')
        for state in ('reproduced', 'fixed', 'verified'):
            ledger = transition(ledger, key, state, b'local evidence containing private details')
            self.assertEqual(ingest(report(), ledger), ledger)
        second = report()
        second['session_id'] = 'new-run'
        ledger = ingest(second, ledger)
        current = next(item for item in ledger['findings'] if item['fingerprint'] == key)
        self.assertEqual(current['state'], 'verified')
        self.assertTrue(current['recurrence_after_verification'])
        ledger = transition(ledger, key, 'proposed', b'new report triage')
        self.assertEqual(ledger['findings'][0]['state'], 'proposed')
        self.assertNotIn('private details', json.dumps(ledger))

    def test_rejects_untrusted_ledger_and_empty_evidence(self):
        ledger = ingest(report())
        with self.assertRaises(ValueError):
            transition(ledger, ledger['findings'][0]['fingerprint'], 'reproduced', b' ')
        ledger['findings'][0]['private_url'] = 'https://private.invalid'
        with self.assertRaises(ValueError):
            validate_ledger(ledger)

    def test_cli_write_repeat_and_safe_error_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'private.json'
            ledger = Path(folder) / 'ledger.json'
            source.write_text(json.dumps(report()), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(source), '--ledger', str(ledger)]), 0)
                initial = ledger.read_bytes()
                self.assertEqual(main([str(source), '--ledger', str(ledger)]), 0)
            self.assertEqual(ledger.read_bytes(), initial)
            with contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(main([str(source), '--ledger', str(source)]), 2)
            self.assertNotIn(folder, output.getvalue())
            self.assertEqual(json.loads(source.read_text()), report())
            source.write_text('{private-secret-invalid', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertEqual(main([str(source), '--ledger', str(ledger)]), 2)
            self.assertNotIn('secret', output.getvalue())
            self.assertEqual(ledger.read_bytes(), initial)


if __name__ == '__main__':
    unittest.main()

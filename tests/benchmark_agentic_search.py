"""Compare both modes on a fixed synthetic WARC with a provisioned local model."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from cli.aegis_cli import PythonWarcWriter
from cli.warc_verify import RECORD_SEPARATOR, parse_warc_header
from portable.archive_search_intake import build_catalogue
from portable.document_catalogue import Catalogue
from portable.document_search import SearchIndex, _literal_query
from portable.intelligence import LocalTools

DOCUMENTS = {
    'leave': 'Leave approval is delegated to the duty officer. Requests are recorded in a leave register.',
    'backups': 'Workstation backups are verified each Friday. Restore copies are kept offline.',
    'orders': 'Purchase orders above the spending threshold require written authorisation by the finance director.',
    'induction': 'New starter orientation takes place on the first Monday. The training coordinator supplies induction materials.',
    'freezer': 'Cold storage alarms trigger a telephone call to the facilities duty supervisor.',
    'visitors': 'Visitors are issued a temporary visitor pass at reception for the duration of the visit.',
}
CASES = (
    ('exact', 'leave approval', 'leave'),
    ('exact', 'workstation backups', 'backups'),
    ('exact', 'visitor pass', 'visitors'),
    ('paraphrase', 'Who signs off on time away?', 'leave'),
    ('paraphrase', 'How often do they verify backup copies?', 'backups'),
    ('paraphrase', 'Who authorizes bigger orders?', 'orders'),
    ('paraphrase', 'When is onboarding for new hires?', 'induction'),
    ('paraphrase', 'Who gets called when the freezer alarm goes off?', 'freezer'),
    ('paraphrase', 'Where do guests get a temporary badge?', 'visitors'),
    ('out_of_scope', 'How much does a new solar panel cost?', None),
    ('out_of_scope', 'When do the intercity trains depart?', None),
)


def _url(name):
    return 'https://fixture.test/' + name


def _timed_search(lookup):
    start = perf_counter()
    result = lookup()
    return result, round(1000 * (perf_counter() - start), 2)


def _citation_matches(hit, capture):
    reference = hit['warc']
    start = reference['offset']
    frame = capture[start:start + reference['length']]
    header, _, block = frame.partition(RECORD_SEPARATOR)
    fields, length = parse_warc_header(header)
    _, _, payload = block[:length].partition(RECORD_SEPARATOR)
    return (
        reference['archive_id'] == 1 and reference['offset_kind'] == 'file'
        and len(block) == length + len(RECORD_SEPARATOR)
        and block[length:] == RECORD_SEPARATOR
        and reference['record_id'] == fields['warc-record-id']
        and reference['captured_at'] == fields['warc-date']
        and hit['original']['url'] == fields['warc-target-uri']
        and hit['original']['revision_id'] == hit['revision_id']
        and hit['original']['content_hash'] == hashlib.sha256(payload).hexdigest()
    )


def _score(hits, expected_revision, capture):
    revisions = [hit['revision_id'] for hit in hits]
    return dict(relevant=expected_revision in revisions, empty=not revisions,
                non_target_hits=sum(revision != expected_revision for revision in revisions),
                citation_errors=sum(not _citation_matches(hit, capture) for hit in hits),
                revision_ids=revisions)


def _sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def compare(manifest):
    tools = LocalTools(manifest)
    runner = tools.asset('llama')
    scout = tools.asset('scout')
    model_sha, runner_sha = _sha256(scout), _sha256(runner)
    version = subprocess.run([str(runner), '--version'], check=True, timeout=15,
                             capture_output=True, text=True)
    fixture_sha = hashlib.sha256(
        json.dumps([DOCUMENTS, CASES], sort_keys=True).encode()
    ).hexdigest()
    results = []
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        warc = root / 'fixture.warc'
        database = root / 'saved.sqlite'
        with closing(PythonWarcWriter(str(warc))) as writer:
            for name, text in DOCUMENTS.items():
                writer.write_response(_url(name), 200, {'Content-Type': 'text/plain'}, text.encode())
        intake = build_catalogue(database, [warc], handling='public')
        if intake['indexed'] != len(DOCUMENTS):
            raise RuntimeError('benchmark WARC did not produce every expected document')
        archive_bytes = warc.read_bytes()
        with closing(Catalogue(database, read_only=True)) as catalogue:
            index = SearchIndex(catalogue)
            for kind, query, expected in CASES:
                revision = None
                if expected is not None:
                    capture, = catalogue.acquisitions(_url(expected))
                    revision = capture['revision_id']
                    if catalogue.original(revision) != DOCUMENTS[expected].encode():
                        raise RuntimeError('benchmark reference content mismatch')
                # Both modes start with the same literalised query and the same index.
                ordinary, ordinary_ms = _timed_search(lambda: index.search(_literal_query(query, 64), limit=3))
                agentic, agentic_ms = _timed_search(lambda: index.search_agentic(query, manifest, limit=3))
                if agentic['follow_up'] == 'model_unavailable':
                    raise RuntimeError('local model failed during comparison')
                results.append(dict(kind=kind, query=query, expected_revision_id=revision,
                                    ordinary=dict(**_score(ordinary, revision, archive_bytes), elapsed_ms=ordinary_ms),
                                    agentic=dict(**_score(agentic['hits'], revision, archive_bytes), elapsed_ms=agentic_ms,
                                                 follow_up=agentic['follow_up'])))
    summary = {}
    for mode in ('ordinary', 'agentic'):
        summary[mode] = dict(
            exact_found=sum(row[mode]['relevant'] for row in results if row['kind'] == 'exact'),
            paraphrase_found=sum(row[mode]['relevant'] for row in results if row['kind'] == 'paraphrase'),
            out_of_scope_empty=sum(row[mode]['empty'] for row in results if row['kind'] == 'out_of_scope'),
            non_target_hits=sum(row[mode]['non_target_hits'] for row in results),
            citation_errors=sum(row[mode]['citation_errors'] for row in results),
            median_ms=median(row[mode]['elapsed_ms'] for row in results),
        )
    summary['agentic']['model_calls'] = sum(row['agentic']['follow_up'] != 'not_needed' for row in results)
    root = Path(__file__).resolve().parents[1]
    sources = ('cli/aegis_cli.py', 'cli/warc_verify.py', 'portable/archive_search_intake.py',
               'portable/document_catalogue.py', 'portable/document_search.py', 'portable/intelligence.py',
               'tests/benchmark_agentic_search.py')
    return dict(fixture_sha256=fixture_sha, document_count=len(DOCUMENTS), top_k=3,
                measured_at=datetime.now(timezone.utc).isoformat(),
                source_sha256={path: _sha256(root / path) for path in sources},
                platform=f'{platform.system()} {platform.machine()}', python=platform.python_version(),
                model_sha256=model_sha, runner_sha256=runner_sha,
                runner_version=(version.stderr + version.stdout).strip().splitlines()[0],
                summary=summary, cases=results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', help='Trusted local manifest for llama-cli and a Scout GGUF')
    print(json.dumps(compare(parser.parse_args().manifest), indent=2))

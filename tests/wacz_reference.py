"""Build a synthetic WACZ and read its indexed responses using Webrecorder tools."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from warcio.archiveiterator import ArchiveIterator

from tests.test_wacz_export import create_archive, DOCUMENT, STYLESHEET


def validate(bundle, expected):
    result = subprocess.run(
        [sys.executable, '-m', 'wacz', 'validate', '-f', str(bundle)], capture_output=True, text=True, check=False)
    # Some reference validator errors are reported in its output with exit status zero.
    if expected not in result.stdout or (expected.startswith('Validation succeeded') and result.returncode):
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


def read_response(package, row):
    with package.open('archive/' + row['filename']) as warc:
        warc.seek(int(row['offset']))
        member = warc.read(int(row['length']))
    records = iter(ArchiveIterator(io.BytesIO(member)))
    record = next(records)
    assert record.rec_type == 'response'
    assert record.rec_headers.get_header('WARC-Target-URI') == row['url']
    body = record.content_stream().read()
    assert next(records, None) is None
    assert 'sha256:' + hashlib.sha256(body).hexdigest() == row['digest']
    assert record.http_headers.get_statuscode() == row['status']
    return {'body': body.decode('utf-8'), 'type': record.http_headers.get_header('Content-Type')}


def replay_fixture(folder, origin, exporter):
    warc = folder / 'reference.warc'
    bundle = folder / 'reference.wacz'
    create_archive(warc, origin)
    subprocess.run([exporter, '-m', 'cli.export_mirror', 'wacz', str(warc), str(bundle)],
                   check=True, capture_output=True, text=True)
    accepted = validate(bundle, 'Validation succeeded, the passed WACZ is valid')
    tampered = folder / 'tampered.wacz'
    with ZipFile(bundle) as package, ZipFile(tampered, 'w') as changed:
        index = package.read('indexes/index.cdxj')
        rows = [json.loads(line.split(b' ', 2)[2]) for line in index.splitlines()]
        responses = {row['url']: read_response(package, row) for row in rows}
        for name in package.namelist():
            changed.writestr(name, package.read(name) if name != 'indexes/index.cdxj' else index + b'\n')
    rejected = validate(tampered, 'Validation failed, the passed WACZ is invalid')
    assert "'type': 'hash-count'" in rejected
    assert responses == {
        origin + '/archive.html': {'body': DOCUMENT.decode('utf-8'), 'type': 'text/html'},
        origin + '/archive.css': {'body': STYLESHEET.decode('utf-8'), 'type': 'text/css'},
    }
    return {'responses': responses, 'validator': accepted.strip(), 'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('origin')
    parser.add_argument('--exporter', default=sys.executable)
    arguments = parser.parse_args()
    print(json.dumps(replay_fixture(arguments.folder, arguments.origin, arguments.exporter)))

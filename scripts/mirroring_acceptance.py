#!/usr/bin/env python3
"""Validate measured mirroring receipts; no platform execution is implied.

Observations use schema aegis.mirroring-observations.v2, source_before and
source_after snapshots, runtime (system/machine/python/browser), the top-level
MEASUREMENTS groups, and artifacts.warc/cdx {path, sha256, bytes}. Artifact paths
are relative to the observations directory; receipt paths to its own directory.
Keep generated evidence in artifacts/ (untracked); commit all source before runs.
Hashes bind supplied evidence, not its truth: the browser driver owns measurement.
"""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = 'tests/browser/fixtures/mirroring-site.json'
SCHEMA = 'aegis.mirroring-acceptance.v2'
# pyproject.toml requires >=3.9; package.json/package-lock.json pin Playwright.
MINIMUM_PYTHON = (3, 9, 0)
PLAYWRIGHT_VERSION = '1.63.0'
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MEASUREMENTS = {
    'capture': {'responses': ('int', 1), 'warc_verified': ('bool', True),
                'expected_payload_hashes_verified': ('bool', True)},
    'offline': {'source_stopped': ('bool', True), 'source_unreachable': ('bool', True),
                'navigation_visits': ('int', 4), 'links_verified': ('bool', True),
                'css_verified': ('bool', True), 'image_verified': ('bool', True),
                'unexpected_requests': ('zero', 0), 'source_requests': ('zero', 0),
                'page_errors': ('zero', 0)},
    'authentication': dict.fromkeys(('denied', 'expired', 'redacted'), ('bool', True)),
    'recovery': dict.fromkeys(('interrupted', 'resumed', 'bytes_preserved',
                               'reload_recovered'), ('bool', True)),
    'launcher': dict.fromkeys(('ordinary', 'relocated', 'missing_runtime_diagnostic'), ('bool', True)),
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def receipt_hash(data):
    return sha(canonical({k: v for k, v in data.items() if k != 'receipt_sha256'}))


def bounded_read(path, limit):
    with Path(path).open('rb') as handle:
        content = handle.read(limit + 1)
    if len(content) > limit:
        raise ValueError('evidence exceeds byte limit')
    return content


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    data = json.loads(bounded_read(path, MAX_JSON_BYTES).decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if type(data) is not dict:
        raise ValueError('expected JSON object')
    return data


def safe_path(base, name):
    if (type(name) is not str or not name or '\\' in name
            or PureWindowsPath(name).drive or PurePosixPath(name).is_absolute()
            or any(part in ('..', '.', '') for part in name.split('/'))):
        raise ValueError('artifact path must be a relative path without traversal')
    base = Path(base).absolute()
    path = base
    # Inspect the base's ancestors too: resolving first would hide symlinks.
    for parent in (base, *base.parents):
        if parent.is_symlink():
            raise ValueError('symlink evidence directory')
    for part in name.split('/'):
        path = path / part
        if path.is_symlink():
            raise ValueError('symlink artifact')
    if not path.is_file():
        raise ValueError('missing artifact: ' + name)
    return path


def file_binding(path, base, max_bytes=None):
    path, base = Path(path).absolute(), Path(base).absolute()
    try:
        name = path.relative_to(base).as_posix()
    except ValueError as exc:
        raise ValueError('evidence must be inside the receipt directory') from exc
    content = bounded_read(safe_path(base, name),
                           MAX_ARTIFACT_BYTES if max_bytes is None else max_bytes)
    return {'path': name, 'sha256': sha(content), 'bytes': len(content)}


def verify_binding(binding, base, max_bytes=None):
    if type(binding) is not dict or set(binding) != {'path', 'sha256', 'bytes'}:
        raise ValueError('malformed artifact binding')
    if (type(binding['bytes']) is not int or binding['bytes'] <= 0
            or type(binding['sha256']) is not str
            or not re.fullmatch('[0-9a-f]{64}', binding['sha256'])):
        raise ValueError('invalid artifact size or digest')
    path = safe_path(base, binding['path'])
    if file_binding(path, base, max_bytes) != binding:
        raise ValueError('artifact content changed')
    return path


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.DEVNULL)


def committed_source(revision):
    """Hash committed blobs, independent of checkout line-ending conversion."""
    if type(revision) is not str or not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('invalid recorded revision')
    if Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve() != ROOT.resolve():
        raise ValueError('missing repository')
    if git('rev-parse', '--verify', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('recorded revision is not a commit')
    entries = []
    for row in git('ls-tree', '-rz', '--full-tree', revision).split(b'\0'):
        if not row:
            continue
        header, name = row.split(b'\t', 1)
        mode, kind, oid = header.split()
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise ValueError('source tree contains symlink or non-file')
        entries.append((name.decode('utf-8'), oid.decode('ascii')))
    proc = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '--batch'],
                          input=''.join(oid + '\n' for _, oid in entries).encode('ascii'),
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    blobs, offset = {}, 0
    for name, oid in entries:
        end = proc.stdout.index(b'\n', offset)
        object_id, kind, size = proc.stdout[offset:end].split()
        if object_id.decode() != oid or kind != b'blob':
            raise ValueError('invalid Git blob')
        offset = end + 1
        length = int(size)
        blobs[name] = proc.stdout[offset:offset + length]
        offset += length + 1
    digest = hashlib.sha256()
    for name in sorted(blobs):
        digest.update(canonical([name, sha(blobs[name])]))
    return {'revision': revision, 'implementation_sha256': digest.hexdigest(),
            'worktree_clean': True}, blobs


def snapshot():
    """Independently hash committed source and require an unchanged checkout.

    Only untracked evidence under artifacts/ is excluded from cleanliness.
    Every tracked file is read independently of index flags. Text checkouts may
    differ only by uniform LF-to-CRLF expansion (no NUL or preexisting CRLF).
    Git metadata must belong to ROOT, never an enclosing repository.
    """
    result = {'revision': None, 'implementation_sha256': None, 'worktree_clean': False}
    try:
        if Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve() != ROOT.resolve():
            return result
        revision = git('rev-parse', '--verify', 'HEAD').decode().strip()
        if not re.fullmatch('[0-9a-f]{40}', revision):
            return result
        source, blobs = committed_source(revision)
        bytes_match = True
        for name, committed in blobs.items():
            actual = safe_path(ROOT, name).read_bytes()
            crlf_checkout = (b'\0' not in committed and b'\r\n' not in committed
                             and actual == committed.replace(b'\n', b'\r\n'))
            bytes_match &= actual == committed or crlf_checkout
        changes = git('status', '--porcelain=v1', '-z', '--untracked-files=all').decode().split('\0')
        clean = all(not line or line.startswith('?? artifacts/') for line in changes)
        clean &= FIXTURE in blobs and bytes_match
        result.update(source, worktree_clean=clean)
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError):
        pass
    return result


def runtime():
    return {'system': platform.system(), 'machine': platform.machine(),
            'python': platform.python_version(), 'browser': None}


def runtime_status(observed):
    """Qualify only numeric supported Python and the pinned Chromium harness."""
    if observed is None:
        return 'pending'
    if type(observed) is not dict:
        raise ValueError('invalid runtime')
    browser = observed.get('browser')
    if browser is not None and type(browser) is not dict:
        raise ValueError('invalid browser runtime')
    browser = browser or {}
    values = (observed.get('python'), browser.get('name'),
              browser.get('version'), browser.get('playwright_version'))
    pending = any(value is None for value in values)
    for value in values:
        if value is not None and type(value) is not str:
            raise ValueError('runtime versions and browser name must be strings')
    python, name, version, playwright = values
    if python is not None:
        if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', python):
            return 'failed'
        if tuple(map(int, python.split('.'))) < MINIMUM_PYTHON:
            return 'failed'
    if name is not None and name != 'chromium':
        return 'failed'
    if version is not None and not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', version):
        return 'failed'
    if playwright is not None and playwright != PLAYWRIGHT_VERSION:
        return 'failed'
    return 'pending' if pending else 'passed'


def fixture_hashes(blobs=None):
    fixture = (json.loads(blobs[FIXTURE].decode('utf-8')) if blobs is not None
               else load(safe_path(ROOT, FIXTURE)))
    if not fixture:
        raise ValueError('empty fixture')
    hashes = {}
    for name, entry in fixture.items():
        if (not name.startswith('/') or type(entry) is not dict
                or type(entry.get('mime')) is not str or not entry['mime']
                or type(entry.get('body')) is not str):
            raise ValueError('fixture must map paths to mime/body strings')
        hashes[name] = sha(entry['body'].encode('utf-8'))
    identity = {name: {'mime': entry['mime'], 'body_sha256': hashes[name]}
                for name, entry in fixture.items()}
    return hashes, sha(canonical(identity))


def measured_status(observations):
    pending, failed = False, False
    for group, fields in MEASUREMENTS.items():
        values = observations.get(group)
        if values is None:
            pending = True
            continue
        if type(values) is not dict:
            raise ValueError('invalid measurement group: ' + group)
        for key, (kind, minimum) in fields.items():
            value = values.get(key)
            if value is None:
                pending = True
                continue
            expected = bool if kind == 'bool' else int
            if type(value) is not expected:
                raise ValueError('invalid measurement type: ' + group + '.' + key)
            failed |= (value is False if kind == 'bool' else
                       value != 0 if kind == 'zero' else value < minimum)
    mode = (observations.get('recovery') or {}).get('mode')
    if mode is None:
        pending = True
    elif type(mode) is not str or not mode:
        raise ValueError('invalid recovery.mode')
    elif mode != 'durable_reload_resume':
        failed = True
    return 'failed' if failed else 'pending' if pending else 'passed'


def build(output, observations_path=None, enforce_runtime=True, recorded_source=None):
    output = Path(output).absolute()
    blobs = None
    if recorded_source is None:
        source = snapshot()
    else:
        source, blobs = committed_source(recorded_source.get('revision'))
        if canonical(recorded_source) != canonical(source):
            raise ValueError('recorded provenance does not match Git tree')
    hashes, fixture_digest = fixture_hashes(blobs)
    result = {'schema': SCHEMA, 'qualification_status': 'pending',
              'provenance': source, 'fixture_hashes': hashes, 'fixture_sha256': fixture_digest,
              'runtime': runtime(), 'artifacts': {},
              **{group: None for group in MEASUREMENTS}}
    if observations_path is not None:
        observations_path = Path(observations_path).absolute()
        observation_binding = file_binding(observations_path, output.parent, MAX_JSON_BYTES)
        observations = load(observations_path)
        if observations.get('schema') != 'aegis.mirroring-observations.v2':
            raise ValueError('unsupported observations schema')
        status = measured_status(observations)
        for group in MEASUREMENTS:
            result[group] = observations.get(group)
        for key in ('source_before', 'source_after'):
            value = observations.get(key)
            if value is None:
                if status != 'failed':
                    status = 'pending'
            elif (type(value) is not dict or type(value.get('worktree_clean')) is not bool):
                raise ValueError('malformed source snapshot')
            elif any(type(value.get(field)) is not str or not re.fullmatch(pattern, value[field])
                     for field, pattern in (('revision', '[0-9a-f]{40}'),
                                            ('implementation_sha256', '[0-9a-f]{64}'))):
                raise ValueError('malformed source revision or implementation digest')
            elif value != source or not source['worktree_clean']:
                status = 'failed'
        observed_runtime = observations.get('runtime')
        runtime_qualification = runtime_status(observed_runtime)
        if runtime_qualification == 'failed':
            status = 'failed'
        elif runtime_qualification == 'pending' and status != 'failed':
            status = 'pending'
        if observed_runtime is None:
            if status != 'failed':
                status = 'pending'
        else:
            if type(observed_runtime) is not dict:
                raise ValueError('invalid runtime')
            for key in ('system', 'machine', 'python'):
                value = observed_runtime.get(key)
                if value is None:
                    if status != 'failed':
                        status = 'pending'
                elif type(value) is not str or not value:
                    raise ValueError('invalid runtime.' + key)
                elif enforce_runtime and value != runtime()[key]:
                    status = 'failed'
            browser = observed_runtime.get('browser')
            if browser is not None and type(browser) is not dict:
                raise ValueError('invalid browser runtime')
            for key in ('name', 'version', 'playwright_version'):
                value = (browser or {}).get(key)
                if value is None:
                    if status != 'failed':
                        status = 'pending'
                elif type(value) is not str or not value.strip():
                    raise ValueError('invalid browser.' + key)
            result['runtime'] = observed_runtime
        artifacts = observations.get('artifacts')
        if artifacts is not None and type(artifacts) is not dict:
            raise ValueError('invalid artifacts')
        for kind in ('warc', 'cdx'):
            binding = (artifacts or {}).get(kind)
            if binding is None:
                if status != 'failed':
                    status = 'pending'
                continue
            path = verify_binding(binding, observations_path.parent)
            result['artifacts'][kind] = file_binding(path, output.parent)
        result['artifacts']['observations'] = observation_binding
        if not source['worktree_clean'] or not source['revision']:
            status = 'failed'
        if recorded_source is None and snapshot() != source:
            status = 'failed'
        result['qualification_status'] = status
    result['receipt_sha256'] = receipt_hash(result)
    return result


def receipt(output, observations_path=None):
    result = build(output, observations_path)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return result


def check(output):
    try:
        if Path(output).is_symlink():
            return False
        data = load(output)
        if data.get('schema') != SCHEMA or data.get('receipt_sha256') != receipt_hash(data):
            return False
        binding = data.get('artifacts', {}).get('observations')
        if binding is None:
            return False
        path = verify_binding(binding, Path(output).absolute().parent, MAX_JSON_BYTES)
        expected = build(output, path, enforce_runtime=False, recorded_source=data.get('provenance'))
        return canonical(data) == canonical(expected) and expected['qualification_status'] == 'passed'
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError,
            subprocess.SubprocessError):
        return False


def compare(outputs):
    if len(outputs) != 2 or not all(check(path) for path in outputs):
        return False
    values = [load(path) for path in outputs]
    platforms = {(v['runtime']['system'], v['runtime']['machine']) for v in values}
    return (platforms == {('Darwin', 'arm64'), ('Windows', 'AMD64')}
            and all(values[0][key] == values[1][key]
                    for key in ('provenance', 'fixture_hashes', 'fixture_sha256')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='artifacts/mirroring-acceptance.json')
    parser.add_argument('--observations', help='measured observations JSON')
    parser.add_argument('--check', action='store_true', help='recheck receipt and files; pending/failed exit 1')
    parser.add_argument('--snapshot', action='store_true', help='print current Git-derived source snapshot')
    parser.add_argument('--compare', nargs=2, metavar=('MAC_RECEIPT', 'WINDOWS_RECEIPT'))
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            print(json.dumps(snapshot(), sort_keys=True))
            return 0
        if args.compare:
            passed = compare(args.compare)
        elif args.check:
            passed = check(args.output)
        else:
            result = receipt(args.output, args.observations)
            print('acceptance: ' + result['qualification_status'])
            return 0
        print('acceptance: ' + ('passed' if passed else 'pending/failed'))
        return 0 if passed else 1
    except (OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.SubprocessError) as exc:
        print('acceptance: invalid: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

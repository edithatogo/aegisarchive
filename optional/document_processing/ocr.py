"""Explicit local OCR; the parent has no third-party imports."""
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading

MAX_BYTES = 33554432
MAX_OUTPUT = 4194304
TIMEOUT = 60
MIMES = {'image/png', 'image/jpeg', 'image/tiff', 'application/pdf'}


def valid_coverage(value, locators, text, status):
    coverage = value['coverage']
    if coverage == {'scope': 'unassessed'}:
        return status in {'failed', 'encrypted', 'unsupported'} and not text and not locators
    fields = {'scope', 'total_pages', 'visited_pages', 'pages_with_text',
              'missing_text_pages', 'raster_pixels'}
    if set(coverage) != fields or coverage['scope'] != 'ocr_pages':
        return False
    for key in ('total_pages', 'visited_pages', 'pages_with_text', 'raster_pixels'):
        if type(coverage[key]) is not int or coverage[key] < 0:
            return False
    total, visited = coverage['total_pages'], coverage['visited_pages']
    missing = coverage['missing_text_pages']
    if (not isinstance(missing, list) or any(type(p) is not int or not 1 <= p <= visited for p in missing)
            or len(set(missing)) != len(missing) or not 0 <= visited <= min(total, 16)
            or coverage['raster_pixels'] > 64000000
            or coverage['pages_with_text'] != len(locators)
            or len(locators) + len(missing) != visited):
        return False
    pages = [loc.get('page') for loc in locators]
    if any(type(p) is not int or not 1 <= p <= visited for p in pages):
        return False
    return (len(set(pages)) == len(pages) and not set(pages) & set(missing)
            and (status != 'complete' or (visited == total and total > 0 and not missing)))


def result(content, status, reason, text='', locators=None, coverage=None, confidence=None, engines=None):
    return dict(status=status, reason=reason, text=text, locators=locators or [],
                output_hash=hashlib.sha256(text.encode()).hexdigest(), extractor='local-ocr-1',
                coverage=coverage or {'scope': 'unassessed'}, kind='ocr', confidence=confidence,
                source_hash=hashlib.sha256(content).hexdigest() if content is not None else None,
                engines=engines or {})


def bounded_run(command, *, cwd, timeout, cap=MAX_OUTPUT, isolated_group=False):
    """Drain bounded stdout, discard stderr, kill the entire process group on POSIX."""
    env = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR') if k in os.environ}
    env['OMP_THREAD_LIMIT'] = '1'
    with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          start_new_session=isolated_group) as proc:
        data = bytearray()
        overflow = threading.Event()

        def kill():
            try:
                if os.name == 'posix' and isolated_group:
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass

        def drain():
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                if len(data) + len(chunk) > cap:
                    overflow.set()
                    kill()
                    break
                data.extend(chunk)
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill()
            proc.wait()
            reader.join(1)
            raise TimeoutError('process_timeout')
        reader.join(1)
        if overflow.is_set() or reader.is_alive():
            kill()
            raise ValueError('output_limit')
        if proc.returncode:
            raise ValueError('engine_failed')
        return bytes(data)


def extract_ocr(content: bytes, mime, limit=MAX_BYTES, *, optional_python=None,
                tesseract_path=None, tessdata_dir=None):
    if not isinstance(content, bytes):
        return result(None, 'failed', 'invalid_input')
    if len(content) > MAX_BYTES:
        return result(None, 'failed', 'size_limit')
    fail = lambda status, reason: result(content, status, reason)
    if type(limit) is not int or limit < 1:
        return fail('failed', 'invalid_input')
    if len(content) > min(limit, MAX_BYTES):
        return result(None, 'failed', 'size_limit')
    if not isinstance(mime, str) or mime not in MIMES:
        return fail('unsupported', 'unsupported_mime')
    try:
        executable = os.fspath(optional_python) if optional_python is not None else sys.executable
        if not all(p and os.path.isabs(os.fspath(p)) for p in (executable, tesseract_path, tessdata_dir)):
            return fail('unsupported', 'explicit_paths_required')
        if not os.path.isfile(executable) or not os.path.isfile(tesseract_path):
            return fail('unsupported', 'engine_or_interpreter_missing')
        if not (Path(tessdata_dir) / 'eng.traineddata').is_file():
            return fail('unsupported', 'model_missing')
        with tempfile.TemporaryDirectory(prefix='aegis-ocr-') as folder:
            source = Path(folder) / 'source'
            source.write_bytes(content)
            raw = bounded_run([executable, '-I', str(Path(__file__).with_name('ocr_worker.py')),
                               str(source), mime, os.fspath(tesseract_path), os.fspath(tessdata_dir)],
                              cwd=folder, timeout=TIMEOUT, isolated_group=True)
            value = json.loads(raw)
            if (not isinstance(value, dict) or set(value) != set(fail('', '')) or
                    value['source_hash'] != hashlib.sha256(content).hexdigest() or
                    value['kind'] != 'ocr' or value['status'] not in
                    {'complete', 'partial', 'failed', 'encrypted', 'unsupported'} or
                    not isinstance(value['text'], str) or
                    value['output_hash'] != hashlib.sha256(value['text'].encode()).hexdigest() or
                    not isinstance(value['locators'], list) or
                    not isinstance(value['engines'], dict) or not isinstance(value['coverage'], dict)):
                return fail('failed', 'worker_protocol')
            if any(not isinstance(v, dict) for v in value['locators']):
                return fail('failed', 'worker_protocol')
            if (not isinstance(value['reason'], str) or value['extractor'] != 'local-ocr-1' or
                    not valid_coverage(value, value['locators'], value['text'], value['status']) or
                    (value['status'] in {'failed', 'encrypted', 'unsupported'} and
                     (value['text'] or value['locators'] or value['confidence'] is not None))):
                return fail('failed', 'worker_protocol')
            for conf in [value['confidence']] + [v.get('confidence') for v in value['locators']]:
                if ((value['text'] and conf is None) or
                        (conf is not None and (type(conf) not in (int, float) or
                                               not math.isfinite(conf) or not 0 <= conf <= 100))):
                    return fail('failed', 'worker_protocol')
            previous_end, previous_page = -1, 0
            for loc in value['locators']:
                if (set(loc) != {'page', 'start', 'end', 'confidence'} or
                        type(loc.get('page')) is not int or loc['page'] < 1 or
                        type(loc.get('start')) is not int or type(loc.get('end')) is not int or
                        not 0 <= loc['start'] < loc['end'] <= len(value['text'])):
                    return fail('failed', 'worker_protocol')
                if (loc['page'] <= previous_page or loc['start'] != previous_end + 1 or
                        (previous_end >= 0 and value['text'][previous_end:loc['start']] != '\n')):
                    return fail('failed', 'worker_protocol')
                previous_end, previous_page = loc['end'], loc['page']
            if ((value['text'] and previous_end != len(value['text'])) or
                    (not value['text'] and value['locators'])):
                return fail('failed', 'worker_protocol')
            return value
    except TimeoutError:
        return fail('failed', 'process_timeout')
    except OSError:
        return fail('unsupported', 'worker_unavailable')
    except (ValueError, TypeError, KeyError, RecursionError):
        return fail('failed', 'worker_protocol')

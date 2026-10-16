"""Standalone isolated worker. Never invoked implicitly by text extraction."""
import csv
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys
import warnings

# -I excludes this directory; load only our fixed sibling transport explicitly.
import importlib.util
spec = importlib.util.spec_from_file_location('ocr_transport', Path(__file__).with_name('ocr.py'))
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def fingerprint(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    source, mime, executable, models = sys.argv[1:]
    with open(source, 'rb') as stream:
        content = stream.read(transport.MAX_BYTES + 1)
    if len(content) > transport.MAX_BYTES:
        return transport.result(None, 'failed', 'size_limit')
    manifest = json.loads(Path(__file__).with_name('ocr-runtime.json').read_text())
    engines = {}
    output = lambda status, reason, **kw: transport.result(content, status, reason, engines=engines, **kw)
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
            resource.setrlimit(resource.RLIMIT_FSIZE, (transport.MAX_BYTES, transport.MAX_BYTES))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        except (ImportError, ValueError, OSError):
            return output('unsupported', 'resource_limits_unavailable')
        for package, expected in manifest['packages'].items():
            try:
                actual = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                return output('unsupported', 'package_missing')
            engines[package] = actual
            if actual != expected:
                return output('unsupported', 'package_version_mismatch')
        version = transport.bounded_run([executable, '--version'], cwd=Path(source).parent,
                                        timeout=5, cap=16384).decode().splitlines()
        version = version[0] if version else ''
        engines.update(tesseract=version, binary_sha256=fingerprint(executable),
                       traineddata_sha256=fingerprint(Path(models) / 'eng.traineddata'))
        if version != 'tesseract ' + manifest['tesseract']:
            return output('unsupported', 'engine_version_mismatch')
        if engines['traineddata_sha256'] != manifest['traineddata_sha256']:
            return output('unsupported', 'model_hash_mismatch')
        from PIL import Image
        import pypdfium2 as pdfium
        from pypdf import PdfReader
        engines['pdfium'] = str(pdfium.PDFIUM_INFO)
        Image.MAX_IMAGE_PIXELS = manifest['max_page_pixels']
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        document = None
        image = None
        if mime == 'application/pdf':
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                return output('encrypted', 'encrypted_pdf')
            if len(reader.pages) == 0:
                return output('failed', 'empty_document')
            document = pdfium.PdfDocument(content)
            total = len(document)
        else:
            image = Image.open(io.BytesIO(content))
            if image.format != {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/tiff': 'TIFF'}[mime]:
                return output('failed', 'mime_mismatch')
            total = getattr(image, 'n_frames', 1)
        if total == 0:
            if document is not None:
                document.close()
            return output('failed', 'empty_document')
        text, locators, confidences = '', [], []
        visited, pixels, missing = 0, 0, []
        reason = 'ok'
        for index in range(min(total, manifest['max_pages'])):
            page = bitmap = None
            if document is not None:
                page = document[index]
                width, height = page.get_size()
                count = __import__('math').ceil(width * 2) * __import__('math').ceil(height * 2)
            else:
                image.seek(index)
                count = image.width * image.height
            if count > manifest['max_page_pixels'] or pixels + count > manifest['max_total_pixels']:
                reason = 'pixel_limit'
                if page is not None:
                    page.close()
                break
            pixels += count
            if page is not None:
                bitmap = page.render(scale=manifest['pdf_scale'])
                frame = bitmap.to_pil().convert('RGB')
            else:
                frame = image.convert('RGB')
            target = Path(source).parent / 'page.png'
            try:
                frame.save(target)
            finally:
                frame.close()
                if bitmap is not None:
                    bitmap.close()
                if page is not None:
                    page.close()
            tsv = transport.bounded_run([executable, str(target), 'stdout', '--tessdata-dir', models,
                                        '-l', 'eng', '--psm', '6', 'tsv'], cwd=target.parent,
                                       timeout=15, cap=1048576).decode('utf-8')
            words, scores = [], []
            for row in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
                if row.get('level') == '5' and row.get('text', '').strip():
                    score = float(row['conf'])
                    if not 0 <= score <= 100:
                        raise ValueError('invalid_confidence')
                    words.append(row['text'].strip())
                    scores.append(score)
            part = ' '.join(words)
            if len((text + part).encode()) > 1048576:
                reason = 'text_limit'
                break
            visited += 1
            if part:
                if text:
                    text += '\n'
                start = len(text)
                text += part
                locators.append(dict(page=index + 1, start=start, end=len(text),
                                     confidence=sum(scores) / len(scores)))
                confidences.extend(scores)
            else:
                missing.append(index + 1)
        if document is not None:
            document.close()
        if image is not None:
            image.close()
        if reason == 'ok' and visited < total:
            reason = 'page_limit'
        if reason == 'ok' and missing:
            reason = 'no_text' if not text else 'pages_without_text'
        return output('complete' if reason == 'ok' else 'partial', reason, text=text, locators=locators,
                      confidence=sum(confidences) / len(confidences) if confidences else None,
                      coverage=dict(scope='ocr_pages', total_pages=total, visited_pages=visited,
                                    pages_with_text=len(locators), missing_text_pages=missing,
                                    raster_pixels=pixels))
    except TimeoutError:
        return output('failed', 'process_timeout')
    except Exception:
        return output('failed', 'malformed_or_resource_limit')


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=True, allow_nan=False))

"""Synthetic acceptance only. See README-OCR.md for explicit opt-in."""
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

from .ocr import extract_ocr, bounded_run

PYTHON = os.environ.get('AEGIS_OCR_TEST_PYTHON')
ENGINE = os.environ.get('AEGIS_OCR_TEST_TESSERACT')
MODELS = os.environ.get('AEGIS_OCR_TEST_TESSDATA')


class Core(unittest.TestCase):
    def test_page_spans_and_confidence_protocol(self):
        import copy
        import json
        from unittest.mock import patch
        from .ocr import result
        baseline = result(b'x', 'complete', 'ok', text='ALPHA\nBETA', confidence=90,
                          locators=[dict(page=1, start=0, end=5, confidence=90),
                                    dict(page=2, start=6, end=10, confidence=90)],
                          coverage=dict(scope='ocr_pages', total_pages=2, visited_pages=2,
                                        pages_with_text=2, missing_text_pages=[], raster_pixels=100))
        cases = {}
        for label in ('overlap', 'reversed_pages', 'trailing_text', 'page_confidence',
                      'overall_confidence', 'nan_confidence', 'infinite_confidence',
                      'leading_gap', 'separator', 'no_locators'):
            cases[label] = copy.deepcopy(baseline)
        cases['overlap']['locators'][1].update(start=0, end=5)
        cases['reversed_pages']['locators'][0]['page'] = 2
        cases['reversed_pages']['locators'][1]['page'] = 1
        cases['trailing_text']['locators'][1]['end'] = 9
        cases['page_confidence']['locators'][0]['confidence'] = None
        cases['overall_confidence']['confidence'] = None
        cases['nan_confidence']['confidence'] = float('nan')
        cases['infinite_confidence']['locators'][0]['confidence'] = float('inf')
        cases['leading_gap']['locators'][0]['start'] = 1
        cases['separator']['text'] = 'ALPHA BETA'
        cases['separator']['output_hash'] = hashlib.sha256(b'ALPHA BETA').hexdigest()
        cases['no_locators']['locators'] = []
        cases['no_locators']['coverage'].update(pages_with_text=0, missing_text_pages=[1, 2])
        cases['no_locators']['status'] = 'partial'
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'eng.traineddata').write_bytes(b'synthetic')
            for label, value in [('valid', baseline), *cases.items()]:
                with self.subTest(label=label), patch(
                        'optional.document_processing.ocr.bounded_run', return_value=json.dumps(value).encode()):
                    received = extract_ocr(b'x', 'image/png', optional_python=sys.executable,
                                           tesseract_path=sys.executable, tessdata_dir=folder)
                    if label == 'valid':
                        self.assertEqual(received, baseline)
                    else:
                        self.assertEqual(received['reason'], 'worker_protocol')
                        self.assertEqual(received['text'], '')

    def test_explicit_configuration(self):
        value = extract_ocr(b'synthetic', 'image/png')
        self.assertEqual(value['status'], 'unsupported')
        self.assertEqual(value['source_hash'], hashlib.sha256(b'synthetic').hexdigest())

    def test_input_limits(self):
        self.assertEqual(extract_ocr(b'abc', 'image/png', 2)['reason'], 'size_limit')
        self.assertIsNone(extract_ocr(b'abc', 'image/png', 2)['source_hash'])
        self.assertEqual(extract_ocr(None, 'image/png')['reason'], 'invalid_input')
        self.assertIsNone(extract_ocr(None, 'image/png')['source_hash'])
        self.assertEqual(extract_ocr(b'', 'text/plain')['status'], 'unsupported')
        for mime in ([], {}, None, 42):
            self.assertEqual(extract_ocr(b'', mime)['status'], 'unsupported')

    def test_missing_engine(self):
        self.assertEqual(extract_ocr(b'', 'image/png', tesseract_path='/missing/tesseract',
                                    tessdata_dir='/missing')['status'], 'unsupported')

    def test_process_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(TimeoutError):
                bounded_run([sys.executable, '-I', '-c', 'import time; time.sleep(5)'],
                            cwd=folder, timeout=0.1, isolated_group=True)
            with self.assertRaises(ValueError):
                bounded_run([sys.executable, '-I', '-c', 'print("x" * 200000)'],
                            cwd=folder, timeout=5, cap=1024, isolated_group=True)

    def test_invalid_locator_protocol(self):
        import json
        from unittest.mock import patch
        from .ocr import result
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'eng.traineddata').write_bytes(b'synthetic')
            values = [result(b'x', 'complete', 'ok', locators=[[]]),
                      result(b'x', 'failed', 'bad', text='must not escape'),
                      result(b'x', 'partial', 'bad', coverage={'scope': 'ocr_pages'}),
                      result(b'x', 'partial', 'bad', coverage=dict(scope='ocr_pages', total_pages=1,
                             visited_pages=1, pages_with_text=0, missing_text_pages=[[]], raster_pixels=1))]
            for value in values:
                with patch('optional.document_processing.ocr.bounded_run', return_value=json.dumps(value).encode()):
                    received = extract_ocr(b'x', 'image/png', optional_python=sys.executable,
                                           tesseract_path=sys.executable, tessdata_dir=folder)
                self.assertEqual(received['reason'], 'worker_protocol')


@unittest.skipUnless(PYTHON and ENGINE and MODELS, 'explicit OCR test configuration required')
class RealOCR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.metadata
        import json
        manifest = json.loads(Path(__file__).with_name('ocr-runtime.json').read_text())
        for package, version in manifest['packages'].items():
            try:
                actual = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                raise unittest.SkipTest('exact optional packages required')
            if actual != version:
                raise unittest.SkipTest('exact optional packages required')

    def call(self, content, mime='image/png', **kw):
        options = dict(optional_python=PYTHON, tesseract_path=ENGINE, tessdata_dir=MODELS)
        options.update(kw)
        return extract_ocr(content, mime, **options)

    def fixture(self, word='ALPHA'):
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('RGB', (1000, 300), 'white')
        if word:
            # Pillow's bundled default font; no platform font lookup.
            ImageDraw.Draw(image).text((60, 80), word, fill='black', font=ImageFont.load_default(size=100))
        return image

    def encoded(self, image, fmt='PNG'):
        stream = io.BytesIO()
        image.save(stream, format=fmt)
        return stream.getvalue()

    def test_real_images(self):
        for mime, fmt in [('image/png', 'PNG'), ('image/jpeg', 'JPEG'), ('image/tiff', 'TIFF')]:
            data = self.encoded(self.fixture(), fmt)
            value = self.call(data, mime)
            self.assertEqual(value['status'], 'complete', value)
            self.assertIn('ALPHA', value['text'])
            self.assertEqual(value['source_hash'], hashlib.sha256(data).hexdigest())
            self.assertEqual(value['locators'][0]['page'], 1)
            self.assertTrue(0 <= value['confidence'] <= 100)

    def test_image_only_pdf(self):
        stream = io.BytesIO()
        self.fixture('ALPHA').save(stream, format='PDF', save_all=True,
                                   append_images=[self.fixture('BETA')])
        from pypdf import PdfReader
        self.assertTrue(all(not p.extract_text() for p in PdfReader(io.BytesIO(stream.getvalue())).pages))
        value = self.call(stream.getvalue(), 'application/pdf')
        self.assertEqual(value['status'], 'complete', value)
        self.assertIn('ALPHA', value['text'])
        self.assertIn('BETA', value['text'])
        self.assertEqual([p['page'] for p in value['locators']], [1, 2])
        self.assertEqual(value['coverage']['visited_pages'], 2)

    def test_blank_and_malformed(self):
        value = self.call(self.encoded(self.fixture('')))
        self.assertEqual((value['status'], value['reason']), ('partial', 'no_text'))
        self.assertIsNone(value['confidence'])
        for mime in ('image/png', 'application/pdf'):
            self.assertEqual(self.call(b'bad synthetic', mime)['status'], 'failed')

    def test_encrypted(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('synthetic-password')
        stream = io.BytesIO()
        writer.write(stream)
        self.assertEqual(self.call(stream.getvalue(), 'application/pdf')['status'], 'encrypted')

    def test_empty_pdf(self):
        from pypdf import PdfWriter
        stream = io.BytesIO()
        PdfWriter().write(stream)
        value = self.call(stream.getvalue(), 'application/pdf')
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['reason'], 'empty_document')

    def test_missing_and_mismatched_model(self):
        data = self.encoded(self.fixture())
        self.assertEqual(self.call(data, optional_python='/missing/python')['status'], 'unsupported')
        self.assertEqual(self.call(data, tesseract_path=PYTHON)['reason'], 'engine_version_mismatch')
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.call(data, tessdata_dir=folder)['reason'], 'model_missing')
            Path(folder, 'eng.traineddata').write_bytes(b'synthetic wrong model')
            self.assertEqual(self.call(data, tessdata_dir=folder)['reason'], 'model_hash_mismatch')

    def test_pixel_and_page_limits(self):
        from PIL import Image
        huge = Image.new('1', (5000, 4000), 1)
        self.assertIn(self.call(self.encoded(huge))['reason'],
                      ('pixel_limit', 'malformed_or_resource_limit'))
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _ in range(17):
            writer.add_blank_page(width=30, height=30)
        stream = io.BytesIO()
        writer.write(stream)
        value = self.call(stream.getvalue(), 'application/pdf')
        self.assertEqual(value['reason'], 'page_limit', value)
        self.assertEqual(value['coverage']['visited_pages'], 16)


if __name__ == '__main__':
    unittest.main()

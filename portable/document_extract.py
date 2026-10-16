"""Bounded native text derivatives; offsets address output text."""
import hashlib
import json
import re
from html.parser import HTMLParser

MAX_BYTES = 32 * 1024 * 1024
MAX_CHARS = 8 * 1024 * 1024
MAX_PARAGRAPHS = 100000
EXTRACTOR = 'builtin-2'


def outcome(status, reason=None, text='', locators=None, extractor=EXTRACTOR):
    """Keep failure diagnostics fixed and free of source excerpts."""
    return {'status': status, 'reason': reason, 'text': text,
            'locators': locators or [], 'extractor': extractor,
            'output_hash': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'locator_space': 'derivative_text', 'offset_unit': 'unicode_codepoint'}


class _LimitError(ValueError):
    pass


class _VisibleHTML(HTMLParser):
    BLOCKS = frozenset(('p', 'div', 'section', 'article', 'h1', 'h2', 'h3',
                        'h4', 'h5', 'h6', 'br', 'li', 'tr', 'td', 'th', 'hr'))
    SKIP = frozenset(('head', 'script', 'style', 'template', 'noscript'))
    VOID = frozenset(('area', 'base', 'br', 'col', 'embed', 'hr', 'img',
                      'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.hidden = 0
        self.parts = []
        self.characters = 0
        self.tokens = 0

    def append(self, text):
        self.characters += len(text)
        self.tokens += 1
        if self.characters > MAX_CHARS or self.tokens > 200000:
            raise _LimitError('output_limit')
        self.parts.append(text)

    def parse_html_declaration(self, index):
        # Newer HTMLParser versions turn unknown marked sections into bogus
        # comments. Keep the original validated marked-section contract, only
        # at declaration boundaries (never inside comment or script contents).
        if self.rawdata.startswith('<![', index):
            try:
                return self.parse_marked_section(index)
            except NotImplementedError:
                # Python 3.9 reports an unknown marked section through error().
                raise ValueError('malformed_input') from None
        return super().parse_html_declaration(index)

    def handle_starttag(self, tag, attrs):
        # HTML permits omitted end tags. Close their scope before counting depth.
        names = [name for name, hidden in self.stack]
        if 'head' in names and tag not in self.SKIP | {'meta', 'link', 'base', 'title'}:
            self.handle_endtag('head')
        scopes = {'li': ({'li'}, {'ul', 'ol'}), 'p': ({'p'}, set()),
                  'dt': ({'dt', 'dd'}, {'dl'}), 'dd': ({'dt', 'dd'}, {'dl'}),
                  'tr': ({'tr'}, {'table', 'tbody', 'thead', 'tfoot'}),
                  'td': ({'td', 'th'}, {'tr', 'table'}), 'th': ({'td', 'th'}, {'tr', 'table'}),
                  'option': ({'option'}, {'select', 'datalist'})}
        if tag in scopes:
            targets, barriers = scopes[tag]
            for name, hidden in reversed(self.stack):
                if name in barriers:
                    break
                if name in targets:
                    self.handle_endtag(name)
                    break
        if tag in self.BLOCKS - {'br', 'td', 'th', 'tr'} and any(name == 'p' for name, _ in self.stack):
            self.handle_endtag('p')
        if tag not in self.VOID:
            suppressed = tag in self.SKIP or any(name == 'hidden' for name, value in attrs)
            self.stack.append((tag, suppressed))
            if suppressed:
                self.hidden += 1
            if len(self.stack) > 512:
                raise _LimitError('structure_limit')
        if not self.hidden and tag in self.BLOCKS:
            self.append('\n')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        names = [name for name, hidden in self.stack]
        if tag in names:
            index = len(names) - 1 - names[::-1].index(tag)
            for removed, suppressed in self.stack[index:]:
                self.hidden -= int(suppressed)
            del self.stack[index:]
        if not self.hidden and tag in self.BLOCKS:
            self.append('\n')

    def handle_data(self, data):
        # Non-whitespace body text also implicitly ends head. Title/script/style
        # data stays suppressed until its own closing tag.
        if data.strip() and self.stack and self.stack[-1][0] == 'head':
            self.handle_endtag('head')
        if not self.hidden:
            self.append(data)

    def text(self):
        return '\n'.join(line for part in ''.join(self.parts).splitlines()
                         if (line := re.sub(r'\s+', ' ', part).strip()))


def _locators(text):
    locators = []
    position = 0
    for index, line in enumerate(text.splitlines(keepends=True), 1):
        if index > MAX_PARAGRAPHS:
            raise _LimitError('structure_limit')
        body = line.rstrip('\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029')
        locators.append({'paragraph': index, 'start': position, 'end': position + len(body)})
        position += len(line)
    return locators


def extract(content, mime='text/plain', limit=MAX_BYTES, *, optional=False,
            optional_python=None):
    """Derive text locally; binary parsers require explicit optional opt-in."""
    if not isinstance(content, bytes):
        return outcome('failed', 'invalid_content')
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        return outcome('failed', 'invalid_limit')
    if len(content) > min(limit, MAX_BYTES):
        return outcome('failed', 'size_limit')
    if not isinstance(mime, str):
        return outcome('unsupported', 'no_builtin_extractor')
    mime = mime.split(';', 1)[0].strip().lower()
    if not (mime.startswith('text/') or mime == 'application/json'):
        if optional:
            from optional.document_processing import extract as extract_optional
            result = extract_optional(content, mime, limit, optional_python=optional_python)
            result.update(locator_space='derivative_text', offset_unit='unicode_codepoint')
            return result
        return outcome('unsupported', 'no_builtin_extractor')
    status, reason = 'complete', None
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('utf-8', 'replace')
        status, reason = 'partial', 'invalid_encoding'
    if len(text) > MAX_CHARS:
        return outcome('failed', 'output_limit')
    try:
        if mime == 'text/html':
            parser = _VisibleHTML()
            parser.feed(text)
            parser.close()
            text = parser.text()
        locators = _locators(text)
    except _LimitError as error:
        return outcome('failed', str(error))
    except (ValueError, RecursionError, AssertionError):
        return outcome('failed', 'malformed_input')
    return outcome(status, reason, text, locators)


def extract_ocr(content, mime, limit=MAX_BYTES, *, optional_python=None,
                tesseract_path=None, tessdata_dir=None):
    """Create a separately identified OCR derivative using explicit local tools.

    OCR never replaces native extraction. Confidence describes the engine output,
    not source truth; downstream storage must retain kind='ocr' and provenance.
    """
    from optional.document_processing.ocr import extract_ocr as run_ocr
    if isinstance(mime, str):
        mime = mime.split(';', 1)[0].strip().lower()
    result = run_ocr(content, mime, limit, optional_python=optional_python,
                     tesseract_path=tesseract_path, tessdata_dir=tessdata_dir)
    result = dict(result, locator_space='derivative_text', offset_unit='unicode_codepoint')
    identity = [result['kind'], result['source_hash'], result['output_hash'],
                result['extractor'], result['engines']]
    result['derivative_id'] = 'ocr:' + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result

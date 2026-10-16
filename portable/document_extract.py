"""Bounded native text derivatives; offsets address output text."""
import hashlib
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

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)
            if tag in self.SKIP:
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
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            for removed in self.stack[index:]:
                if removed in self.SKIP:
                    self.hidden -= 1
            del self.stack[index:]
        if not self.hidden and tag in self.BLOCKS:
            self.append('\n')

    def handle_data(self, data):
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


def extract(content, mime='text/plain', limit=MAX_BYTES):
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
    except (ValueError, RecursionError):
        return outcome('failed', 'malformed_input')
    return outcome(status, reason, text, locators)

"""Static HTML/CSS discovery. No execution, fetching or third-party dependencies."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
import re

VERSION = '1.0'
MAX_TEXT = 8 * 1024 * 1024
MAX_REFERENCES = 20000


def resolve(raw, base):
    raw = str(raw or '').strip()
    if not raw or raw.startswith('#'):
        return None
    try:
        url = urlsplit(urljoin(base, raw))
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            return None
        return urlunsplit((url.scheme, url.netloc, url.path or '/', url.query, ''))
    except ValueError:
        return None


def srcset(value):
    candidates = []
    position = 0
    while position < len(value):
        while position < len(value) and (value[position].isspace() or value[position] == ','):
            position += 1
        start = position
        data_url = value[position:position + 5].lower() == 'data:'
        while position < len(value) and not value[position].isspace() and (data_url or value[position] != ','):
            position += 1
        if position > start:
            candidates.append(value[start:position].rstrip(','))
        while position < len(value) and value[position] != ',':
            position += 1
    return candidates


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.base = None
        self.styles = []
        self.in_style = False
        self.dynamic = False

    def handle_starttag(self, tag, attrs):
        a = {}
        for key, value in attrs:
            a.setdefault(key, value)
        if tag == 'base' and self.base is None and a.get('href'):
            self.base = a['href']
        if tag in ('a', 'area', 'link') and a.get('href'):
            self.links.append((a['href'], 'page' if tag in ('a', 'area') else 'asset'))
        if tag in ('img', 'script', 'iframe', 'source', 'video', 'audio', 'input', 'embed', 'track') and a.get('src'):
            self.links.append((a['src'], 'page' if tag == 'iframe' else 'asset'))
        for attr in ('poster', 'data' if tag == 'object' else ''):
            if attr and a.get(attr):
                self.links.append((a[attr], 'asset'))
        if tag in ('img', 'source') and a.get('srcset'):
            self.links.extend((s, 'asset') for s in srcset(a['srcset']))
        if a.get('style'):
            self.styles.append(a['style'])
        if tag == 'style':
            self.in_style = True
        if tag == 'script':
            self.dynamic = True

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.styles.append(data)


def css_urls(text):
    """Scan comments, strings and URL/import tokens without treating strings as code."""
    string = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    tokens = re.compile(r'/\*[\s\S]*?(?:\*/|$)|url\(\s*(' + string + r'|(?:\\.|[^)\\])*)\s*\)|@import\s+(' + string + r')|' + string, re.I)
    out = []
    for m in tokens.finditer(text):
        raw = m.group(1) if m.group(1) is not None else m.group(2)
        if raw is None:
            continue
        raw = raw.strip()
        if raw[:1] in ('"', "'"):
            raw = raw[1:-1]
        def unescape(match):
            token = match.group(1)
            if re.fullmatch(r'[0-9a-fA-F]{1,6}\s?', token):
                number = int(token.strip(), 16)
                return chr(number) if 0 < number <= 0x10ffff else '\ufffd'
            return '' if token in ('\n', '\r') else token
        out.append(re.sub(r'\\([0-9a-fA-F]{1,6}\s?|[\s\S])', unescape, raw))
    return out


def discover(text, mime, url):
    """Return resolved references and explicit static-analysis limitations."""
    result = {'resources': [], 'unsupported': []}
    if len(text) > MAX_TEXT:
        result['unsupported'].append('discovery_text_limit')
        return result
    mime = mime.split(';')[0].strip().lower()
    if mime not in ('text/html', 'application/xhtml+xml', 'text/css'):
        return result
    links = []
    base = url
    if mime != 'text/css':
        parser = _HTML()
        parser.feed(text)
        base = resolve(parser.base, url) or url
        links = parser.links
        for style in parser.styles:
            links.extend((raw, 'asset') for raw in css_urls(style))
        if parser.dynamic:
            result['unsupported'].append('script_generated_content_not_evaluated')
    if mime == 'text/css':
        links = [(raw, 'asset') for raw in css_urls(text)]
    seen = set()
    for raw, kind in links:
        target = resolve(raw, base)
        if target and target not in seen:
            if len(seen) >= MAX_REFERENCES:
                result['unsupported'].append('discovery_reference_limit')
                break
            seen.add(target)
            result['resources'].append({'url': target, 'kind': kind})
        elif target is None and raw and not raw.strip().startswith(('#', 'data:')):
            result['unsupported'].append('unsupported_reference_scheme')
    result['unsupported'] = sorted(set(result['unsupported']))
    return result

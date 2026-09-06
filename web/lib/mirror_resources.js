/* Static discovery only: no source script execution or network access. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.MirrorResources = factory();
}(typeof self !== 'undefined' ? self : this, function() {
  const VERSION = '1.0', MAX_TEXT = 8 * 1024 * 1024, MAX_REFERENCES = 20000;
  function resolve(raw, base) {
    raw = String(raw || '').trim();
    if (!raw || raw.startsWith('#')) return null;
    try {
      const u = new URL(raw, base);
      if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password) return null;
      u.hash = ''; return u.href;
    } catch (_) { return null; }
  }
  function entity(s) {
    return s.replace(/&(#x[\da-f]+|#\d+|amp|quot|apos|lt|gt);/gi, (m, x) => {
      if (x[0] !== '#') return ({amp:'&',quot:'"',apos:"'",lt:'<',gt:'>'})[x.toLowerCase()];
      const n = parseInt(x.slice(x[1].toLowerCase() === 'x' ? 2 : 1), x[1].toLowerCase() === 'x' ? 16 : 10);
      return n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : '\ufffd';
    });
  }
  function html(text) {
    const links = [], styles = []; let base = null, dynamic = false;
    // Tokenise tags with quoted > support and consume raw script bodies as one token.
    const token = /<!--[\s\S]*?(?:-->|$)|<(script|style)\b((?:"[^"]*"|'[^']*'|[^'">])*)>([\s\S]*?)(?:<\/\1\s*>|$)|<([a-z][\w:-]*)\b((?:"[^"]*"|'[^']*'|[^'">])*)>/gi;
    let m;
    while ((m = token.exec(text))) {
      const tag = (m[1] || m[4] || '').toLowerCase();
      if (!tag) continue;
      const a = {}; const attrs = m[2] || m[5] || '';
      for (const x of attrs.matchAll(/([^\s=/>]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) {
        const key = x[1].toLowerCase(); if (!(key in a)) a[key] = entity(x[2] ?? x[3] ?? x[4]);
      }
      if (tag === 'base' && base === null && a.href) base = a.href;
      if (['a','area','link'].includes(tag) && a.href) links.push([a.href, tag === 'link' ? 'asset' : 'page']);
      if (['img','script','iframe','source','video','audio','input','embed','track'].includes(tag) && a.src) links.push([a.src, tag === 'iframe' ? 'page' : 'asset']);
      if (a.poster) links.push([a.poster, 'asset']);
      if (tag === 'object' && a.data) links.push([a.data, 'asset']);
      if (['img','source'].includes(tag) && a.srcset) {
        for (const x of a.srcset.matchAll(/(?:^|,)\s*(\S+)(?:\s+[^,]*)?/g)) links.push([x[1].replace(/,+$/, ''), 'asset']);
      }
      if (a.style) styles.push(a.style);
      if (tag === 'style') styles.push(m[3] || '');
      if (tag === 'script') dynamic = true;
    }
    return {links, styles, base, dynamic};
  }

  function cssUrls(text) {
    const out = [];
    const tokens = /\/\*[\s\S]*?(?:\*\/|$)|url\(\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(?:\\.|[^)\\])*)\s*\)|@import\s+("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/gi;
    for (const m of text.matchAll(tokens)) {
      let raw = m[1] ?? m[2]; if (raw === undefined) continue;
      raw = raw.trim(); if (/^["']/.test(raw)) raw = raw.slice(1, -1);
      out.push(raw.replace(/\\([\da-f]{1,6}\s?|[\s\S])/gi, (_, x) => {
        if (/^[\da-f]{1,6}\s?$/i.test(x)) { const n = parseInt(x.trim(), 16); return n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : '\ufffd'; }
        return /[\r\n]/.test(x) ? '' : x;
      }));
    }
    return out;
  }
  function discover(text, mime, url) {
    const result = {resources:[], unsupported:[]};
    if (text.length > MAX_TEXT) { result.unsupported.push('discovery_text_limit'); return result; }
    mime = mime.split(';')[0].trim().toLowerCase();
    if (!['text/html','application/xhtml+xml','text/css'].includes(mime)) return result;
    let links = [], base = url;
    if (mime !== 'text/css') {
      const parsed = html(text); base = resolve(parsed.base, url) || url; links = parsed.links;
      for (const style of parsed.styles) links.push(...cssUrls(style).map(raw => [raw, 'asset']));
      if (parsed.dynamic) result.unsupported.push('script_generated_content_not_evaluated');
    }
    if (mime === 'text/css') links = cssUrls(text).map(raw => [raw, 'asset']);
    const seen = new Set();
    for (const [raw, kind] of links) {
      const target = resolve(raw, base);
      if (target && !seen.has(target)) {
        if (seen.size >= MAX_REFERENCES) { result.unsupported.push('discovery_reference_limit'); break; }
        seen.add(target); result.resources.push({url:target, kind});
      } else if (!target && raw && !/^(#|data:)/.test(raw.trim())) result.unsupported.push('unsupported_reference_scheme');
    }
    result.unsupported = [...new Set(result.unsupported)].sort(); return result;
  }
  return {VERSION, discover, resolve};
}));

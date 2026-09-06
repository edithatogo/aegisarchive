/* Archive-local navigation helpers. Never falls back to the live network. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.OfflineNavigation = factory();
}(typeof self !== 'undefined' ? self : this, function() {
  function canonical(raw, base) {
    try {
      const u = new URL(raw, base); u.hash = '';
      if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password) return null;
      return u.href;
    } catch (_) { return null; }
  }
  function resolve(raw, pageUrl, reader) {
    let parsed; try { parsed = new URL(raw, pageUrl); } catch (_) { return {state:'invalid', target:null}; }
    const fragment = parsed.hash || ''; const target = canonical(raw, pageUrl);
    if (!target) return {state:'invalid', target:null};
    const record = reader && reader.getRecord(target);
    if (!record) return {state:'missing', target};
    let final = target; let current = record; const seen = new Set();
    while (current && current.status >= 300 && current.status < 400 && current.headers && current.headers.location && !seen.has(final)) {
      seen.add(final); final = canonical(current.headers.location, final); current = final && reader.getRecord(final);
    }
    return current ? {state:'captured', target: final + fragment, lookup: final, record: current} : {state:'missing', target: final + fragment, lookup: final};
  }
  function navigationMessage(target, nonce) { return {type:'aegis-archive-navigate', target, nonce}; }
  function acceptNavigation(event, source, nonce) {
    return !!event && event.source === source && !!event.data &&
      event.data.type === 'aegis-archive-navigate' && event.data.nonce === nonce &&
      typeof event.data.target === 'string';
  }
  return {canonical, resolve, navigationMessage, acceptNavigation};
}));

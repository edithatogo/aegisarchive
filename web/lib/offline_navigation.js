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
    const target = canonical(raw, pageUrl);
    if (!target) return {state:'invalid', target:null};
    const record = reader && reader.getRecord(target);
    if (!record) return {state:'missing', target};
    return {state:'captured', target, record};
  }
  function navigationMessage(target, nonce) { return {type:'aegis-archive-navigate', target, nonce}; }
  function acceptNavigation(event, source, nonce) {
    return !!event && event.source === source && !!event.data &&
      event.data.type === 'aegis-archive-navigate' && event.data.nonce === nonce &&
      typeof event.data.target === 'string';
  }
  return {canonical, resolve, navigationMessage, acceptNavigation};
}));

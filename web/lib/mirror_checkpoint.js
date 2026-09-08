/* Portable validation helpers for browser checkpoint metadata. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.MirrorCheckpoint = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  const VERSION = 1;
  function validate(state, profileId, profileHash) {
    if (!state || state.version !== VERSION || state.profile_id !== profileId || state.profile_sha256 !== profileHash) return false;
    if (!Array.isArray(state.queue) || !Array.isArray(state.visited) || !Array.isArray(state.segments)) return false;
    return state.segments.every(s => s && Number.isInteger(s.sequence) && s.sequence >= 0 &&
      typeof s.name === 'string' && /^segment-\d{8}\.bin$/.test(s.name) && Number.isInteger(s.bytes) && s.bytes >= 0 &&
      typeof s.sha256 === 'string' && /^[a-f0-9]{64}$/.test(s.sha256));
  }
  function lineage(segments) {
    const seen = new Set();
    return (segments || []).slice().sort((a, b) => a.sequence - b.sequence).map(s => {
      const key = s.sha256 + ':' + s.bytes;
      const revisit = seen.has(key); seen.add(key);
      return Object.assign({}, s, { revisit });
    });
  }
  return { VERSION, validate, lineage };
}));

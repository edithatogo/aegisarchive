/* Explicit capture/replay mode contract. No mode changes original archive bytes. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.PreservationModes = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  const MODES = Object.freeze({
    preservation: Object.freeze({ original: true, offline: false, rendered: false }),
    offline_reading: Object.freeze({ original: true, offline: true, rendered: false }),
    rendered_optional: Object.freeze({ original: true, offline: true, rendered: true })
  });
  function describe(mode) {
    const value = MODES[mode];
    if (!value) throw new Error('unknown preservation mode');
    return { mode, ...value, originalsAuthoritative: true, backendBehaviour: 'unsupported' };
  }
  return { MODES, describe };
}));

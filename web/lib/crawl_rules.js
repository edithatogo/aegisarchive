/** Bounded, deterministic rule configuration. No fetching or regex matchers. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CrawlRules = factory();
}(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  const actions = ['discover', 'download', 'traverse'];
  const textFields = ['url_prefix', 'path_prefix', 'host', 'mime', 'kind'];
  const numberFields = ['min_depth', 'max_depth', 'min_bytes', 'max_bytes'];
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const keys = (value, allowed) => Object.keys(value).every(key => allowed.includes(key));
  function validateRules(config) {
    if (!object(config) || !keys(config,['version','rules']) || config.version !== 1 ||
        !Array.isArray(config.rules) || config.rules.length > 100) throw Error('Invalid rule configuration');
    const ids = new Set();
    for (const rule of config.rules) {
      if (!object(rule) || !keys(rule,['id','match','decision']) ||
          typeof rule.id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(rule.id) || ids.has(rule.id)) throw Error('Invalid rule id');
      ids.add(rule.id);
      const match = rule.match, decision = rule.decision;
      if (!object(match) || !keys(match,[...textFields,...numberFields])) throw Error('Unknown matcher');
      if (!object(decision) || !Object.keys(decision).length || !keys(decision,actions) ||
          Object.values(decision).some(value=>typeof value !== 'boolean')) throw Error('Invalid decision');
      for (const [key,value] of Object.entries(match)) {
        if (numberFields.includes(key)) {
          if (!Number.isSafeInteger(value) || value < 0) throw Error('Invalid numeric bound');
        } else if (typeof value !== 'string' || !value || Array.from(value).length > 2048 || /[\x00-\x1f]/.test(value)) throw Error('Invalid matcher text');
      }
      for (const unit of ['depth','bytes']) {
        if ((match['min_'+unit] ?? 0) > (match['max_'+unit] ?? Number.MAX_SAFE_INTEGER)) throw Error('Reversed interval');
      }
      if ('kind' in match && !['page','asset','sitemap'].includes(match.kind)) throw Error('Invalid kind');
      if ('host' in match && !/^[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(match.host)) throw Error('Invalid host');
      if ('path_prefix' in match && !match.path_prefix.startsWith('/')) throw Error('Invalid path prefix');
      if ('url_prefix' in match) {
        const url = new URL(match.url_prefix);
        if (!['http:','https:'].includes(url.protocol) || !url.hostname || url.username || url.password) throw Error('Invalid URL prefix');
      }
    }
    return JSON.parse(JSON.stringify(config));
  }
  return {validateRules};
}));

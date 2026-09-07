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
  function evaluateRules(config, resource, inScope) {
    config = validateRules(config);
    if (typeof inScope !== 'boolean' || !object(resource) || typeof resource.url !== 'string' ||
        Array.from(resource.url).length > 8192 || /[\x00-\x1f]/.test(resource.url)) throw Error('Invalid resource');
    const url = new URL(resource.url);
    if (!['http:','https:'].includes(url.protocol) || !url.hostname || url.username || url.password ||
        !['page','asset','sitemap'].includes(resource.kind)) throw Error('Invalid resource URL or kind');
    for (const key of ['depth','bytes']) {
      if (resource[key] != null && (!Number.isSafeInteger(resource[key]) || resource[key]<0)) throw Error('Invalid resource count');
    }
    if (resource.mime != null && (typeof resource.mime !== 'string' || Array.from(resource.mime).length>2048)) throw Error('Invalid MIME');
    const result = {discover:inScope,download:inScope,traverse:inScope,rule_id:null,state:inScope?'decided':'out_of_scope',missing:[]};
    if (!inScope) return result;
    for (const rule of config.rules) {
      const missing = new Set();let mismatch = false;
      for (const [key,expected] of Object.entries(rule.match)) {
        if (numberFields.includes(key)) {
          const [direction,field]=key.split('_'),value=resource[field];
          if (value == null) missing.add(field);
          else if ((direction==='min' && value<expected) || (direction==='max' && value>expected)) mismatch=true;
        } else if (key==='mime') {
          if (resource.mime == null) missing.add('mime');
          else if (resource.mime.split(';')[0].trim().toLowerCase()!==expected.toLowerCase()) mismatch=true;
        } else {
          const value={url_prefix:resource.url,path_prefix:url.pathname || '/',host:url.hostname.toLowerCase(),kind:resource.kind}[key];
          if (!(key.endsWith('_prefix') ? value.startsWith(expected) : value===expected)) mismatch=true;
        }
      }
      if (mismatch) continue;
      result.rule_id=rule.id;
      if (missing.size) return {...result,download:false,traverse:false,state:'needs_metadata',missing:[...missing].sort()};
      Object.assign(result,rule.decision);
      result.download=result.discover && result.download;
      result.traverse=result.download && result.traverse;
      return result;
    }
    return result;
  }
  return {validateRules, evaluateRules};
}));

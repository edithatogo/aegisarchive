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
  function scopeHosts(allowedHosts, aliases = {}) {
    const valid = value => typeof value==='string' && value.length<=253 && /^[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(value);
    if (!Array.isArray(allowedHosts) || allowedHosts.length>32 || !allowedHosts.every(valid) ||
        !object(aliases) || Object.keys(aliases).length>16) throw Error('Invalid host scope');
    const hosts=new Set(allowedHosts);
    for (const [primary,extra] of Object.entries(aliases)) {
      if (!allowedHosts.includes(primary) || !Array.isArray(extra) || extra.length>16 || !extra.every(valid)) throw Error('Invalid explicit alias');
      extra.forEach(host=>hosts.add(host));
    }
    if (hosts.size>32) throw Error('Too many hosts');
    return [...hosts].sort();
  }
  function sitemapLocations(text) {
    // Small strict XML subset also usable in the dependency-free test runtime.
    if (/[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]/.test(text)) throw Error('Invalid XML character');
    if (/<!DOCTYPE|<!ENTITY|<\/?[A-Za-z_][\w.-]*:/i.test(text)) throw Error('Unsupported sitemap XML');
    const structure={urlset:['url'],sitemapindex:['sitemap'],url:['loc','lastmod','changefreq','priority'],sitemap:['loc','lastmod'],loc:[],lastmod:[],changefreq:[],priority:[]};
    const stack=[],locations=[];let root=null,position=0,nodes=0,loc='';
    const decode=value=>value.replace(/&([^;]+);/g,(_,entity)=>{
      const entities={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"};
      if (Object.hasOwn(entities,entity)) return entities[entity];
      if (!/^#(?:x[0-9a-fA-F]+|[0-9]+)$/.test(entity)) throw Error('Invalid entity');
      const n=entity[1]==='x'?parseInt(entity.slice(2),16):Number(entity.slice(1));
      if (!Number.isSafeInteger(n) || (n<0x20 && ![9,10,13].includes(n)) || n===0xfffe || n===0xffff || n>0x10ffff || (n>=0xd800 && n<=0xdfff)) throw Error('Invalid entity');
      return String.fromCodePoint(n);
    });
    while (position<text.length) {
      if (text.startsWith('<!--',position)) {
        const end=text.indexOf('-->',position+4);if(end<0)throw Error('Malformed comment');position=end+3;continue;
      }
      if (text.startsWith('<?xml',position) && root===null) {
        const end=text.indexOf('?>',position+5);if(end<0)throw Error('Malformed declaration');position=end+2;continue;
      }
      if (text[position]!=='<') {
        let end=text.indexOf('<',position);if(end<0)end=text.length;
        const raw=text.slice(position,end);
        if (raw.replace(/&(?:amp|lt|gt|quot|apos|#x[0-9a-fA-F]+|#[0-9]+);/g,'').includes('&')) throw Error('Malformed entity');
        const value=decode(raw);
        if (stack.at(-1)==='loc') loc+=value;
        else if (!stack.length && value.trim()) throw Error('Text outside root');
        position=end;continue;
      }
      const end=text.indexOf('>',position);if(end<0)throw Error('Malformed tag');
      const token=text.slice(position,end+1);position=end+1;
      const closing=token.match(/^<\/([a-z]+)\s*>$/);
      if (closing) {
        if (stack.pop()!==closing[1]) throw Error('Mismatched tag');
        if (closing[1]==='loc' && loc.trim()) locations.push(loc.trim());
        if (locations.length>1000) throw Error('Sitemap location limit');
        continue;
      }
      const opening=token.match(/^<([a-z]+)((?:\s+[\w:.-]+\s*=\s*(?:"[^"<>]*"|'[^'<>]*'))*)\s*(\/?)>$/);
      if (!opening || !Object.hasOwn(structure,opening[1]) || ++nodes>6001) throw Error('Unsupported sitemap structure');
      const name=opening[1];
      if (opening[2].trim() && !/^\s+xmlns\s*=\s*(?:"[^"<>]*"|'[^'<>]*')\s*$/.test(opening[2])) throw Error('Unsupported attributes');
      const namespace=opening[2].match(/\sxmlns\s*=\s*["']([^"']*)["']/);
      if (namespace && namespace[1]!=='http://www.sitemaps.org/schemas/sitemap/0.9') throw Error('Unsupported namespace');
      if (!stack.length) {
        if (root || !['urlset','sitemapindex'].includes(name)) throw Error('Invalid root');root=name;
      } else if (!structure[stack.at(-1)].includes(name)) throw Error('Unsupported nesting');
      if (name==='loc') loc='';
      if (!opening[3]) stack.push(name);
    }
    if (stack.length || !root) throw Error('Unclosed sitemap');
    return {root,locations};
  }
  function discoverSitemap(text, sourceUrl, allowedHosts, visited=[]) {
    const hosts=scopeHosts(allowedHosts);
    if (typeof text!=='string' || new TextEncoder().encode(text).length>262144) throw Error('Sitemap byte limit');
    const identity=value=>{
      const url=new URL(value);
      if(!['http:','https:'].includes(url.protocol) || !url.hostname || url.username || url.password) throw Error('Invalid sitemap identity');
      url.hash='';return url.href;
    };
    const seen=new Set(visited.map(identity)),result={pages:[],sitemaps:[],excluded:[]};
    const source=new URL(sourceUrl);
    if (!['http:','https:'].includes(source.protocol) || !hosts.includes(source.hostname) || source.username || source.password) throw Error('Source outside scope');
    sourceUrl=identity(sourceUrl);
    if(seen.has(sourceUrl))return result;
    seen.add(sourceUrl);
    const {root,locations}=sitemapLocations(text);
    for(const location of locations) {
      if(Array.from(location).length>8192)throw Error('Sitemap URL limit');
      const url=new URL(location,sourceUrl);url.hash='';const value=url.href;
      if(!['http:','https:'].includes(url.protocol) || !hosts.includes(url.hostname) || url.username || url.password) {
        if(!result.excluded.includes(value))result.excluded.push(value);
      } else if(!seen.has(value)) {result[root==='sitemapindex'?'sitemaps':'pages'].push(value);seen.add(value);}
    }
    return result;
  }
  return {validateRules, evaluateRules, scopeHosts, discoverSitemap};
}));

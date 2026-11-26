'use strict';
importScripts('warc_reader.js', 'offline_navigation.js');

const scope = new URL(self.registration.scope);
const archiveRead = new AbortController();
let archive;
let stopped = false;

const local = name => new URL(name, scope);
const responseHeaders = {
  'Cache-Control': 'no-store',
  'X-Content-Type-Options': 'nosniff',
  'Cross-Origin-Resource-Policy': 'same-origin',
  'Content-Security-Policy': "sandbox; default-src 'none'",
};
const absent = () => new Response('Missing archived resource', {status:404, headers:responseHeaders});

function json(value) {
  return Response.json(value, {headers:responseHeaders});
}

function assetUrl(url) {
  const asset = local('asset');
  asset.searchParams.set('url', url);
  return asset.href;
}

function usable(record) {
  return record && !record.unresolved && record.status >= 200 && record.status < 300;
}

function html(record) {
  return usable(record) && ['text/html', 'application/xhtml+xml'].includes(record.mimeType);
}

async function load() {
  const file = await fetch(local('archive'), {
    credentials:'omit', cache:'no-store', redirect:'error', signal:archiveRead.signal,
  });
  if (!file.ok) throw new Error('The selected archive could not be read');
  const body = file.headers.get('Content-Type') === 'application/gzip'
    ? file.body.pipeThrough(new DecompressionStream('gzip')) : file.body;
  const reader = new WarcReader();
  const report = await reader.loadWarcBuffer(await new Response(body).arrayBuffer());
  if (report.warnings.length) throw new Error(report.warnings[0]);
  return reader;
}

function archivedAsset(reader, url, destination) {
  const {record} = OfflineNavigation.resolve(url, url, reader);
  if (!usable(record)) return absent();
  const mime = record.mimeType;
  let body = record.bodyBytes;
  if (destination === 'style' && mime === 'text/css') {
    body = reader.rewriteStyles(new TextDecoder().decode(body), record.url, asset => assetUrl(asset.url));
  } else if (!(
    (destination === 'image' && /^image\/(png|jpeg|gif|webp|avif|bmp|svg\+xml|x-icon)$/.test(mime)) ||
    (destination === 'font' && /^font\/(woff2?|otf|ttf)$/.test(mime)) ||
    (destination === 'audio' && /^audio\/(mpeg|mp4|ogg|wav|webm)$/.test(mime)) ||
    (destination === 'video' && /^video\/(mp4|ogg|webm)$/.test(mime))
  )) {
    return absent();
  }
  return new Response(body, {headers:{...responseHeaders, 'Content-Type':mime}});
}

async function archived(request, url, name) {
  const reader = await (archive ??= load());
  if (stopped) return absent();
  const target = url.searchParams.get('url');
  if (name === 'asset') return target ? archivedAsset(reader, target, request.destination) : absent();
  if (name === 'catalogue') {
    return json([...new Set(reader.urlList.filter(item => html(reader.getRecord(item))))]);
  }
  if (!target) return absent();
  const {record} = OfflineNavigation.resolve(target, target, reader);
  if (!html(record)) return absent();
  const text = new TextDecoder().decode(record.bodyBytes);
  const document = text.replace(/(<style\b[^>]*>)([\s\S]*?)(<\/style>)/gi, (match, start, css, end) =>
    start + reader.rewriteStyles(css, record.url, asset => assetUrl(asset.url)) + end);
  return json({url:record.url, document});
}

async function respond(request) {
  const url = new URL(request.url);
  if (url.origin !== scope.origin || !url.pathname.startsWith(scope.pathname)) return absent();
  const name = url.pathname.slice(scope.pathname.length);
  if (!url.search && name === 'stop' && request.method === 'POST') {
    stopped = true;
    archiveRead.abort();
    archive = null;
    const reply = await fetch(request);
    if (reply.ok) {
      const clients = await self.clients.matchAll({type:'window'});
      for (const client of clients) client.postMessage('aegis-replay-stopped');
    }
    return reply;
  }
  if (stopped || request.method !== 'GET') return absent();
  if (!url.search && (name === '' || name === 'app.js')) return fetch(request);
  if (name === 'asset' || (request.destination === '' && request.mode === 'same-origin' &&
      (name === 'document' || name === 'catalogue'))) {
    try {
      return await archived(request, url, name);
    } catch (error) {
      return new Response('Could not read the saved WARC', {status:422, headers:responseHeaders});
    }
  }
  return absent();
}

self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => event.respondWith(respond(event.request)));

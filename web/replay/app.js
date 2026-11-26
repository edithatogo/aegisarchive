'use strict';

const frame = document.getElementById('replayFrame');
const pages = document.getElementById('pages');
const status = document.getElementById('status');
const stop = document.getElementById('stop');
const fallback = 'Open the saved WARC in the station’s Offline WARC Viewer to use the fallback.';
const stoppedMessage = 'Replay stopped. You can close this tab.';
const passiveTags = new Set(('a abbr address article aside audio b blockquote br caption cite code col colgroup dd del ' +
  'details div dl dt em figcaption figure footer h1 h2 h3 h4 h5 h6 header hr i img ins kbd li link main mark nav ol ' +
  'p picture pre q s samp section small source span strong style sub summary sup table tbody td th thead time tr u ul var video').split(' '));
const textAttributes = new Set(['alt', 'class', 'id', 'title', 'role', 'lang', 'dir', 'width', 'height', 'colspan', 'rowspan']);
const assetAttributes = {img:['src'], link:['href'], source:['src'], audio:['src'], video:['src', 'poster']};
let registration;
let stopped = false;
let displayed = 0;

function targetUrl(raw, base) {
  try {
    const url = new URL(raw, base);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch (_) {
    return null;
  }
}

function assetUrl(url) {
  const asset = new URL('asset', location.href);
  asset.searchParams.set('url', url);
  return asset.href;
}

function passiveDocument(text, url) {
  // Template contents stay inert until every element and URL has been checked.
  const page = document.createElement('template');
  page.innerHTML = text;
  for (const element of page.content.querySelectorAll('*')) {
    const tag = element.localName;
    if (element.namespaceURI !== 'http://www.w3.org/1999/xhtml' || !passiveTags.has(tag) ||
        (tag === 'link' && element.getAttribute('rel')?.toLowerCase() !== 'stylesheet')) {
      element.remove();
      continue;
    }
    const sources = assetAttributes[tag] || [];
    const links = new Map();
    for (const name of tag === 'a' ? ['href'] : sources) {
      const raw = element.getAttribute(name);
      const target = raw && targetUrl(raw, url);
      if (target) links.set(name, target);
    }
    for (const {name} of [...element.attributes]) {
      if (!textAttributes.has(name)) element.removeAttribute(name);
    }
    if (tag === 'a' && links.has('href')) {
      element.setAttribute('href', '#');
      element.dataset.archiveTarget = links.get('href');
    } else {
      for (const [name, target] of links) element.setAttribute(name, assetUrl(target));
      if (tag === 'link') element.setAttribute('rel', 'stylesheet');
      if (tag === 'audio' || tag === 'video') element.controls = true;
    }
  }
  return page.content;
}

async function get(name, target) {
  const url = new URL(name, location.href);
  if (target) url.searchParams.set('url', target);
  return fetch(url, {mode:'same-origin', cache:'no-store', credentials:'omit', redirect:'error'});
}

async function show(target) {
  const request = ++displayed;
  const reply = await get('document', target);
  if (stopped || request !== displayed) return;
  if (reply.status === 404) {
    status.textContent = 'Missing archived resource: ' + target;
    return;
  }
  if (!reply.ok) throw new Error('Could not read the saved archive.');
  const entry = await reply.json();
  if (stopped || request !== displayed) return;
  const contents = passiveDocument(entry.document, entry.url);
  const view = frame.contentDocument;
  view.body.replaceChildren(contents);
  view.title = entry.url;
  frame.hidden = false;
  if ([...pages.options].some(option => option.value === entry.url)) pages.value = entry.url;
  status.textContent = entry.url;
}

function reportError(error) {
  if (!stopped) status.textContent = error.message + ' ' + fallback;
}

function waitForControl() {
  const service = navigator.serviceWorker;
  if (service.controller) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timeout = AbortSignal.timeout(10000);
    service.addEventListener('controllerchange', resolve, {once:true, signal:timeout});
    timeout.addEventListener('abort', () => reject(new Error('Replay worker did not activate.')), {once:true});
  });
}

async function start() {
  try {
    if (!navigator.serviceWorker) throw new Error('This browser cannot start an isolated replay worker.');
    registration = await navigator.serviceWorker.register('worker.js', {scope:'./'});
    if (stopped) {
      await registration.unregister();
      return;
    }
    await waitForControl();
    const reply = await get('catalogue');
    if (!reply.ok) throw new Error('Could not read the selected WARC.');
    const urls = await reply.json();
    if (stopped) return;
    if (!urls.length) throw new Error('This archive contains no replayable HTML pages.');
    for (const url of urls) pages.add(new Option(url, url));
    pages.disabled = false;
    await show(urls[0]);
  } catch (error) {
    reportError(error);
  }
}

frame.addEventListener('load', () => {
  frame.contentDocument.addEventListener('click', event => {
    const link = event.target.closest('a[data-archive-target]');
    if (link) {
      event.preventDefault();
      show(link.dataset.archiveTarget).catch(reportError);
    }
  });
  start();
}, {once:true});
frame.srcdoc = '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" ' +
  'content="default-src \'none\'; style-src \'self\' \'unsafe-inline\'; img-src \'self\'; font-src \'self\'; media-src \'self\'; ' +
  'script-src \'none\'; connect-src \'none\'; form-action \'none\'; base-uri \'none\'"></head><body></body></html>';

pages.addEventListener('change', () => show(pages.value).catch(reportError));
function clearPage(message) {
  stopped = true;
  frame.hidden = true;
  const view = frame.contentDocument;
  if (view) {
    view.title = '';
    view.body?.replaceChildren();
  }
  pages.replaceChildren();
  pages.disabled = true;
  stop.disabled = true;
  status.textContent = message;
}
navigator.serviceWorker?.addEventListener('message', event => {
  if (!stopped && event.source === navigator.serviceWorker.controller && event.data === 'aegis-replay-cleared') {
    clearPage('Replay cleared. You can close this tab.');
  }
});
stop.addEventListener('click', async () => {
  clearPage('Closing replay…');
  try {
    const reply = await fetch('stop', {method:'POST', mode:'same-origin', signal:AbortSignal.timeout(10000)});
    if (!reply.ok) throw new Error('Replay server did not confirm stop');
    status.textContent = stoppedMessage;
  } catch (_) {
    status.textContent = 'Replay cleared. If the replay server is still running, press Ctrl+C in its terminal.';
  } finally {
    await registration?.unregister();
  }
});

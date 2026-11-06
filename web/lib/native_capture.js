/* Scoped local transport; source response bodies remain inert bytes. */
class NativeCapture {
  static async archive() {
    const response = await fetch('/__station/capture/session', {headers: {'X-Aegis-UI': '1'}});
    if (!response.ok) throw Error('Launch AegisArchive from the USB before capturing.');
    const {token} = await response.json();
    return new UsbArchiveStreamer(new NativeCapture(token));
  }
  static async start(profile, archive = null) {
    const response = await fetch('/__station/capture/session', {headers: {'X-Aegis-UI': '1'}});
    if (!response.ok) throw Error('Start the local launcher to use native capture.');
    const {token} = await response.json();
    const session = new NativeCapture(token);
    const result = await session.call('start', {profile,
      ...(archive ? {archive_id:archive.id,lease:archive.lease} : {})});
    session.id = result.id; session.logFile = result.log_file;
    return session;
  }
  static async discoverArchives() {
    const archive = await NativeCapture.archive();
    return (await archive.session.call('archive-discover', {})).archives;
  }
  static async profileHash(profile, route = 'native') {
    const publicProfile={acquisition_route:route,target:profile.target || {},politeness:profile.politeness || {},
      archival:profile.archival || {},taxonomy:profile.taxonomy || [],
      profile_id:profile.profile_id || null,authentication:{mode:profile.authentication?.mode || 'none',
        allowed_domains:profile.authentication?.allowed_domains || []}};
    const ordered=value=>Array.isArray(value)?value.map(ordered):value && typeof value==='object'
      ?Object.fromEntries(Object.keys(value).sort().map(key=>[key,ordered(value[key])])):value;
    const bytes=new TextEncoder().encode(JSON.stringify(ordered(publicProfile)));
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
  }
  static async saveReport(report) {
    const response = await fetch('/__station/capture/session', {headers: {'X-Aegis-UI': '1'}});
    if (!response.ok) throw Error('Local diagnostic storage unavailable; check that the USB launcher is running.');
    const {token} = await response.json();
    return new NativeCapture(token).call('diagnostics', {report});
  }
  static async recover() {
    const response = await fetch('/__station/capture/session', {headers: {'X-Aegis-UI': '1'}});
    if (!response.ok) throw Error('Local launcher unavailable');
    const {token} = await response.json();
    return new NativeCapture(token).call('recover', {});
  }
  constructor(token) { this.token = token; }
  async call(action, payload) {
    const controller = action.startsWith('debug-') ? new AbortController() : null;
    const timeout = controller ? setTimeout(() => controller.abort(), 5000) : null;
    try {
    const body = JSON.stringify(payload);
    if (action === 'archive-checkpoint') {
      const bytes = new TextEncoder().encode(body).byteLength;
      const limit = 33 * 1024 * 1024;
      if (bytes > limit) {
        const error = Error('Checkpoint request exceeds the local request limit; previous checkpoint retained.');
        error.diagnostic = {stage:'checkpoint', error_type:'CheckpointLimitError', reason_code:'request_limit', bytes, limit_bytes:limit};
        throw error;
      }
    }
    const response = await fetch('/__station/capture/' + action, {
      method: 'POST', keepalive: action === 'stop' || action === 'debug-events', signal: controller?.signal,
      headers: {'Content-Type': 'application/json', 'X-Capture-Token': this.token},
      body
    });
    const result = await response.json();
    if (!response.ok) {
      const error = Error(result.error || 'Native acquisition failed');
      error.diagnostic = result.diagnostic;
      throw error;
    }
    return result;
    } finally { if (timeout) clearTimeout(timeout); }
  }
  async fetch(url, options = {}) {
    const result = await this.call('fetch', {id: this.id, url, options: {method: options.method || 'GET', headers: options.headers || {},
      ...(options.rule_context ? {rule_context:options.rule_context} : {})}});
    const body = Uint8Array.from(atob(result.body), c => c.charCodeAt(0));
    const status=result.status === 0 && result.rule_decision && !result.rule_decision.download ? 204 : result.status;
    const response = new Response([204,205,304].includes(status) ? null : body,
      {status, headers: result.headers});
    response.aegisRequest = result.request;
    response.aegisRuleDecision = result.rule_decision;
    return response;
  }
  async close() { return this.call('stop', {id: this.id}); }
}

class UsbArchiveStreamer {
  constructor(session) {
    this.session = session;
    this.isUsb = true;
    this.offsets = {warc: 0, cdx: 0};
    this.failed = false;
  }
  async init() {
    if (this.id) return true;
    const result = await this.session.call('archive-start', {});
    this.id = result.archive_id;
    this.directory = result.directory;
    this.lease = result.lease;
    this.generation = result.generation;
    return true;
  }
  async reopen(archive, profileHash) {
    const result=await this.session.call('archive-reopen', {archive_id:archive.archive_id,
      generation:archive.generation,profile_hash:profileHash});
    this.id=result.archive_id;this.directory=result.directory;
    this.lease=result.lease;this.generation=result.generation;this.offsets=result.offsets;
    return result.state;
  }
  async checkpoint(state, profileHash) {
    if (!state) return; // Finalization, not a null callback, closes the on-disk checkpoint.
    if (this.failed) throw Error('USB archive storage has failed');
    try {
      const result=await this.session.call('archive-checkpoint',{archive_id:this.id,
        generation:this.generation,state,profile_hash:profileHash,lease:this.lease});
      this.generation=result.generation;
    } catch (error) {
      error.diagnostic = {stage:'checkpoint', error_type:error.name, ...error.diagnostic};
      throw error;
    }
  }
  async writeChunk(bytes, kind = 'warc') {
    if (this.failed) throw Error('USB archive storage has failed');
    try {
      for (let start = 0; start < bytes.length; start += 262144) {
        const part = bytes.subarray(start, start + 262144);
        let binary = '';
        for (let i = 0; i < part.length; i += 8192) binary += String.fromCharCode(...part.subarray(i, i + 8192));
        const payload={archive_id:this.id,kind,offset:this.offsets[kind],data:btoa(binary),lease:this.lease};
        // A lost acknowledgement can be retried once with the exact same bytes/offset.
        let result;
        try {result=await this.session.call('archive-chunk',payload);}
        catch(error) {
          if (error.diagnostic || !(error instanceof TypeError)) throw error;
          result=await this.session.call('archive-chunk',payload);
        }
        if (result.offset !== this.offsets[kind] + part.length) throw Error('USB archive write offset mismatch');
        this.offsets[kind] = result.offset;
      }
    } catch (error) {
      this.failed = true;
      error.diagnostic = {stage: 'storage', error_type: 'StorageError'};
      throw error;
    }
  }
  async finalize(cdxText, complete) {
    if (this.failed) throw Error('USB archive storage has failed');
    await this.writeChunk(new TextEncoder().encode(cdxText), 'cdx');
    return this.session.call('archive-finalize', {archive_id: this.id, lease:this.lease, summary: {complete}});
  }
  getTotalBytes() { return this.offsets.warc; }
}

// Persist only safe native diagnostics and code locations, never arbitrary exception text.
function captureFailureReport(error, crawler) {
  const diagnostic = error.diagnostic || {};
  const event = {stage:diagnostic.stage || 'capture', error_type:diagnostic.error_type || error.name || 'Error',
    timestamp:new Date().toISOString()};
  for (const key of ['reason_code','operation','code_file','code_function'])
    if (typeof diagnostic[key] === 'string' && /^[\w .:/()-]{1,100}$/.test(diagnostic[key])) event[key]=diagnostic[key];
  for (const key of ['bytes','limit_bytes','code_line'])
    if (Number.isSafeInteger(diagnostic[key]) && diagnostic[key]>=0) event[key]=diagnostic[key];
  if (event.error_type === 'CheckpointLimitError' && ['state_limit','metadata_limit','request_limit'].includes(event.reason_code))
    event.error_message = `Checkpoint ${event.reason_code}: ${event.bytes} bytes exceeds ${event.limit_bytes} byte limit. Previous checkpoint retained; narrow the capture scope.`;
  else event.error_message = `${event.error_type} during ${event.stage}${event.code_file ? ' at '+event.code_file+':'+event.code_line+' ('+event.code_function+')' : ''}.`;
  if (diagnostic.diagnostic_log_failed === true) event.diagnostic_log_failed = true;
  const counts=Object.fromEntries(['captured','excluded','failed','pending','unsupported'].map(k=>[k,0]));
  for (const item of crawler?.resourceOutcomes?.values() || []) if (item.state in counts) counts[item.state]++;
  return {schema_version:1, generated_at:event.timestamp, outcome:'failed',
    coverage:{complete:false, counts, archive_storage_verified:false}, events:[event],
    progress:{visited: crawler?.visited?.size || 0, queued:crawler?.queue?.length || 0},
    limitations:['No successful archive receipt was produced. Partial bytes and the previous checkpoint may remain on the USB.']};
}
if (typeof module !== 'undefined') module.exports = {NativeCapture, UsbArchiveStreamer, captureFailureReport};

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
    const response = await fetch('/__station/capture/' + action, {
      method: 'POST', keepalive: action === 'stop' || action === 'debug-events', signal: controller?.signal,
      headers: {'Content-Type': 'application/json', 'X-Capture-Token': this.token},
      body: JSON.stringify(payload)
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
    const result=await this.session.call('archive-checkpoint',{archive_id:this.id,
      generation:this.generation,state,profile_hash:profileHash,lease:this.lease});
    this.generation=result.generation;
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

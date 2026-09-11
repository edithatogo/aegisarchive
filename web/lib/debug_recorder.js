/* Progressive USB journal. Never serializes profiles, headers, bodies or errors. */
class DebugRecorder {
  constructor(call, notify = () => {}, failed = () => {}) {
    this.call = call; this.notify = notify; this.onFailure = failed;
    this.queue = []; this.active = false; this.sending = false; this.sequence = 0;
  }
  async enable(create = true) {
    if (this.active) return;
    const status = await this.call('debug-status', {});
    if (status.failed) {
      this.path = status.log_file; this.terminal = true;
      this.notify({failed: true, permanent: true, path: this.path, pending: this.queue.length});
      this.onFailure(); return;
    }
    if (!create && !status.active) return;
    const result = await this.call('debug-start', {});
    this.client = result.client_id; this.path = result.log_file;
    this.sequence = result.next_sequence; this.active = true; this.terminal = false;
    this.notify({saved: result.saved_events, pending: 0, path: this.path});
    this.record('browser_attached');
  }
  record(event, fields = {}) {
    if (!this.active || this.terminal) return;
    if (this.queue.length >= 1024) {
      this.notify({failed: true, path: this.path, pending: this.queue.length, overflow: true});
      this.onFailure(); return;
    }
    // Call sites pass structured scalar fields only; filter again on the server.
    const value = {event};
    for (const [key, field] of Object.entries(fields)) {
      if (typeof field === 'number' || typeof field === 'boolean') value[key] = field;
      else if (typeof field === 'string' && field.length <= 8192 && !['message','body','headers','source'].includes(key)) value[key] = field;
    }
    if (value.url) {
      try { const url = new URL(value.url); url.username = ''; url.password = ''; url.search = ''; url.hash = ''; value.url = url.href; }
      catch (_) { delete value.url; }
    }
    this.queue.push(value);
    void this.flush();
  }
  async flush() {
    if (!this.active || this.terminal || this.sending || !this.queue.length) return;
    this.sending = true;
    // Freeze the batch until acknowledged, including after an ambiguous timeout.
    this.batch ||= this.queue.slice(0, 4);
    try {
      const result = await this.call('debug-events', {client_id: this.client, sequence: this.sequence, events: this.batch});
      if (result.next_sequence !== this.sequence + this.batch.length) throw Error('Debug acknowledgement mismatch');
      this.sequence = result.next_sequence;
      this.queue.splice(0, this.batch.length); this.batch = null;
      this.notify({saved: result.saved_events, pending: this.queue.length, path: this.path});
    } catch (error) {
      this.terminal = error.diagnostic?.stage === 'storage';
      this.notify({failed: true, permanent: this.terminal, pending: this.queue.length, path: this.path});
      this.onFailure();
    } finally { this.sending = false; }
    // A failed batch is retried by the timer, never in a tight loop.
    if (!this.batch && this.queue.length) void this.flush();
  }
}
if (typeof module !== 'undefined') module.exports = {DebugRecorder};

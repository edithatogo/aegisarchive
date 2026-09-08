/* Scoped local transport; source response bodies remain inert bytes. */
class NativeCapture {
  static async start(profile) {
    const response = await fetch('/__station/capture/session', {headers: {'X-Aegis-UI': '1'}});
    if (!response.ok) throw Error('Start the local launcher to use native capture.');
    const {token} = await response.json();
    const session = new NativeCapture(token);
    const result = await session.call('start', {profile});
    session.id = result.id; session.logFile = result.log_file;
    return session;
  }
  constructor(token) { this.token = token; }
  async call(action, payload) {
    const response = await fetch('/__station/capture/' + action, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Capture-Token': this.token},
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || 'Native acquisition failed');
    return result;
  }
  async fetch(url) {
    const result = await this.call('fetch', {id: this.id, url});
    const body = Uint8Array.from(atob(result.body), c => c.charCodeAt(0));
    return new Response([204,205,304].includes(result.status) ? null : body,
      {status: result.status, headers: result.headers});
  }
  async close() { return this.call('stop', {id: this.id}); }
}

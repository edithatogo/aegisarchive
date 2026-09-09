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
  static async saveReport(report) {
    const response = await fetch('/__station/capture/session', {headers: {'X-Aegis-UI': '1'}});
    if (!response.ok) throw Error('Local diagnostic storage unavailable; download JSON to the USB.');
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
    const response = await fetch('/__station/capture/' + action, {
      method: 'POST', keepalive: action === 'stop', headers: {'Content-Type': 'application/json', 'X-Capture-Token': this.token},
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) {
      const error = Error(result.error || 'Native acquisition failed');
      error.diagnostic = result.diagnostic;
      throw error;
    }
    return result;
  }
  async fetch(url, options = {}) {
    const result = await this.call('fetch', {id: this.id, url, options: {method: options.method || 'GET', headers: options.headers || {}}});
    const body = Uint8Array.from(atob(result.body), c => c.charCodeAt(0));
    const response = new Response([204,205,304].includes(result.status) ? null : body,
      {status: result.status, headers: result.headers});
    response.aegisRequest = result.request;
    return response;
  }
  async close() { return this.call('stop', {id: this.id}); }
}

/**
 * J.A.R.V.I.S. Pure Decoupled API Service Layer
 * Handles all backend REST communication with automatic host detection and timeouts.
 */
(function (window) {
  const API_BASE = (window.location.protocol === 'file:' || (window.location.port !== '5000' && window.location.port !== ''))
    ? 'http://127.0.0.1:5000'
    : '';

  const JarvisApi = {
    getBaseUrl() {
      return API_BASE;
    },

    async fetchTelemetry(timeoutMs = 2500) {
      const resp = await fetch(`${API_BASE}/api/telemetry`, { signal: AbortSignal.timeout(timeoutMs) });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    },

    async sendChatCommand(prompt, speak = false, timeoutMs = 15000) {
      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, speak }),
        signal: AbortSignal.timeout(timeoutMs)
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    },

    async launchApp(target, action = 'open') {
      const resp = await fetch(`${API_BASE}/api/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, action }),
        signal: AbortSignal.timeout(5000)
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    },

    async setVolume(level) {
      const resp = await fetch(`${API_BASE}/api/system/volume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level })
      });
      return await resp.json();
    },

    async setBrightness(level) {
      const resp = await fetch(`${API_BASE}/api/system/brightness`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level })
      });
      return await resp.json();
    },

    async getNotes() {
      const resp = await fetch(`${API_BASE}/api/notes`, { signal: AbortSignal.timeout(3000) });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    },

    async addNote(text) {
      const resp = await fetch(`${API_BASE}/api/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      return await resp.json();
    },

    async clearNotes() {
      const resp = await fetch(`${API_BASE}/api/notes`, { method: 'DELETE' });
      return await resp.json();
    },

    async voiceListen() {
      const resp = await fetch(`${API_BASE}/api/voice/listen`, {
        method: 'POST',
        signal: AbortSignal.timeout(6000)
      });
      return await resp.json();
    }
  };

  window.JarvisApi = JarvisApi;
})(window);


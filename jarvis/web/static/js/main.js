/**
 * J.A.R.V.I.S. Main Coordinator (Decoupled Modular Architecture)
 * Integrates JarvisApi, JarvisStore, JarvisAudio, and JarvisSpatialHUD.
 */
function initJarvisHUD() {
  // DOM Elements
  const spatialContainer = document.getElementById('spatial3DViewport');
  const chatStream = document.getElementById('chatStream');
  const txtCommand = document.getElementById('txtCommand');
  const btnSend = document.getElementById('btnSend');
  const btnMic = document.getElementById('btnMic');
  const toggleVoice = document.getElementById('toggleVoiceOutput');
  const btnMute = document.getElementById('btnAudioMute');
  const hudStatusBadge = document.getElementById('hudStatusBadge');
  const hudStatusText = document.getElementById('hudStatusText');
  const coreStatusTitle = document.getElementById('coreStatusTitle');
  const coreSubTitle = document.getElementById('coreSubTitle');
  const coreCoords = document.getElementById('coreCoords');
  const hudClock = document.getElementById('hudClock');
  const hudDate = document.getElementById('hudDate');
  const sliderVol = document.getElementById('sliderVolume');
  const sliderBright = document.getElementById('sliderBrightness');
  const lblVolVal = document.getElementById('lblVolVal');
  const lblBrightVal = document.getElementById('lblBrightVal');

  // Telemetry Gauges
  const valCpu = document.getElementById('valCpu');
  const barCpu = document.getElementById('barCpu');
  const valRam = document.getElementById('valRam');
  const barRam = document.getElementById('barRam');
  const valBattery = document.getElementById('valBattery');
  const barBattery = document.getElementById('barBattery');
  const valDisk = document.getElementById('valDisk');
  const barDisk = document.getElementById('barDisk');

  // Notes Drawer
  const notesDrawer = document.getElementById('notesDrawer');
  const notesBackdrop = document.getElementById('notesDrawerBackdrop');
  const btnCloseNotes = document.getElementById('btnCloseNotes');
  const notesListContainer = document.getElementById('notesListContainer');
  const txtNewNote = document.getElementById('txtNewNote');
  const btnAddNote = document.getElementById('btnAddNote');
  const btnClearAllNotes = document.getElementById('btnClearAllNotes');
  const btnReset3DCamera = document.getElementById('btnReset3DCamera');

  // 1. Initialize 3D Spatial Cockpit Scene
  if (window.JarvisSpatialHUD && spatialContainer) {
    window.JarvisSpatialHUD.init(spatialContainer);
  }

  // 2. Chat Bubble Helpers
  function appendChatBubble(role, text, timeStr) {
    if (!chatStream) return;
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role === 'user' ? 'user-bubble' : 'jarvis-bubble'} animate-slide-up`;

    const now = timeStr || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const sender = role === 'user' ? 'YOU' : '● J.A.R.V.I.S.';

    bubble.innerHTML = `
      <div class="bubble-header">
        <span class="avatar-tag">${sender}</span>
        <span class="bubble-time">${now}</span>
      </div>
      <div class="bubble-content">${escapeHtml(text)}</div>
    `;

    chatStream.appendChild(bubble);
    chatStream.scrollTop = chatStream.scrollHeight;
  }

  function escapeHtml(string) {
    return String(string)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/\n/g, '<br>');
  }

  // 3. Command Submission (Chat API + Local Fallback)
  async function submitCommand(prompt) {
    const query = (prompt || (txtCommand ? txtCommand.value : '') || '').trim();
    if (!query) return;

    if (txtCommand) txtCommand.value = '';
    appendChatBubble('user', query);
    window.JarvisStore.setSystemState('processing');
    if (window.JarvisAudio) window.JarvisAudio.playSound('click');

    const speak = toggleVoice ? toggleVoice.checked : false;

    try {
      const data = await window.JarvisApi.sendChatCommand(query, speak);
      if (data.success) {
        appendChatBubble('jarvis', data.response, data.timestamp);
        if (window.JarvisAudio) window.JarvisAudio.playSound('success');

        if (speak) {
          window.JarvisStore.setSystemState('speaking');
          setTimeout(() => window.JarvisStore.setSystemState('idle'), 2500);
        } else {
          window.JarvisStore.setSystemState('idle');
        }
      } else {
        appendChatBubble('jarvis', `Error: ${data.error || 'Failed to process command'}`);
        window.JarvisStore.setSystemState('idle');
      }
    } catch (err) {
      const local = window.JarvisStore.getOfflineResponse(query);
      if (local) {
        appendChatBubble('jarvis', local);
        if (window.JarvisAudio) window.JarvisAudio.playSound('success');
      } else {
        appendChatBubble('jarvis', `⚠️ Backend server is offline or unreachable.\nTo enable full AI automation and desktop app launching, please run in your terminal:\n▶ python run_web.py`);
      }
      window.JarvisStore.setSystemState('idle');
    }
  }

  if (btnSend) {
    btnSend.addEventListener('click', (e) => {
      e.preventDefault();
      submitCommand();
      if (txtCommand) txtCommand.focus();
    });
  }

  if (txtCommand) {
    txtCommand.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitCommand();
      }
    });
  }

  // Wire 3D Core Raycast Click Event
  window.JarvisStore.on('core:click', () => {
    if (btnMic) {
      btnMic.click();
    } else {
      submitCommand('system status');
    }
  });

  // Suggestion Chips
  document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const prompt = btn.getAttribute('data-prompt');
      if (prompt) submitCommand(prompt);
    });
  });

  // 4. Quick Launchpad Buttons
  document.querySelectorAll('.launch-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (window.JarvisAudio) window.JarvisAudio.playSound('click');

      btn.classList.add('btn-clicked');
      setTimeout(() => btn.classList.remove('btn-clicked'), 350);

      const app = btn.getAttribute('data-app');
      const cmd = btn.getAttribute('data-cmd');
      const drawer = btn.getAttribute('data-drawer');
      const label = btn.querySelector('.btn-text')?.textContent || app || 'Action';

      if (drawer === 'notes') {
        openNotesDrawer();
      } else if (cmd) {
        submitCommand(cmd);
      } else if (app) {
        appendChatBubble('user', `▶ Open ${label}`);
        window.JarvisStore.setSystemState('processing');
        try {
          const data = await window.JarvisApi.launchApp(app, 'open');
          appendChatBubble('jarvis', data.message || `Launching ${label}...`);
          if (window.JarvisAudio) window.JarvisAudio.playSound('success');
          window.JarvisStore.setSystemState('idle');
        } catch (err) {
          appendChatBubble('jarvis', `⚠️ Failed to launch ${label}. Please ensure the backend is running:\n▶ python run_web.py`);
          window.JarvisStore.setSystemState('idle');
        }
      }
    });
  });

  // 5. Speech Recognition Setup
  if (btnMic && window.JarvisAudio) {
    const speechDriver = window.JarvisAudio.initSpeechRecognition((transcript) => {
      submitCommand(transcript);
    });
    btnMic.addEventListener('click', () => {
      speechDriver.start();
    });
  }

  // 6. Hardware Sliders (Volume & Brightness)
  if (sliderVol) {
    sliderVol.addEventListener('input', (e) => {
      if (lblVolVal) lblVolVal.textContent = `${e.target.value}%`;
    });
    sliderVol.addEventListener('change', async (e) => {
      const val = parseInt(e.target.value, 10);
      if (window.JarvisAudio) window.JarvisAudio.playSound('click');
      try {
        await window.JarvisApi.setVolume(val);
      } catch (err) {
        console.error('Volume control error:', err);
      }
    });
  }

  if (sliderBright) {
    sliderBright.addEventListener('input', (e) => {
      if (lblBrightVal) lblBrightVal.textContent = `${e.target.value}%`;
    });
    sliderBright.addEventListener('change', async (e) => {
      const val = parseInt(e.target.value, 10);
      if (window.JarvisAudio) window.JarvisAudio.playSound('click');
      try {
        await window.JarvisApi.setBrightness(val);
      } catch (err) {
        console.error('Brightness control error:', err);
      }
    });
  }

  // 7. Reset Camera
  if (btnReset3DCamera && window.JarvisSpatialHUD) {
    btnReset3DCamera.addEventListener('click', () => {
      window.JarvisSpatialHUD.resetCamera();
    });
  }

  // Audio SFX Toggle
  if (btnMute) {
    btnMute.addEventListener('click', () => {
      const curr = window.JarvisStore.get('sfxEnabled');
      window.JarvisStore.setState('sfxEnabled', !curr);
      btnMute.style.color = !curr ? 'var(--text-secondary)' : 'var(--color-red)';
      if (window.JarvisAudio) window.JarvisAudio.playSound('click');
    });
  }

  // 8. Telemetry Polling Loop
  async function pollTelemetry() {
    try {
      const data = await window.JarvisApi.fetchTelemetry(2000);
      window.JarvisStore.setBackendOnline(true);
      window.JarvisStore.updateTelemetry({
        cpu: data.cpu ? data.cpu.percent : 0,
        ramPercent: data.ram ? data.ram.percent : 0,
        ramUsed: data.ram ? data.ram.used_gb : 0,
        ramTotal: data.ram ? data.ram.total_gb : 0,
        battery: data.battery ? data.battery.percent : 100,
        batteryPlugged: data.battery ? data.battery.plugged : true,
        diskFree: data.disk ? data.disk.free_gb : 0,
        diskPercent: data.disk ? data.disk.percent : 0,
        time: data.time,
        date: data.date
      });

      // Handle backend reminder events
      if (data.events && data.events.length > 0) {
        data.events.forEach(ev => {
          if (ev.type === 'reminder') {
            if (window.JarvisAudio) window.JarvisAudio.playSound('alert');
            appendChatBubble('jarvis', `🚨 ALARM / REMINDER: ${ev.message}`, ev.time);
          }
        });
      }
    } catch (e) {
      window.JarvisStore.setBackendOnline(false);
      const now = new Date();
      if (hudClock) hudClock.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      if (hudDate) hudDate.textContent = now.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
    }
  }
  setInterval(pollTelemetry, 2000);
  pollTelemetry();

  // 9. React to Store State Changes
  window.JarvisStore.on('backend:status', ({ online }) => {
    if (hudStatusBadge) {
      hudStatusBadge.classList.toggle('offline', !online);
      if (hudStatusText) {
        hudStatusText.textContent = online ? 'SYSTEMS OPERATIONAL' : 'BACKEND OFFLINE (run python run_web.py)';
      }
    }
  });

  window.JarvisStore.on('state:system', ({ state }) => {
    if (hudStatusBadge) hudStatusBadge.className = `status-badge ${state}`;
    if (btnMic) {
      btnMic.classList.toggle('active-listening', state === 'listening');
    }
    if (coreStatusTitle) {
      if (state === 'listening') coreStatusTitle.textContent = 'LISTENING';
      else if (state === 'speaking') coreStatusTitle.textContent = 'SPEAKING';
      else if (state === 'processing') coreStatusTitle.textContent = 'PROCESSING';
      else coreStatusTitle.textContent = 'ONLINE';
    }
    if (coreSubTitle) {
      if (state === 'listening') coreSubTitle.textContent = 'AUDIO INPUT ACTIVE';
      else if (state === 'speaking') coreSubTitle.textContent = 'TTS SYNTHESIS';
      else if (state === 'processing') coreSubTitle.textContent = 'NEURAL EVALUATION';
      else coreSubTitle.textContent = 'NEURAL SYNC 100%';
    }
  });

  window.JarvisStore.on('telemetry:update', (telem) => {
    if (valCpu) valCpu.textContent = `${telem.cpu.toFixed(1)}%`;
    if (barCpu) barCpu.style.width = `${Math.min(100, telem.cpu)}%`;

    if (valRam) valRam.textContent = `${telem.ramUsed} / ${telem.ramTotal} GB`;
    if (barRam) barRam.style.width = `${Math.min(100, telem.ramPercent)}%`;

    if (valBattery) {
      const plug = telem.batteryPlugged ? '⚡ Charging' : 'Discharging';
      valBattery.textContent = `${telem.battery}% (${plug})`;
    }
    if (barBattery) barBattery.style.width = `${Math.min(100, telem.battery)}%`;

    if (valDisk) valDisk.textContent = `${telem.diskFree} GB Free`;
    if (barDisk) barDisk.style.width = `${Math.min(100, telem.diskPercent)}%`;

    if (hudClock && telem.time) hudClock.textContent = telem.time;
    if (hudDate && telem.date) hudDate.textContent = telem.date;
  });

  // 10. Notes Drawer Logic
  function openNotesDrawer() {
    window.JarvisStore.toggleNotesDrawer(true);
    if (notesDrawer) notesDrawer.classList.add('open');
    if (notesBackdrop) notesBackdrop.classList.add('open');
    loadNotes();
  }

  function closeNotesDrawer() {
    window.JarvisStore.toggleNotesDrawer(false);
    if (notesDrawer) notesDrawer.classList.remove('open');
    if (notesBackdrop) notesBackdrop.classList.remove('open');
  }

  if (btnCloseNotes) btnCloseNotes.addEventListener('click', closeNotesDrawer);
  if (notesBackdrop) notesBackdrop.addEventListener('click', closeNotesDrawer);

  function getLocalNotes() {
    try {
      return JSON.parse(localStorage.getItem('jarvis_notes') || '[]');
    } catch (e) { return []; }
  }
  function saveLocalNotes(notes) {
    try {
      localStorage.setItem('jarvis_notes', JSON.stringify(notes));
    } catch (e) {}
  }

  async function loadNotes() {
    let notes = [];
    try {
      const data = await window.JarvisApi.getNotes();
      if (data.notes) {
        notes = data.notes;
        saveLocalNotes(notes);
      }
    } catch (e) {
      notes = getLocalNotes();
    }

    if (!notesListContainer) return;
    notesListContainer.innerHTML = '';
    if (!notes || notes.length === 0) {
      notesListContainer.innerHTML = '<p class="empty-note-msg">No notes recorded yet. Add one above!</p>';
      return;
    }
    notes.forEach(n => {
      const item = document.createElement('div');
      item.className = 'note-item';
      item.innerHTML = `
        <div>${escapeHtml(n.text)}</div>
        <div class="note-time">${n.at ? new Date(n.at).toLocaleString() : 'Recent'}</div>
      `;
      notesListContainer.appendChild(item);
    });
  }

  if (btnAddNote) {
    btnAddNote.addEventListener('click', async () => {
      const text = txtNewNote ? txtNewNote.value.trim() : '';
      if (!text) return;
      if (txtNewNote) txtNewNote.value = '';
      if (window.JarvisAudio) window.JarvisAudio.playSound('click');

      const local = getLocalNotes();
      local.push({ text, at: new Date().toISOString() });
      saveLocalNotes(local);

      try {
        await window.JarvisApi.addNote(text);
      } catch (e) {}

      await loadNotes();
    });
  }

  if (btnClearAllNotes) {
    btnClearAllNotes.addEventListener('click', async () => {
      if (!confirm('Clear all stored notes?')) return;
      if (window.JarvisAudio) window.JarvisAudio.playSound('click');
      saveLocalNotes([]);
      try {
        await window.JarvisApi.clearNotes();
      } catch (e) {}
      await loadNotes();
    });
  }
}

// Auto-initialize whether DOM is ready or loading
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initJarvisHUD);
} else {
  initJarvisHUD();
}

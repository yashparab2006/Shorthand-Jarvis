/**
 * J.A.R.V.I.S. Reactive State Store & Event Bus
 * Decouples state mutations and event signaling from UI and 3D rendering.
 */
(function (window) {
  class JarvisEventBus {
    constructor() {
      this.listeners = new Map();
    }

    on(event, handler) {
      if (!this.listeners.has(event)) {
        this.listeners.set(event, new Set());
      }
      this.listeners.get(event).add(handler);
      return () => this.off(event, handler);
    }

    off(event, handler) {
      if (this.listeners.has(event)) {
        this.listeners.get(event).delete(handler);
      }
    }

    emit(event, data) {
      if (this.listeners.has(event)) {
        this.listeners.get(event).forEach(fn => {
          try {
            fn(data);
          } catch (err) {
            console.error(`[EventBus] Error in handler for '${event}':`, err);
          }
        });
      }
    }
  }

  const bus = new JarvisEventBus();

  const state = {
    systemState: 'idle', // 'idle' | 'listening' | 'speaking' | 'processing'
    backendOnline: false,
    voiceEnabled: false,
    sfxEnabled: true,
    telemetry: {
      cpu: 0,
      ramPercent: 0,
      ramUsed: 0,
      ramTotal: 0,
      battery: 100,
      batteryPlugged: true,
      diskFree: 0,
      diskPercent: 0,
      time: '--:--:--',
      date: '--------'
    },
    volume: 50,
    brightness: 50,
    notes: [],
    notesDrawerOpen: false,
    spatialFocus: 'center' // 'center' | 'left' | 'right' | 'drawer'
  };

  const JarvisStore = {
    get(key) {
      return state[key];
    },

    getState() {
      return { ...state };
    },

    setState(key, value) {
      const prev = state[key];
      if (prev !== value) {
        state[key] = value;
        bus.emit(`change:${key}`, { value, prev });
        bus.emit('state:change', { key, value, prev });
      }
    },

    setSystemState(newState) {
      const prev = state.systemState;
      if (prev !== newState) {
        state.systemState = newState;
        bus.emit('state:system', { state: newState, prev });
      }
    },

    setBackendOnline(isOnline) {
      const prev = state.backendOnline;
      if (prev !== isOnline) {
        state.backendOnline = isOnline;
        bus.emit('backend:status', { online: isOnline, prev });
      }
    },

    updateTelemetry(data) {
      state.telemetry = { ...state.telemetry, ...data };
      bus.emit('telemetry:update', state.telemetry);
    },

    setNotes(notes) {
      state.notes = notes;
      bus.emit('notes:update', notes);
    },

    toggleNotesDrawer(open = null) {
      state.notesDrawerOpen = open !== null ? open : !state.notesDrawerOpen;
      bus.emit('notes:drawer', state.notesDrawerOpen);
    },

    setSpatialFocus(wing) {
      state.spatialFocus = wing;
      bus.emit('spatial:focus', wing);
    },

    on(event, handler) {
      return bus.on(event, handler);
    },

    emit(event, data) {
      bus.emit(event, data);
    },

    getOfflineResponse(query) {
      const q = (query || '').toLowerCase().trim();
      if (/^(hi|hello|hey|greetings|good morning|good evening|good afternoon)\b/i.test(q)) {
        return "Hello Sir! Systems are operational in local 3D spatial cockpit mode. To enable desktop app launching and full system automation, ensure the Python backend is active via 'python run_web.py'.";
      }
      if (/how are you|system status/i.test(q)) {
        return "3D Spatial HUD is operating smoothly at 60 FPS. Ready for your command, Sir. Launch 'python run_web.py' for full desktop integration.";
      }
      if (/who are you|what are you/i.test(q)) {
        return "I am J.A.R.V.I.S., your Just A Rather Very Intelligent System. Connect me to the Python backend ('python run_web.py') for full hardware and application control.";
      }
      if (/what time|current time|the time|clock/i.test(q)) {
        return `The current time is ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}.`;
      }
      if (/date|today/i.test(q)) {
        return `Today is ${new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}.`;
      }
      if (/help|what can you do/i.test(q)) {
        return "I can assist with: launching desktop apps (Chrome, VS Code, Terminal, Notepad), taking screenshots, calculating math, setting reminders, and managing notes. Run 'python run_web.py' to activate full backend capabilities.";
      }
      return null;
    }
  };

  window.JarvisStore = JarvisStore;
})(window);


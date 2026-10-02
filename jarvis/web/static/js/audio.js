/**
 * J.A.R.V.I.S. Procedural Audio Synthesizer & Speech Controller
 * Manages Web Audio SFX and browser/backend speech recognition.
 */
(function (window) {
  let audioCtx = null;

  function getAudioContext() {
    if (!audioCtx) {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (AudioCtxClass) {
        audioCtx = new AudioCtxClass();
      }
    }
    return audioCtx;
  }

  const JarvisAudio = {
    playSound(type = 'click') {
      if (!window.JarvisStore || !window.JarvisStore.get('sfxEnabled')) return;
      try {
        const ctx = getAudioContext();
        if (!ctx) return;
        if (ctx.state === 'suspended') ctx.resume();

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        const now = ctx.currentTime;
        if (type === 'click') {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(1200, now);
          osc.frequency.exponentialRampToValueAtTime(400, now + 0.05);
          gain.gain.setValueAtTime(0.08, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
          osc.start(now);
          osc.stop(now + 0.05);
        } else if (type === 'beep') {
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(880, now);
          osc.frequency.setValueAtTime(1760, now + 0.06);
          gain.gain.setValueAtTime(0.06, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
          osc.start(now);
          osc.stop(now + 0.12);
        } else if (type === 'success') {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(587.33, now); // D5
          osc.frequency.setValueAtTime(880, now + 0.08); // A5
          gain.gain.setValueAtTime(0.08, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
          osc.start(now);
          osc.stop(now + 0.2);
        } else if (type === 'alert') {
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(440, now);
          osc.frequency.setValueAtTime(330, now + 0.1);
          gain.gain.setValueAtTime(0.08, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
          osc.start(now);
          osc.stop(now + 0.25);
        }
      } catch (err) {
        // Autoplay policy catch
      }
    },

    initSpeechRecognition(onResultCallback) {
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      let recognition = null;

      if (SpeechRec) {
        recognition = new SpeechRec();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
          window.JarvisStore.setSystemState('listening');
          JarvisAudio.playSound('beep');
        };

        recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          if (onResultCallback) onResultCallback(transcript);
        };

        recognition.onerror = (event) => {
          console.warn('[JarvisAudio] Browser speech recognition error:', event.error);
          JarvisAudio.fallbackPythonVoice(onResultCallback);
        };

        recognition.onend = () => {
          if (window.JarvisStore.get('systemState') === 'listening') {
            window.JarvisStore.setSystemState('idle');
          }
        };
      }

      return {
        start() {
          if (recognition) {
            try {
              recognition.start();
            } catch (e) {
              JarvisAudio.fallbackPythonVoice(onResultCallback);
            }
          } else {
            JarvisAudio.fallbackPythonVoice(onResultCallback);
          }
        }
      };
    },

    async fallbackPythonVoice(onResultCallback) {
      window.JarvisStore.setSystemState('listening');
      JarvisAudio.playSound('beep');
      try {
        const data = await window.JarvisApi.voiceListen();
        if (data.success && data.query) {
          if (onResultCallback) onResultCallback(data.query);
        } else {
          window.JarvisStore.emit('chat:system_message', 'I did not catch any speech. Please try again.');
          window.JarvisStore.setSystemState('idle');
        }
      } catch (err) {
        window.JarvisStore.emit('chat:system_message', 'Voice input offline. Check microphone.');
        window.JarvisStore.setSystemState('idle');
      }
    }
  };

  window.JarvisAudio = JarvisAudio;
})(window);


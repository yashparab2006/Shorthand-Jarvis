"""Phase-2 voice engine — no LLMs.

- Ambient-noise calibration (2.5)
- VAD listening via SpeechRecognition Microphone when PyAudio exists,
  fallback to legacy fixed-duration sounddevice recording
- STT chain: Google (online) -> Vosk (offline, if installed + model present)
- Async SAPI TTS queue with interrupt + wait_until_done
- Passive wake-word polling ("jarvis") without extra models
"""
from __future__ import annotations

import gc
import json
import os
import queue
import threading

import pythoncom
import sounddevice as sd
import speech_recognition as sr
import win32com.client

from jarvis.logger import get_logger

log = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# SVSFlags for SAPI SpVoice.Speak: 0 = default (blocking), 2 = purge before speak
_SVSFPurgeBeforeSpeak = 2


def _voice_settings() -> dict:
    try:
        with open(os.path.join(_BASE_DIR, "config", "settings.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("voice", {})
    except Exception:
        return {}


class VoiceEngine:
    def __init__(self, rate: int = 175, sample_rate: int = 16000, **overrides) -> None:
        cfg = _voice_settings()
        cfg.update(overrides or {})

        self._recognizer = sr.Recognizer()
        self._sample_rate = sample_rate
        self._rate = rate

        # Tunables (all overridable via settings.json -> voice.*)
        self._calibrate_duration: float = float(cfg.get("calibrate_duration", 1.0))
        self._vad_enabled: bool = bool(cfg.get("vad_enabled", True))
        self._stt_mode: str = str(cfg.get("stt", "auto")).lower()  # auto|google|vosk
        raw_model = cfg.get("vosk_model_path", os.path.join(_BASE_DIR, "models", "vosk-en"))
        # Resolve relative to repo root so it works regardless of cwd.
        self._vosk_model_path: str = raw_model if os.path.isabs(raw_model) else os.path.join(_BASE_DIR, raw_model)
        self._wake_words: list = [w.lower() for w in cfg.get("wake_words", ["jarvis", "hey jarvis"])]
        self._wake_chunk: float = float(cfg.get("wake_chunk", 2.5))
        self._tts_async: bool = bool(cfg.get("tts_async", True))

        # Dynamic energy threshold works better across rooms/mics.
        self._recognizer.dynamic_energy_threshold = True
        try:
            self._recognizer.energy_threshold = int(cfg.get("energy_threshold", 300))
        except Exception:
            pass

        # --- TTS worker thread (owns its own SpVoice; COM apartment-safe) ---
        self._speaker = None
        if not self._tts_async:
            pythoncom.CoInitialize()
            self._speaker = win32com.client.Dispatch("SAPI.SpVoice")
            self._speaker.Volume = 100
            self._speaker.Rate = max(-10, min(10, int((rate - 175) / 15)))

        self._tts_queue: queue.Queue = queue.Queue()
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._tts_thread = threading.Thread(target=self._tts_worker, name="jarvis-tts", daemon=True)
        self._tts_thread.start()

        # Lazy Vosk model (load on first offline need, not at boot).
        self._vosk_model = None
        self._vosk_warned = False

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------
    def _tts_worker(self) -> None:
        try:
            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Volume = 100
            speaker.Rate = max(-10, min(10, int((self._rate - 175) / 15)))
        except Exception as exc:
            log.error("TTS worker init failed: %s", exc)
            return
        while not self._stop.is_set():
            try:
                item = self._tts_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:  # shutdown sentinel
                self._tts_queue.task_done()
                break
            text, purge = item
            if text is None:
                if purge:
                    try:
                        speaker.Speak("", _SVSFPurgeBeforeSpeak)
                    except Exception:
                        pass
                self._tts_queue.task_done()
                continue
            try:
                self._speaking.set()
                speaker.Speak(text, _SVSFPurgeBeforeSpeak if purge else 0)
            except Exception as exc:
                log.error("TTS Output Error: %s", exc)
            finally:
                self._speaking.clear()
                self._tts_queue.task_done()
        try:
            speaker = None
            gc.collect()
            pythoncom.CoUninitialize()
        except Exception:
            pass

    def speak(self, text: str, interrupt: bool = False, wait: bool = False) -> None:
        """Enqueue speech. interrupt=True purges pending + current utterance."""
        if not text:
            return
        print(f"\nJarvis: {text}")
        if not self._tts_async:
            if self._speaker is None:
                try:
                    pythoncom.CoInitialize()
                    self._speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    self._speaker.Volume = 100
                    self._speaker.Rate = max(-10, min(10, int((self._rate - 175) / 15)))
                except Exception as exc:
                    log.error("TTS Output Error: %s", exc)
                    return
            try:
                self._speaker.Speak(text, _SVSFPurgeBeforeSpeak if interrupt else 0)
            except Exception as exc:
                log.error("TTS Output Error: %s", exc)
            return
        if interrupt:
            self._drain_queue()
        self._tts_queue.put((text, interrupt))
        if wait:
            self.wait_until_done()

    def _drain_queue(self) -> None:
        try:
            while True:
                self._tts_queue.get_nowait()
                self._tts_queue.task_done()
        except queue.Empty:
            pass

    def interrupt(self) -> None:
        """Stop current + pending speech (e.g. urgent reminder)."""
        self._drain_queue()
        if self._tts_async:
            self._tts_queue.put((None, True))
        elif self._speaker is not None:
            try:
                self._speaker.Speak("", _SVSFPurgeBeforeSpeak)
            except Exception:
                pass

    def wait_until_done(self, timeout: float = 30.0) -> bool:
        """Block until TTS queue drains and current utterance ends."""
        import time as _time

        try:
            self._tts_queue.join()
        except Exception:
            pass
        deadline = _time.time() + max(0.0, timeout)
        while self._speaking.is_set():
            if _time.time() >= deadline:
                return False
            _time.sleep(0.05)
        return True

    def shutdown(self) -> None:
        try:
            self._stop.set()
            self._tts_queue.put(None)
            self._tts_thread.join(timeout=3.0)
        except Exception as exc:
            log.debug("Voice shutdown: %s", exc)
        if self._speaker is not None:
            try:
                self._speaker = None
                gc.collect()
                pythoncom.CoUninitialize()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Calibration (Phase 2.5)
    # ------------------------------------------------------------------
    def calibrate(self, duration: float | None = None) -> None:
        """Adapt energy_threshold to room noise. Never fatal."""
        duration = self._calibrate_duration if duration is None else duration
        try:
            mic = sr.Microphone(sample_rate=self._sample_rate)
            with mic as source:
                print(f"Calibrating mic for {duration:.1f}s ambient noise...")
                self._recognizer.adjust_for_ambient_noise(source, duration=duration)
            log.info("Mic calibrated, energy_threshold=%s", self._recognizer.energy_threshold)
        except Exception as exc:
            # PyAudio missing / no mic — VAD path will fall back to sounddevice.
            log.info("Mic calibration skipped (%s); using threshold %s", exc, self._recognizer.energy_threshold)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def _record_fixed(self, duration: float) -> sr.AudioData:
        audio_array = sd.rec(
            int(duration * self._sample_rate),
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()
        return sr.AudioData(audio_array.tobytes(), self._sample_rate, 2)

    def _record_vad(self, max_duration: float) -> sr.AudioData | None:
        """Phrase-based recording (stops on silence). None if unavailable."""
        if not self._vad_enabled:
            return None
        try:
            mic = sr.Microphone(sample_rate=self._sample_rate)
        except Exception as exc:
            log.debug("VAD unavailable (%s), using fixed recording", exc)
            return None
        try:
            with mic as source:
                audio = self._recognizer.listen(
                    source, timeout=8, phrase_time_limit=max(max_duration, 6.0)
                )
            return audio
        except sr.WaitTimeoutError:
            return None
        except Exception as exc:
            log.debug("VAD listen failed (%s), using fixed recording", exc)
            return None

    # ------------------------------------------------------------------
    # STT (Google -> Vosk offline fallback, no LLMs)
    # ------------------------------------------------------------------
    def _recognize_google(self, audio: sr.AudioData) -> str | None:
        try:
            return self._recognizer.recognize_google(audio).strip()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            log.warning("Google STT unreachable (%s)", exc)
            return None  # signal: try offline fallback
        except Exception as exc:
            log.warning("Google STT error (%s)", exc)
            return None

    def _vosk_available(self) -> bool:
        if self._vosk_model is not None:
            return True
        try:
            import vosk  # noqa: F401
        except ImportError:
            if not self._vosk_warned:
                log.info("Vosk not installed; offline STT disabled (pip install vosk)")
                self._vosk_warned = True
            return False
        if not os.path.isdir(self._vosk_model_path):
            if not self._vosk_warned:
                log.info("Vosk model missing at %s; offline STT disabled", self._vosk_model_path)
                self._vosk_warned = True
            return False
        return True

    def _recognize_vosk(self, audio: sr.AudioData) -> str | None:
        """Offline recognition. Returns None if unavailable."""
        try:
            import vosk
        except ImportError:
            return None
        if not os.path.isdir(self._vosk_model_path):
            return None
        try:
            if self._vosk_model is None:
                self._vosk_model = vosk.Model(self._vosk_model_path)
                log.info("Vosk offline model loaded from %s", self._vosk_model_path)
            rec = vosk.KaldiRecognizer(self._vosk_model, self._sample_rate)
            rec.AcceptWaveform(audio.get_raw_data())
            import json as _json

            text = _json.loads(rec.FinalResult()).get("text", "")
            return text.strip()
        except Exception as exc:
            log.warning("Vosk recognition failed (%s)", exc)
            return None

    def _recognize(self, audio: sr.AudioData) -> str:
        """STT chain honoring stt mode. Always returns str (possibly '')."""
        if self._stt_mode == "vosk":
            return self._recognize_vosk(audio) or ""
        if self._stt_mode == "google":
            return self._recognize_google(audio) or ""
        # auto: Google first, Vosk fallback on network failure
        result = self._recognize_google(audio)
        if result is not None:
            return result
        offline = self._recognize_vosk(audio)
        if offline is not None:
            log.info("Used offline (Vosk) recognition")
            return offline
        print("\r[Voice Error]: Speech network unreachable (offline model missing).")
        return ""

    # ------------------------------------------------------------------
    # Public: listen + wake word
    # ------------------------------------------------------------------
    def listen(self, duration: float = 4.0) -> str:
        print("\nListening...", end="", flush=True)
        try:
            audio = self._record_vad(duration)
            if audio is None:
                audio = self._record_fixed(duration)
            print("\rRecognizing voice...", end="", flush=True)
            query = self._recognize(audio)
            if query:
                print(f"\rUser (Voice): {query}")
            else:
                print("\r[Voice Warning]: Speech unreadable or silent.")
            return query
        except Exception as exc:
            print(f"\r[Voice Error]: {exc}")
            return ""

    def _contains_wake(self, text: str) -> str | None:
        low = text.lower().strip()
        for w in self._wake_words:
            if w and w in low:
                # Return remainder after wake word ("hey jarvis open notepad" -> "open notepad")
                idx = low.find(w) + len(w)
                return text[idx:].strip(" ,!-_")
        return None

    def wait_for_wake_word(self, timeout: float | None = 60.0) -> str:
        """Passive polling loop. Returns command remainder, '' on timeout.

        Uses short fixed chunks so it works with stock deps; if Vosk is
        installed it is preferred (free offline wake checks).
        """
        import time as _time

        print(f"\nSay '{self._wake_words[-1]}' to wake me... (timeout {timeout}s)")
        deadline = None if timeout is None else _time.time() + timeout
        offline_first = self._vosk_available()
        _silent_chunks = 0
        while deadline is None or _time.time() < deadline:
            try:
                audio = self._record_fixed(self._wake_chunk)
            except Exception as exc:
                log.debug("Wake chunk failed: %s", exc)
                _time.sleep(0.3)
                continue
            # Mic-dead detector: RMS near zero means nothing captured
            # (muted mic / Windows privacy block / wrong device).
            try:
                import numpy as np

                data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
                rms = int(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
            except Exception:
                try:
                    import audioop

                    rms = audioop.rms(audio.get_raw_data(), 2)
                except Exception:
                    rms = -1
            if rms >= 0 and rms < 80:
                _silent_chunks += 1
                if _silent_chunks == 3:
                    print("\n[Wake] mic sounds silent — check Windows mic volume + "
                          "Settings > Privacy > Microphone > 'Let desktop apps access your microphone'.")
                continue
            if rms >= 0:
                _silent_chunks = 0
            # Run offline first; if it heard speech but no wake word,
            # double-check with Google before discarding (Vosk-small often
            # mis-hears "jarvis" as "service/james/travis").
            vosk_text, google_text = "", None
            if offline_first:
                vosk_text = self._recognize_vosk(audio) or ""
                remainder = self._contains_wake(vosk_text)
                if remainder is not None:
                    print(f"\r[Wake] heard: {vosk_text!r}")
                    return remainder
                if vosk_text:
                    print(f"  [heard (offline): {vosk_text!r}] — listening for 'hey jarvis'...")
                    google_text = self._recognize_google(audio)
                    if google_text is None:
                        continue
                else:
                    google_text = self._recognize_google(audio) or ""
            else:
                google_text = self._recognize_google(audio)
                if google_text is None:  # network down -> try offline once
                    google_text = self._recognize_vosk(audio) or ""
            text = google_text or ""
            if not text:
                continue
            if text != vosk_text:
                print(f"  [heard (online): {text!r}] — listening for 'hey jarvis'...")
            remainder = self._contains_wake(text)
            if remainder is not None:
                print(f"\r[Wake] heard: {text!r}")
                return remainder
        return ""

"""Jarvis entry point — voice mode (default) or text mode (--text)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from jarvis import JarvisBrain, VoiceEngine
from jarvis.logger import get_logger
from jarvis.modules.utilities import UtilityEngine

log = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_settings() -> dict:
    try:
        with open(os.path.join(_BASE_DIR, "config", "settings.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.warning("Could not load settings.json (%s), using defaults", exc)
        return {"voice": {"rate": 175, "sample_rate": 16000, "listen_duration": 4.0}}


def _is_exit_command(command: str) -> bool:
    return command.lower().strip() in ("exit", "quit", "stop", "bye")


def run_voice_assistant(rate: int | None = None, duration: float | None = None,
                       use_wake: bool | None = None, calibrate: bool = True,
                       stt: str | None = None, wakeup_audio: bool | None = None):
    settings = load_settings()
    vcfg = settings.get("voice", {})
    rate = rate if rate is not None else vcfg.get("rate", 175)
    duration = duration if duration is not None else vcfg.get("listen_duration", 4.0)
    if use_wake is None:
        use_wake = bool(vcfg.get("wake_enabled", False))
    wake_timeout = float(vcfg.get("wake_timeout", 60.0))
    if wakeup_audio is None:
        wakeup_audio = bool(vcfg.get("wakeup_audio", True))
    wakeup_text = str(vcfg.get("wakeup_text", "Audio check."))
    overrides = {}
    if stt:
        overrides["stt"] = stt

    print("Booting audio systems...")
    voice = VoiceEngine(rate=rate, sample_rate=vcfg.get("sample_rate", 16000), **overrides)
    brain = JarvisBrain(speak_callback=voice.speak)

    print("==================================================")
    mode = "WAKE-WORD MODE (say 'hey jarvis')" if use_wake else "PURE VOICE MODE"
    print(f"      JARVIS ASSISTANT - {mode}          ")
    print("==================================================")

    # 1. Sacrificial blip (absorbs Windows audio cold-start cut).
    # Non-blocking: plays in background while we calibrate, so startup
    # costs ~0.3s instead of the full utterance. Skip with --no-wakeup.
    if wakeup_audio:
        voice.speak(wakeup_text, wait=False)
        time.sleep(0.3)


    # 2a. Mic calibration (Phase 2.5) — skipped with --no-calibrate
    if calibrate:
        try:
            voice.calibrate()
        except Exception as exc:
            log.debug("Calibration failed: %s", exc)

    # 2b. Time-aware greeting (wait until done so mic doesn't hear itself)
    try:
        greeting = UtilityEngine().get_personal_opening()
    except Exception:
        greeting = "Good morning! Welcome back. Systems are operational."
    if use_wake:
        greeting += " Say hey Jarvis to wake me."
    voice.speak(greeting, wait=True)

    def handle(command: str) -> bool:
        """Returns True to keep looping, False to exit."""
        if not command:
            return True
        if _is_exit_command(command):
            voice.speak("Shutting down. Goodbye!", wait=True)
            return False
        try:
            response = brain.respond(command)
        except Exception as exc:
            log.exception("Respond error: %s", exc)
            response = f"Sorry, something went wrong: {exc}"
        voice.speak(response, wait=True)
        return True

    # 3. Main loop with graceful shutdown
    try:
        while True:
            try:
                if use_wake:
                    # Idle until wake word; remainder may already be a command.
                    remainder = voice.wait_for_wake_word(timeout=wake_timeout)
                    if remainder and not _is_exit_command(remainder) and len(remainder.split()) >= 2:
                        command = remainder
                    else:
                        if remainder and _is_exit_command(remainder):
                            voice.speak("Shutting down. Goodbye!", wait=True)
                            break
                        voice.speak("Yes?", wait=True)
                        command = voice.listen(duration=duration)
                    if not handle(command):
                        break
                else:
                    command = voice.listen(duration=duration)
                    if not handle(command):
                        break

            except KeyboardInterrupt:
                print("\nVoice Mode terminated manually.")
                voice.speak("System offline.", wait=True)
                break
            except Exception as exc:
                log.exception("Loop error: %s", exc)
    finally:
        brain.shutdown()
        voice.shutdown()


def run_text_mode():
    """Test Jarvis without a microphone: type commands instead."""
    print("==================================================")
    print("      JARVIS ASSISTANT - TEXT MODE                ")
    print("       (type 'exit' to quit)                      ")
    print("==================================================")

    def speak_callback(text: str) -> None:
        print(f"\nJarvis: {text}")

    brain = JarvisBrain(speak_callback=speak_callback)
    try:
        print(f"Jarvis: {UtilityEngine().get_personal_opening()} (text mode)")
        while True:
            try:
                command = input("\nYou: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nText mode terminated.")
                break
            if not command:
                continue
            if _is_exit_command(command):
                print("Jarvis: Shutting down. Goodbye!")
                break
            try:
                print(f"Jarvis: {brain.respond(command)}")
            except Exception as exc:
                log.exception("Respond error: %s", exc)
                print(f"Jarvis: Sorry, something went wrong: {exc}")
    finally:
        brain.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis voice assistant")
    parser.add_argument("--web", action="store_true", help="Launch the 2D Holographic HUD Web Interface")
    parser.add_argument("--gui", action="store_true", help="Launch the Jarvis 2D Web HUD Interface")
    parser.add_argument("--native", action="store_true", help="Launch the Native CustomTkinter Desktop GUI")
    parser.add_argument("--text", action="store_true", help="Run in text mode (no microphone needed)")
    parser.add_argument("--rate", type=int, default=None, help="TTS speech rate")
    parser.add_argument("--listen-duration", type=float, default=None, help="Seconds to listen per turn")
    parser.add_argument("--wake", action="store_true", help="Enable passive wake-word mode (say 'hey jarvis')")
    parser.add_argument("--no-wake", action="store_true", help="Force classic always-listening loop")
    parser.add_argument("--no-calibrate", action="store_true", help="Skip mic ambient-noise calibration")
    parser.add_argument("--no-wakeup", action="store_true", help="Skip sacrificial wake-up blip (fastest boot)")
    parser.add_argument("--stt", choices=["auto", "google", "vosk"], default=None,
                        help="Speech-to-text backend (auto = Google with Vosk offline fallback)")
    args = parser.parse_args(argv)

    if args.native:
        from jarvis.gui import run_gui
        run_gui()
    elif args.web or args.gui:
        from run_web import main as run_web_main
        run_web_main()
    elif args.text:
        run_text_mode()
    else:
        use_wake = True if args.wake else (False if args.no_wake else None)
        run_voice_assistant(rate=args.rate, duration=args.listen_duration,
                            use_wake=use_wake, calibrate=not args.no_calibrate,
                            stt=args.stt, wakeup_audio=not args.no_wakeup)
    return 0


if __name__ == "__main__":
    sys.exit(main())

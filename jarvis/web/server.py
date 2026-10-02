"""Flask Web Server for Jarvis 2D Modern HUD Website.
Connects the web frontend to all backend Jarvis engines.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response

from jarvis.brain import JarvisBrain
from jarvis.voice.engine import VoiceEngine
from jarvis.modules.health import HealthEngine
from jarvis.modules.utilities import UtilityEngine
from jarvis.modules.notes import NotesEngine
from jarvis.modules.reminders import ReminderEngine
from jarvis.modules.system_control import SystemControlEngine
from jarvis.launcher.app_launcher import AppLauncher
from jarvis.logger import get_logger

log = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)

# Initialize Backend Engines
health_engine = HealthEngine()
utility_engine = UtilityEngine()
notes_engine = NotesEngine()
system_engine = SystemControlEngine()
app_launcher = AppLauncher()

# Global events/state for web notifications
recent_events = []


def on_reminder_trigger(message: str):
    log.info("Web reminder trigger: %s", message)
    recent_events.append({
        "type": "reminder",
        "message": message,
        "time": datetime.now().strftime("%I:%M %p"),
    })


reminder_engine = ReminderEngine(speak_callback=on_reminder_trigger)
brain = JarvisBrain(speak_callback=on_reminder_trigger)

# Safe Voice Engine
try:
    voice_engine = VoiceEngine(rate=175)
except Exception as exc:
    log.warning("VoiceEngine init issue in web server: %s", exc)
    voice_engine = None


# ---------------------------------------------------------------------
# CORS & Static File Routing
# ---------------------------------------------------------------------
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With, *"
        return response, 200


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, X-Requested-With, *"
    return response


@app.route("/static/<path:filename>")
def custom_static(filename):
    return send_from_directory(_STATIC_DIR, filename)


@app.route("/jarvis/web/static/<path:filename>")
def custom_nested_static(filename):
    return send_from_directory(_STATIC_DIR, filename)


# ---------------------------------------------------------------------
# Web Routes
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")



@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    speak = bool(data.get("speak", False))

    if not prompt:
        return jsonify({"success": False, "error": "Empty prompt", "response": ""})

    try:
        response_text = brain.respond(prompt)
    except Exception as exc:
        log.exception("Brain error: %s", exc)
        response_text = f"An error occurred: {exc}"

    if speak and voice_engine:
        threading.Thread(target=voice_engine.speak, args=(response_text,), kwargs={"wait": False}, daemon=True).start()

    return jsonify({
        "success": True,
        "prompt": prompt,
        "response": response_text,
        "timestamp": datetime.now().strftime("%I:%M %p"),
    })


@app.route("/api/telemetry", methods=["GET"])
def api_telemetry():
    import psutil

    # CPU
    cpu_p = psutil.cpu_percent(interval=None)

    # RAM
    mem = psutil.virtual_memory()
    ram_used_gb = round(mem.used / (1024**3), 1)
    ram_total_gb = round(mem.total / (1024**3), 1)
    ram_p = mem.percent

    # Battery
    bat = psutil.sensors_battery()
    bat_p = bat.percent if bat else 100
    bat_plugged = bool(bat.power_plugged) if bat else True

    # Disk
    disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
    free_gb = round(disk.free / (1024**3), 1)
    disk_p = disk.percent

    # Volume & Brightness
    vol = system_engine.get_volume() or 50
    bright = system_engine._get_brightness() or 50

    # Events drain
    events = list(recent_events)
    recent_events.clear()

    return jsonify({
        "cpu": {"percent": cpu_p},
        "ram": {"used_gb": ram_used_gb, "total_gb": ram_total_gb, "percent": ram_p},
        "battery": {"percent": bat_p, "plugged": bat_plugged},
        "disk": {"free_gb": free_gb, "percent": disk_p},
        "volume": vol,
        "brightness": bright,
        "time": datetime.now().strftime("%I:%M:%S %p"),
        "date": datetime.now().strftime("%A, %B %d, %Y"),
        "events": events,
    })


@app.route("/api/system/volume", methods=["POST"])
def api_volume():
    data = request.get_json(force=True, silent=True) or {}
    level = int(data.get("level", 50))
    msg = system_engine.set_volume(level)
    return jsonify({"success": True, "message": msg, "level": level})


@app.route("/api/system/brightness", methods=["POST"])
def api_brightness():
    data = request.get_json(force=True, silent=True) or {}
    level = int(data.get("level", 50))
    msg = system_engine.set_brightness(level)
    return jsonify({"success": True, "message": msg, "level": level})


@app.route("/api/launch", methods=["POST"])
def api_launch():
    data = request.get_json(force=True, silent=True) or {}
    app_name = (data.get("target") or "").strip()
    action = data.get("action", "open")

    if action == "close":
        msg = app_launcher.close(app_name)
    else:
        msg = app_launcher.open(app_name)

    return jsonify({"success": True, "message": msg})


@app.route("/api/notes", methods=["GET", "POST", "DELETE"])
def api_notes():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        text = (data.get("text") or "").strip()
        msg = notes_engine.add_note(text)
        return jsonify({"success": True, "message": msg})
    elif request.method == "DELETE":
        msg = notes_engine.clear_notes()
        return jsonify({"success": True, "message": msg})
    else:
        notes_list = notes_engine._read()
        return jsonify({"success": True, "notes": notes_list})


@app.route("/api/reminders", methods=["GET"])
def api_reminders():
    jobs = reminder_engine.scheduler.get_jobs()
    active = []
    for j in jobs:
        active.append({
            "id": j.id,
            "name": j.args[0] if j.args else j.name,
            "next_run": j.next_run_time.strftime("%I:%M %p") if j.next_run_time else "--",
        })
    return jsonify({"success": True, "reminders": active})


@app.route("/api/voice/listen", methods=["POST"])
def api_voice_listen():
    if not voice_engine:
        return jsonify({"success": False, "error": "Voice engine not initialized", "query": ""})

    query = voice_engine.listen(duration=4.5)
    return jsonify({"success": True, "query": query})


def start_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    log.info("Starting Jarvis 2D HUD server on http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    start_server(debug=True)


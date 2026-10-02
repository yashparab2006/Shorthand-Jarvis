"""Launch the Jarvis 2D Holographic HUD Website."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import webbrowser

from jarvis.web.server import start_server


def find_browser_app_executable() -> tuple[str, bool]:
    """Find Chrome or Edge to launch in standalone --app mode."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c, True

    chrome_which = shutil.which("chrome") or shutil.which("msedge")
    if chrome_which:
        return chrome_which, True

    return "browser", False


def main():
    host = "127.0.0.1"
    port = 5000
    url = f"http://{host}:{port}"

    print("==================================================")
    print("      J.A.R.V.I.S. // 2D HOLOGRAPHIC HUD          ")
    print(f"      Launching Web Interface: {url}       ")
    print("==================================================")

    # Start Flask server in daemon thread
    server_thread = threading.Thread(target=start_server, kwargs={"host": host, "port": port, "debug": False}, daemon=True)
    server_thread.start()

    time.sleep(1.2)  # Allow server to bind port

    # Launch in standalone App mode if Chrome/Edge available, else default browser
    exe, is_app_mode = find_browser_app_executable()
    if is_app_mode:
        print(f"Opening in Standalone App Window using: {exe}")
        try:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1200,800"])
        except Exception as exc:
            print(f"Fallback to default browser ({exc})...")
            webbrowser.open(url)
    else:
        print("Opening in default browser...")
        webbrowser.open(url)

    print("\nPress Ctrl+C to stop the Jarvis Web Server.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Jarvis Web Server. Goodbye!")


if __name__ == "__main__":
    main()


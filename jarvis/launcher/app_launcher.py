"""Launch and close desktop apps / websites using config/app_registry.json."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import webbrowser

from jarvis.logger import get_logger

log = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_json(path: str, default: dict) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log.warning("Registry not found: %s, using defaults", path)
    except json.JSONDecodeError as exc:
        log.warning("Registry %s is invalid JSON (%s), using defaults", path, exc)
    return default


def _resolve_executable(path: str) -> str | None:
    """Resolve an executable path, command name, or App Paths registry key on Windows."""
    if not path:
        return None
    expanded = os.path.expandvars(os.path.expanduser(path))
    if os.path.isfile(expanded):
        return expanded
    which_path = shutil.which(expanded) or shutil.which(path)
    if which_path:
        return which_path

    # On Windows, look up registered applications in App Paths registry
    exe_name = os.path.basename(expanded)
    if not exe_name.lower().endswith(".exe"):
        exe_name += ".exe"
    try:
        import winreg

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}") as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    if val:
                        clean_val = os.path.expandvars(val.strip('"'))
                        if os.path.isfile(clean_val):
                            return clean_val
            except OSError:
                pass
    except Exception:
        pass

    # Common installation directory heuristics
    common_candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for cand in common_candidates:
        if os.path.basename(cand).lower() == exe_name.lower() and os.path.isfile(cand):
            return cand

    return None


def _load_settings_chrome() -> str:
    try:
        with open(os.path.join(_BASE_DIR, "config", "settings.json"), "r", encoding="utf-8") as f:
            configured = json.load(f)["browser"]["chrome_path"]
            if os.path.isfile(configured):
                return configured
    except Exception:
        pass
    resolved = _resolve_executable("chrome.exe")
    if resolved:
        return resolved
    return "C:/Program Files/Google/Chrome/Application/chrome.exe"


_ALIASES = {
    "google chrome": "chrome",
    "command prompt": "cmd",
    "terminal": "terminal",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "file explorer": "explorer",
    "explorer": "explorer",
    "task manager": "taskmgr",
}


class AppLauncher:
    # Fallback so Jarvis still works if config files are missing/corrupt.
    _DEFAULT_REGISTRY = {
        "system_apps": {
            "calculator": "calc.exe",
            "notepad": "notepad.exe",
            "command prompt": "cmd.exe",
            "settings": "ms-settings:",
        },
        "process_names": {
            "calculator": "CalculatorApp.exe",
            "notepad": "notepad.exe",
        },
        "custom_apps": {},
    }

    def __init__(self, registry_path: str | None = None) -> None:
        self.chrome_path = _load_settings_chrome()
        try:
            webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(self.chrome_path))
        except Exception as exc:
            log.debug("Could not register Chrome: %s", exc)

        path = registry_path or os.path.join(_BASE_DIR, "config", "app_registry.json")
        registry = _load_json(path, self._DEFAULT_REGISTRY)
        self.system_apps: dict = registry.get("system_apps", {})
        self.process_names: dict = registry.get("process_names", {})
        self.custom_apps: dict = registry.get("custom_apps", {})

        # Merge web direct_sites so "open youtube" keeps working from one place.
        try:
            with open(os.path.join(_BASE_DIR, "config", "web_registry.json"), "r", encoding="utf-8") as f:
                self.direct_sites: dict = json.load(f).get("direct_sites", {})
        except Exception:
            self.direct_sites = {
                "youtube": "https://www.youtube.com",
                "google": "https://www.google.com",
                "github": "https://github.com",
            }

        self.targets: dict = {**self.system_apps, **self.custom_apps, **self.direct_sites}
        # Normalized index so STT noise still hits: 'note pad' -> 'notepad',
        # 'command-prompt' -> 'command prompt'.
        self._norm_index: dict = {}
        for key in list(self.targets) + list(self.process_names):
            self._norm_index.setdefault(re.sub(r"[\s\-_]+", "", key.lower()), key)

    def _resolve(self, target: str) -> str:
        """Map noisy STT target to canonical registry key."""
        t = target.lower().strip()
        if t in _ALIASES:
            t = _ALIASES[t]
        if t in self.targets or t in self.process_names:
            return t
        norm = re.sub(r"[\s\-_]+", "", t)
        if norm in self._norm_index:
            return self._norm_index[norm]
        for alias, canonical in _ALIASES.items():
            if re.sub(r"[\s\-_]+", "", alias) == norm:
                return canonical
        return t

    # -- open -------------------------------------------------------------
    def open(self, target: str) -> str:
        spoken = target.lower().strip()
        target = self._resolve(spoken)
        if target not in self.targets:
            # Fallback: check if target can be resolved directly (e.g. system app or command)
            exe = _resolve_executable(target)
            if exe is None and hasattr(os, "startfile"):
                try:
                    os.startfile(target)
                    return f"Opening {target}."
                except Exception:
                    pass
            if exe is None:
                return f"I don't have a configured path to open {spoken}."
            path = exe
        else:
            path = self.targets[target]

        # URLs / ms-settings: links -> open in browser / OS handler.
        if path.startswith(("http://", "https://", "ms-settings:", "ms-")):
            try:
                if path.startswith(("http://", "https://")):
                    try:
                        webbrowser.get("chrome").open(path)
                    except webbrowser.Error:
                        webbrowser.open(path)
                    return f"Opening {target} in Chrome."
                os.startfile(path)  # type: ignore[attr-defined]  # Windows only
                return f"Opening {target}."
            except Exception as exc:
                log.exception("Failed to open %s", target)
                return f"I could not open {target}: {exc}"

        # Local executables: resolve full path
        exe = _resolve_executable(path)
        if exe is None:
            if hasattr(os, "startfile"):
                try:
                    os.startfile(path)
                    return f"Opening {target}."
                except Exception:
                    pass
            return f"I could not find the executable to open {target}."

        try:
            if "cmd.exe" in exe.lower() or target in ("cmd", "terminal"):
                subprocess.Popen(["cmd.exe", "/k"], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            elif hasattr(os, "startfile") and not exe.lower().endswith((".bat", ".cmd")):
                os.startfile(exe)
            else:
                subprocess.Popen([exe], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            return f"Opening {target}."
        except Exception as exc:
            log.exception("Failed to launch %s", target)
            return f"I could not open {target}: {exc}"

    # -- close ------------------------------------------------------------
    def close(self, target: str) -> str:
        spoken = target.lower().strip()
        target = self._resolve(spoken)

        # Websites / tabs -> close active browser tab (needs focused browser window).
        # Note: "chrome" is handled below by process_names so "close chrome" kills the application.
        if target in ("youtube", "google", "browser", "tab", "gmail", "github"):
            try:
                import pyautogui

                pyautogui.hotkey("ctrl", "w")
                return "Closed the active tab."
            except Exception as exc:
                log.exception("Failed to close tab")
                return f"I could not close the tab: {exc}"

        # Desktop apps -> allowlisted taskkill only.
        if target in self.process_names:
            proc = self.process_names[target]
            try:
                subprocess.run(["taskkill", "/f", "/im", proc], capture_output=True, check=False)  # noqa: S603,S607
                return f"Closed {target}."
            except Exception as exc:
                log.exception("Failed to close %s", target)
                return f"I could not close {target}: {exc}"

        return f"I cannot safely close {target}."

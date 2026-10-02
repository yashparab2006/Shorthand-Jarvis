"""Quick voice notes — persisted to config/notes.json."""
from __future__ import annotations

import json
import os
from datetime import datetime

from jarvis.logger import get_logger

log = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_NOTES_FILE = os.path.join(_BASE_DIR, "config", "notes.json")


class NotesEngine:
    def add_note(self, text: str) -> str:
        text = text.strip().rstrip("?.!")
        if not text:
            return "What should I note down?"
        notes = self._read()
        notes.append({"text": text, "at": datetime.now().isoformat()})
        self._write(notes)
        return f"Noted: {text}."

    def read_notes(self, limit: int = 5) -> str:
        notes = self._read()
        if not notes:
            return "You have no notes yet. Say 'note that ...' to add one."
        recent = notes[-limit:]
        lines = [f"{i + 1}. {n['text']}" for i, n in enumerate(recent)]
        return "Your recent notes: " + "; ".join(lines) + "."

    def clear_notes(self) -> str:
        self._write([])
        return "All notes cleared."

    # -- storage ----------------------------------------------------------
    def _read(self) -> list:
        try:
            with open(_NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, notes: list) -> None:
        try:
            with open(_NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(notes, f, indent=2)
        except Exception as exc:
            log.warning("Could not save notes: %s", exc)

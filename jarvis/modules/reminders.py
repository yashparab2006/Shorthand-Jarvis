"""Background Reminder Engine using APScheduler with JSON persistence."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from jarvis.logger import get_logger

log = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _reminders_path() -> str:
    try:
        with open(os.path.join(_BASE_DIR, "config", "settings.json"), "r", encoding="utf-8") as f:
            rel = json.load(f)["paths"]["reminders_file"]
        return os.path.join(_BASE_DIR, rel)
    except Exception:
        return os.path.join(_BASE_DIR, "config", "reminders.json")


class ReminderEngine:
    def __init__(self, speak_callback: Callable[[str], None] | None = None) -> None:
        self.speak_callback = speak_callback or (lambda msg: None)
        self._file = _reminders_path()
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self._restore_pending()

    # -- public API -------------------------------------------------------
    def add_reminder(self, task: str, amount: int, unit: str) -> str:
        if amount <= 0:
            return "Reminder time must be in the future."
        run_date = datetime.now()
        if "minute" in unit:
            run_date += timedelta(minutes=amount)
        elif "hour" in unit:
            run_date += timedelta(hours=amount)
        else:
            return f"I don't understand the time unit '{unit}'."

        self.scheduler.add_job(self._trigger_reminder, "date", run_date=run_date, args=[task])
        self._persist(task, run_date)
        return f"I have set a reminder to {task} in {amount} {unit}."

    def add_timer(self, amount: int, unit: str) -> str:
        """One-shot countdown — announced like a reminder when it fires."""
        if amount <= 0:
            return "Timer length must be in the future."
        run_date = datetime.now()
        if "second" in unit:
            run_date += timedelta(seconds=amount)
        elif "minute" in unit:
            run_date += timedelta(minutes=amount)
        elif "hour" in unit:
            run_date += timedelta(hours=amount)
        else:
            return f"I don't understand the time unit '{unit}'."

        label = f"Timer ({amount} {unit}) finished"
        self.scheduler.add_job(self._trigger_timer, "date", run_date=run_date, args=[amount, unit])
        self._persist(label, run_date)
        return f"Timer set for {amount} {unit}. I'll let you know when it's done."

    def list_reminders(self) -> str:
        jobs = self.scheduler.get_jobs()
        if not jobs:
            return "You have no pending reminders."
        lines = []
        for i, j in enumerate(jobs):
            if j.func.__name__ == "_trigger_timer":
                lines.append(f"{i+1}. Timer ({j.args[0]} {j.args[1]}) at {j.next_run_time:%I:%M %p}")
            else:
                lines.append(f"{i+1}. {j.args[0]} at {j.next_run_time:%I:%M %p}")
        return "Your reminders: " + "; ".join(lines) + "."

    def shutdown(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
        except Exception as exc:
            log.debug("Scheduler shutdown: %s", exc)

    # -- internals --------------------------------------------------------
    def _trigger_reminder(self, task: str) -> None:
        self._remove_persisted(task)
        try:
            self.speak_callback(f"Sir, here is your reminder: {task}.")
        except Exception as exc:
            log.exception("Reminder callback failed: %s", exc)

    def _trigger_timer(self, amount: int, unit: str) -> None:
        self._remove_persisted(f"Timer ({amount} {unit}) finished")
        try:
            self.speak_callback(f"Your {amount} {unit} timer is finished.")
        except Exception as exc:
            log.exception("Timer callback failed: %s", exc)

    def _persist(self, task: str, run_date: datetime) -> None:
        try:
            entries = self._read_all()
            entries.append({"task": task, "run_at": run_date.isoformat()})
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except Exception as exc:
            log.warning("Could not persist reminder: %s", exc)

    def _remove_persisted(self, task: str) -> None:
        try:
            entries = [e for e in self._read_all() if e.get("task") != task]
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except Exception:
            pass

    def _read_all(self) -> list:
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _restore_pending(self) -> None:
        import re as _re

        restored = 0
        for entry in self._read_all():
            try:
                run_at = datetime.fromisoformat(entry["run_at"])
                if run_at > datetime.now():
                    m = _re.fullmatch(r"Timer \((\d+) (\w+)\) finished", str(entry.get("task", "")))
                    if m:
                        self.scheduler.add_job(self._trigger_timer, "date", run_date=run_at,
                                               args=[int(m.group(1)), m.group(2)])
                    else:
                        self.scheduler.add_job(self._trigger_reminder, "date", run_date=run_at, args=[entry["task"]])
                    restored += 1
            except Exception as exc:
                log.warning("Skipping bad reminder entry %s: %s", entry, exc)
        # Rewrite file dropping expired entries.
        try:
            pending = [e for e in self._read_all() if datetime.fromisoformat(e["run_at"]) > datetime.now()]
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(pending, f, indent=2)
        except Exception:
            pass
        if restored:
            log.info("Restored %d pending reminder(s)", restored)

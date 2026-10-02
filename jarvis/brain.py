from jarvis.launcher.parser import LauncherParser
from jarvis.launcher.app_launcher import AppLauncher
from jarvis.launcher.web_launcher import WebLauncher

from jarvis.modules.health import HealthEngine
from jarvis.modules.utilities import UtilityEngine
from jarvis.modules.reminders import ReminderEngine
from jarvis.modules.system_control import SystemControlEngine
from jarvis.modules.knowledge import KnowledgeEngine
from jarvis.modules.notes import NotesEngine
from jarvis.logger import get_logger

log = get_logger(__name__)

class JarvisBrain:
    def __init__(self, speak_callback=None):
        self._parser = LauncherParser()
        self._utilities = UtilityEngine()
        self._health = HealthEngine()
        self._reminders = ReminderEngine(speak_callback)
        self._system = SystemControlEngine()
        self._knowledge = KnowledgeEngine()
        self._notes = NotesEngine()
        
        # Now active!
        self._app_launcher = AppLauncher()
        self._web_launcher = WebLauncher()

    def shutdown(self):
        """Gracefully stop background services (call on exit)."""
        try:
            self._reminders.shutdown()
        except Exception as exc:
            log.debug("Brain shutdown: %s", exc)

    def respond(self, prompt: str) -> str:
        parsed = self._parser.parse(prompt)

        if not parsed:
            return "I am sorry, I didn't recognize that command."

        intent = parsed["type"]

        if intent == "conversation":
            action = parsed["action"]
            if action == "greeting":
                return "Hello Sir! All systems are online and operational. How can I assist you today?"
            elif action == "status":
                return "I am functioning at optimal capacity, Sir. Neural sync is at 100%. Ready for your command."
            elif action == "identity":
                return "I am J.A.R.V.I.S., your Just A Rather Very Intelligent System. I can manage hardware, launch applications, search the web, calculate math, take screenshots, manage notes, and assist you with daily tasks."
            elif action == "gratitude":
                return "You're very welcome, Sir. Always at your service."
            elif action == "farewell":
                return "Goodbye Sir. Systems standing by."

        elif intent == "system":
            action = parsed["action"]
            if action == "set_volume": return self._system.set_volume(parsed["value"])
            elif action == "volume_up": return self._system.volume_up()
            elif action == "volume_down": return self._system.volume_down()
            elif action == "mute": return self._system.mute_volume(mute=True)
            elif action == "unmute": return self._system.mute_volume(mute=False)
            elif action == "set_brightness": return self._system.set_brightness(parsed["value"])
            elif action == "brightness_up": return self._system.brightness_up()
            elif action == "brightness_down": return self._system.brightness_down()
            elif action == "media": return self._system.control_media(parsed["command"])
            elif action == "screenshot": return self._system.take_screenshot()
            elif action == "lock": return self._system.lock_workstation()
            
        elif intent == "reminder":
            return self._reminders.add_reminder(parsed["task"], parsed["amount"], parsed["unit"])

        elif intent == "timer":
            return self._reminders.add_timer(parsed["amount"], parsed["unit"])

        elif intent == "list_reminders":
            return self._reminders.list_reminders()

        elif intent == "calculate":
            return self._utilities.calculate(parsed["expression"])

        elif intent == "knowledge":
            return self._knowledge.wikipedia(parsed["topic"])

        elif intent == "note_add":
            return self._notes.add_note(parsed["text"])
        elif intent == "note_list":
            return self._notes.read_notes()
        elif intent == "note_clear":
            return self._notes.clear_notes()
            
        elif intent == "health":
            action = parsed["action"]
            if action == "battery": return self._health.get_battery()
            elif action == "cpu": return self._health.get_cpu()
            elif action == "ram": return self._health.get_ram()
            elif action == "disk": return self._health.get_disk()
            
        elif intent == "utility":
            action = parsed["action"]
            if action == "time": return self._utilities.get_time()
            elif action == "date": return self._utilities.get_date()
            elif action == "joke": return self._utilities.get_joke()
            elif action == "help": return self._utilities.get_help()
            elif action == "personal_opening": return self._utilities.get_personal_opening()

        # Now active!
        elif intent == "open": return self._app_launcher.open(parsed["target"])
        elif intent == "close": return self._app_launcher.close(parsed["target"])
        elif intent == "search": return self._web_launcher.search(parsed["query"], parsed.get("engine"))

        return "Command parsed, but execution failed."
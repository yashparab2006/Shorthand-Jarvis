"""Unit tests for Jarvis Assistant modules and launchers."""
import os
import unittest
from unittest.mock import patch, MagicMock

from jarvis.launcher.parser import LauncherParser
from jarvis.launcher.app_launcher import AppLauncher, _resolve_executable, _ALIASES
from jarvis.launcher.web_launcher import WebLauncher
from jarvis.modules.utilities import UtilityEngine
from jarvis.modules.health import HealthEngine
from jarvis.modules.notes import NotesEngine
from jarvis.brain import JarvisBrain


class TestLauncherParser(unittest.TestCase):
    def setUp(self):
        self.parser = LauncherParser()

    def test_search_variants(self):
        # Default search engine
        res = self.parser.parse("search python")
        self.assertEqual(res, {"type": "search", "engine": None, "query": "python"})

        res = self.parser.parse("search for quantum computing")
        self.assertEqual(res, {"type": "search", "engine": None, "query": "quantum computing"})

        # Search with on/in engine
        res = self.parser.parse("search python on google")
        self.assertEqual(res, {"type": "search", "engine": "google", "query": "python"})

        res = self.parser.parse("search chill music on youtube")
        self.assertEqual(res, {"type": "search", "engine": "youtube", "query": "chill music"})

        # Search <engine> for <query>
        res = self.parser.parse("search google for weather today")
        self.assertEqual(res, {"type": "search", "engine": "google", "query": "weather today"})

        # Google prefix
        res = self.parser.parse("google best restaurants")
        self.assertEqual(res, {"type": "search", "engine": "google", "query": "best restaurants"})

    def test_timers_and_reminders(self):
        # Timers
        res = self.parser.parse("set timer 5 minutes")
        self.assertEqual(res, {"type": "timer", "amount": 5, "unit": "minutes"})

        res = self.parser.parse("start a timer for 10 seconds")
        self.assertEqual(res, {"type": "timer", "amount": 10, "unit": "seconds"})

        # Reminders
        res = self.parser.parse("remind me in 10 minutes to take medicine")
        self.assertEqual(res, {"type": "reminder", "amount": 10, "unit": "minutes", "task": "take medicine"})

        res = self.parser.parse("set a reminder for 15 minutes to take a break")
        self.assertEqual(res, {"type": "reminder", "amount": 15, "unit": "minutes", "task": "take a break"})

        res = self.parser.parse("after 1 hour tell me to stretch")
        self.assertEqual(res, {"type": "reminder", "amount": 1, "unit": "hour", "task": "stretch"})

        res = self.parser.parse("show my reminders")
        self.assertEqual(res, {"type": "list_reminders"})

    def test_notes(self):
        res = self.parser.parse("note that buy groceries")
        self.assertEqual(res, {"type": "note_add", "text": "buy groceries"})

        res = self.parser.parse("add a note to call the mechanic")
        self.assertEqual(res, {"type": "note_add", "text": "call the mechanic"})

        res = self.parser.parse("read my notes")
        self.assertEqual(res, {"type": "note_list"})

        res = self.parser.parse("clear my notes")
        self.assertEqual(res, {"type": "note_clear"})

    def test_calculator(self):
        res = self.parser.parse("calculate 12 times 8")
        self.assertEqual(res, {"type": "calculate", "expression": "12 times 8"})

        res = self.parser.parse("what is 15 plus 7")
        self.assertEqual(res, {"type": "calculate", "expression": "15 plus 7"})

        res = self.parser.parse("how much is 50 divided by 2")
        self.assertEqual(res, {"type": "calculate", "expression": "50 divided by 2"})

    def test_system_controls(self):
        self.assertEqual(self.parser.parse("volume to 60"), {"type": "system", "action": "set_volume", "value": 60})
        self.assertEqual(self.parser.parse("volume up"), {"type": "system", "action": "volume_up"})
        self.assertEqual(self.parser.parse("volume down"), {"type": "system", "action": "volume_down"})
        self.assertEqual(self.parser.parse("mute"), {"type": "system", "action": "mute"})
        self.assertEqual(self.parser.parse("unmute"), {"type": "system", "action": "unmute"})
        self.assertEqual(self.parser.parse("brightness to 80"), {"type": "system", "action": "set_brightness", "value": 80})
        self.assertEqual(self.parser.parse("brightness up"), {"type": "system", "action": "brightness_up"})
        self.assertEqual(self.parser.parse("take a screenshot"), {"type": "system", "action": "screenshot"})
        self.assertEqual(self.parser.parse("lock my computer"), {"type": "system", "action": "lock"})

    def test_open_and_close(self):
        self.assertEqual(self.parser.parse("open notepad"), {"type": "open", "target": "notepad"})
        self.assertEqual(self.parser.parse("open google chrome"), {"type": "open", "target": "google chrome"})
        self.assertEqual(self.parser.parse("close notepad"), {"type": "close", "target": "notepad"})
        self.assertEqual(self.parser.parse("close chrome"), {"type": "close", "target": "chrome"})


class TestAppLauncher(unittest.TestCase):
    def setUp(self):
        self.launcher = AppLauncher()

    def test_aliases(self):
        self.assertEqual(self.launcher._resolve("google chrome"), "chrome")
        self.assertEqual(self.launcher._resolve("command prompt"), "cmd")
        self.assertEqual(self.launcher._resolve("vs code"), "vscode")
        self.assertEqual(self.launcher._resolve("visual studio code"), "vscode")
        self.assertEqual(self.launcher._resolve("file explorer"), "explorer")

    def test_executable_resolution(self):
        notepad_exe = _resolve_executable("notepad.exe")
        self.assertIsNotNone(notepad_exe)
        self.assertTrue(os.path.isfile(notepad_exe))

        cmd_exe = _resolve_executable("cmd.exe")
        self.assertIsNotNone(cmd_exe)
        self.assertTrue(os.path.isfile(cmd_exe))

    @patch("subprocess.Popen")
    def test_open_app(self, mock_popen):
        with patch("os.startfile", create=True) as mock_startfile:
            res = self.launcher.open("notepad")
            self.assertEqual(res, "Opening notepad.")
            self.assertTrue(mock_popen.called or mock_startfile.called)


class TestWebLauncher(unittest.TestCase):
    def setUp(self):
        self.web = WebLauncher()

    @patch("webbrowser.get")
    def test_search_default_engine(self, mock_get):
        mock_chrome = MagicMock()
        mock_get.return_value = mock_chrome
        res = self.web.search("python tutorial")
        self.assertIn("Searching for python tutorial on google", res)
        mock_chrome.open.assert_called_once()
        called_url = mock_chrome.open.call_args[0][0]
        self.assertIn("google.com/search?q=python%20tutorial", called_url)

    @patch("webbrowser.get")
    def test_search_named_engine(self, mock_get):
        mock_chrome = MagicMock()
        mock_get.return_value = mock_chrome
        res = self.web.search("lofi", engine="youtube")
        self.assertIn("Searching for lofi on youtube", res)
        mock_chrome.open.assert_called_once()
        called_url = mock_chrome.open.call_args[0][0]
        self.assertIn("youtube.com/results?search_query=lofi", called_url)


class TestUtilityEngine(unittest.TestCase):
    def setUp(self):
        self.utils = UtilityEngine()

    def test_time_and_date(self):
        self.assertIn("The time is currently", self.utils.get_time())
        self.assertIn("Today is", self.utils.get_date())

    def test_joke(self):
        joke = self.utils.get_joke()
        self.assertIsInstance(joke, str)
        self.assertGreater(len(joke), 10)

    def test_calculate(self):
        self.assertEqual(self.utils.calculate("5 plus 10"), "The answer is 15.")
        self.assertEqual(self.utils.calculate("12 times 8"), "The answer is 96.")
        self.assertEqual(self.utils.calculate("100 divided by 4"), "The answer is 25.")
        self.assertEqual(self.utils.calculate("sqrt(144)"), "The answer is 12.")
        self.assertEqual(self.utils.calculate("10 / 0"), "Division by zero is not allowed.")


class TestHealthEngine(unittest.TestCase):
    def setUp(self):
        self.health = HealthEngine()

    def test_metrics(self):
        self.assertIn("CPU utilization", self.health.get_cpu())
        self.assertIn("RAM", self.health.get_ram())
        self.assertIn("storage space", self.health.get_disk())
        battery = self.health.get_battery()
        self.assertTrue("Battery is at" in battery or "No battery detected" in battery)


class TestNotesEngine(unittest.TestCase):
    def setUp(self):
        self.notes = NotesEngine()

    def test_notes_lifecycle(self):
        self.notes.clear_notes()
        add_res = self.notes.add_note("Buy coffee beans")
        self.assertIn("Noted: Buy coffee beans", add_res)

        read_res = self.notes.read_notes()
        self.assertIn("Buy coffee beans", read_res)

        clear_res = self.notes.clear_notes()
        self.assertEqual(clear_res, "All notes cleared.")


class TestJarvisBrain(unittest.TestCase):
    def setUp(self):
        self.brain = JarvisBrain(speak_callback=lambda x: None)

    def tearDown(self):
        self.brain.shutdown()

    def test_brain_respond(self):
        self.assertIn("The time is currently", self.brain.respond("what time is it"))
        self.assertIn("The answer is 42", self.brain.respond("calculate 6 times 7"))
        self.assertIn("CPU utilization", self.brain.respond("check cpu"))
        self.assertIn("Here's what I can do", self.brain.respond("help"))


if __name__ == "__main__":
    unittest.main()

"""Web search using config/web_registry.json."""
from __future__ import annotations

import json
import os
import urllib.parse
import webbrowser

from jarvis.logger import get_logger

log = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class WebLauncher:
    _DEFAULT_ENGINES = {
        "google": "https://www.google.com/search?q={query}",
        "youtube": "https://www.youtube.com/results?search_query={query}",
        "wikipedia": "https://en.wikipedia.org/wiki/Special:Search?search={query}",
    }

    def __init__(self, registry_path: str | None = None) -> None:
        path = registry_path or os.path.join(_BASE_DIR, "config", "web_registry.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.engines = json.load(f).get("search_engines", self._DEFAULT_ENGINES)
        except Exception as exc:
            log.warning("Could not load %s (%s), using defaults", path, exc)
            self.engines = dict(self._DEFAULT_ENGINES)

        # Ensure wikipedia always available even if config lacks it.
        self.engines.setdefault("wikipedia", self._DEFAULT_ENGINES["wikipedia"])
        # Normalize legacy "{query}"-less URLs to accept a query suffix.
        for name, url in list(self.engines.items()):
            if "{query}" not in url:
                self.engines[name] = url.rstrip("=") + "{query}" if url.endswith("=") else url + "{query}"

        try:
            with open(os.path.join(_BASE_DIR, "config", "settings.json"), "r", encoding="utf-8") as f:
                bcfg = json.load(f).get("browser", {})
                chrome_path = bcfg.get("chrome_path", "C:/Program Files/Google/Chrome/Application/chrome.exe")
                self.default_engine = bcfg.get("default_search_engine", "google").lower()
        except Exception:
            chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
            self.default_engine = "google"
        try:
            webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(chrome_path))
        except Exception as exc:
            log.debug("Could not register Chrome: %s", exc)

    def search(self, query: str, engine: str | None = None) -> str:
        engine = (engine or self.default_engine or "google").lower().strip()
        query = (query or "").strip()
        if not query:
            return "What would you like to search for?"
        if engine not in self.engines:
            available = ", ".join(sorted(self.engines))
            return f"I don't have {engine} configured. Available: {available}."

        search_url = self.engines[engine].replace("{query}", urllib.parse.quote(query))
        try:
            try:
                webbrowser.get("chrome").open(search_url)
            except webbrowser.Error:
                webbrowser.open(search_url)
        except Exception as exc:
            log.exception("Search failed")
            return f"I could not search for {query}: {exc}"
        return f"Searching for {query} on {engine}."

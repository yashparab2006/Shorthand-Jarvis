"""Offline-key knowledge engine — Wikipedia summaries (internet, no API key)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from jarvis.logger import get_logger

log = get_logger(__name__)

_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"


class KnowledgeEngine:
    def wikipedia(self, topic: str, sentences: int = 2) -> str:
        topic = topic.strip().rstrip("?.!")
        if not topic:
            return "What should I look up on Wikipedia?"
        url = _API + urllib.parse.quote(topic.replace(" ", "_"))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JarvisAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
        except Exception as exc:
            log.warning("Wikipedia lookup failed for %r: %s", topic, exc)
            return f"I couldn't reach Wikipedia for '{topic}'. Check your internet connection."
        if data.get("type") == "disambiguation":
            return f"'{topic}' has multiple meanings on Wikipedia. Try being more specific."
        extract = (data.get("extract") or "").strip()
        if not extract:
            return f"I found no Wikipedia article for '{topic}'."
        # Trim to N sentences for comfortable speech.
        import re as _re

        parts = _re.split(r"(?<=[.!?])\s+", extract)
        short = " ".join(parts[: max(1, sentences)]).strip()
        # Spoken answers shouldn't include awkward bracket refs.
        short = _re.sub(r"\s*\[[^\]]*\]", "", short)
        if len(short) > 450:
            short = short[:447].rsplit(" ", 1)[0] + "..."
        return short

import re

_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100,
}

_NUM_PATTERN = r"(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"


def _to_number(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token)


def _clean_target(raw: str) -> str:
    """Normalize STT-noisy targets: 'the note-pad please' -> 'note pad'."""
    t = raw.strip().lower()
    t = re.sub(r"^(?:the|my|up|an?)\s+", "", t)  # 'open up youtube', 'close the tab'
    t = re.sub(r"\s+(?:please|app|window|website|tab|program)$", "", t)
    t = re.sub(r"[-_]+", " ", t).strip()
    return t


class LauncherParser:
    def parse(self, text: str) -> dict | None:
        if not text:
            return None

        clean_text = text.strip().lower()
        if clean_text in ("jarvis", "hey jarvis", "hi jarvis", "ok jarvis"):
            return {"type": "conversation", "action": "greeting"}
        clean_text = re.sub(r"^(?:hey\s+|hi\s+)?jarvis\b[,!\s]*", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"^(?:please|could you|can you|tell me)\s+", "", clean_text, flags=re.IGNORECASE).strip()

        # 0. Conversational Intents
        if re.match(r"^(?:hello|hi|hey|greetings|good morning|good afternoon|good evening|good day)\b", clean_text):
            return {"type": "conversation", "action": "greeting"}
        if re.match(r"^(?:how are you|how are things|how are you doing|how r u|how is it going|how are you feeling)\??$", clean_text):
            return {"type": "conversation", "action": "status"}
        if re.match(r"^(?:who are you|what are you|what is your name|who made you|introduce yourself)\??$", clean_text):
            return {"type": "conversation", "action": "identity"}
        if re.match(r"^(?:thank you|thanks|thanks a lot|thank you so much|appreciate it)\b", clean_text):
            return {"type": "conversation", "action": "gratitude"}
        if re.match(r"^(?:bye|goodbye|see you|see you later|good night)\b", clean_text):
            return {"type": "conversation", "action": "farewell"}

        # 1. Flexible Reminders (digits or number words: 'in five minutes')
        m_remind_a = re.match(rf"^after\s+({_NUM_PATTERN})\s+(minute|minutes|hour|hours)\s+(?:tell me|remind me)(?:\s+that|\s+to)?\s+(.+)$", clean_text)
        if m_remind_a:
            n = _to_number(m_remind_a.group(1))
            if n is not None: return {"type": "reminder", "amount": n, "unit": m_remind_a.group(2), "task": m_remind_a.group(3).strip()}

        m_remind_b = re.match(rf"^(?:remind me|tell me|set a reminder)\s+(?:in|for)\s+({_NUM_PATTERN})\s+(minute|minutes|hour|hours)\s+(?:to|that)?\s+(.+)$", clean_text)
        if m_remind_b:
            n = _to_number(m_remind_b.group(1))
            if n is not None: return {"type": "reminder", "amount": n, "unit": m_remind_b.group(2), "task": m_remind_b.group(3).strip()}

        m_remind_c = re.match(rf"^(?:remind me to|set a reminder to|tell me to)\s+(.+)\s+(?:in|after|for)\s+({_NUM_PATTERN})\s+(minute|minutes|hour|hours)$", clean_text)
        if m_remind_c:
            n = _to_number(m_remind_c.group(2))
            if n is not None: return {"type": "reminder", "task": m_remind_c.group(1).strip(), "amount": n, "unit": m_remind_c.group(3)}

        # 1b. Timers (one-shot countdowns)
        m_timer = re.match(rf"^(?:set|start)?\s*(?:a\s+)?timer\s+(?:for\s+|of\s+)?({_NUM_PATTERN})\s+(second|seconds|minute|minutes|hour|hours)$", clean_text.strip())
        if m_timer:
            n = _to_number(m_timer.group(1))
            if n is not None: return {"type": "timer", "amount": n, "unit": m_timer.group(2)}

        # 1c. List reminders
        if (re.match(r"^(?:list|show|read|what are|do i have)(?:\s+my|\s+any)?\s+reminders?\??$", clean_text)
                or clean_text in ("my reminders", "reminders", "any reminders", "show reminders")):
            return {"type": "list_reminders"}

        # 1c2. Notes ('note that buy milk', 'read my notes', 'clear my notes')
        m_note_add = re.match(r"^(?:note|note down|take a note|add a note|create a note|make a note|remember)(?:\s+that|\s+to)?\s+(.+)$", clean_text)
        if m_note_add and m_note_add.group(1).strip():
            return {"type": "note_add", "text": m_note_add.group(1).strip()}
        if (re.match(r"^(?:read|show|list|what are)(?:\s+my)?\s+notes?\??$", clean_text)
                or clean_text in ("my notes", "notes", "show notes")):
            return {"type": "note_list"}
        if re.match(r"^(?:clear|delete|remove)(?:\s+my|\s+all)?\s+notes?$", clean_text):
            return {"type": "note_clear"}

        # 1d. Help
        if re.match(r"^(help|help me|what can you do|commands|features|how do i use you)\??$", clean_text):
            return {"type": "utility", "action": "help"}

        # 1e. Calculator ('calculate 12 times 8', 'what is 15 plus 7?')
        _MATH_KW = r"\b(sqrt|cbrt|sin|sine|cos|cosine|tan|tangent|log|ln|factorial|pi\b|square root|cube root)"
        m_calc_kw = re.match(r"^(?:calculate|compute|solve|math|evaluate)\s+(.+)$", clean_text)
        if m_calc_kw and (re.search(r"\d", m_calc_kw.group(1)) or re.search(_MATH_KW, m_calc_kw.group(1))):
            return {"type": "calculate", "expression": m_calc_kw.group(1).strip()}
        m_calc_what = re.match(r"^(?:what is|what's|how much is)\s+(.+)$", clean_text)
        if m_calc_what and (re.search(r"\d", m_calc_what.group(1)) or re.search(_MATH_KW, m_calc_what.group(1))) and re.search(
                r"[+\-*/%()]|\b(plus|minus|times|multiplied|divided|divide|over|power|percent|sqrt|root|sin|sine|cos|cosine|tan|tangent|log|factorial|pi)\b",
                m_calc_what.group(1)):
            return {"type": "calculate", "expression": m_calc_what.group(1).strip()}

        # 2. Health Checks
        if re.search(r"\b(battery|charge)\b", clean_text): return {"type": "health", "action": "battery"}
        if re.search(r"\b(cpu|processor)\b", clean_text): return {"type": "health", "action": "cpu"}
        if re.search(r"\b(ram|memory)\b", clean_text): return {"type": "health", "action": "ram"}
        if re.search(r"\b(disk|storage)\b", clean_text): return {"type": "health", "action": "disk"}

        # 3. Utilities (FIXED JOKES: Now accepts "joke" or "jokes")
        if re.search(r"\b(time|what time)\b", clean_text): return {"type": "utility", "action": "time"}
        if re.search(r"\b(date|what day)\b", clean_text): return {"type": "utility", "action": "date"}
        if re.search(r"\b(joke|jokes|funny)\b", clean_text): return {"type": "utility", "action": "joke"}
        if re.search(r"\b(good morning|good afternoon|good evening)\b", clean_text): return {"type": "utility", "action": "personal_opening"}

        # 4. System & Hardware Controls (brightness first: 'turn down brightness'
        # must not match generic volume patterns)
        m_bright = re.search(rf"\bbrightness\s*(?:to\s*)?({_NUM_PATTERN})\b", clean_text)
        if m_bright:
            n = _to_number(m_bright.group(1))
            if n is not None: return {"type": "system", "action": "set_brightness", "value": n}

        if re.search(r"\b(brightness up|increase brightness|brighter|turn up brightness|turn down brightness|brightness down|decrease brightness|dimmer)\b", clean_text):
            if re.search(r"\b(up|increase|brighter)\b", clean_text): return {"type": "system", "action": "brightness_up"}
            return {"type": "system", "action": "brightness_down"}

        m_vol = re.search(rf"\bvolume\s*(?:to\s*)?({_NUM_PATTERN})\b", clean_text)
        if m_vol:
            n = _to_number(m_vol.group(1))
            if n is not None: return {"type": "system", "action": "set_volume", "value": n}

        if "brightness" not in clean_text:
            if re.search(r"\b(increase|turn up|raise|louder|volume up)\b", clean_text): return {"type": "system", "action": "volume_up"}
            if re.search(r"\b(decrease|turn down|lower|quieter|volume down)\b", clean_text): return {"type": "system", "action": "volume_down"}

        if re.search(r"\b(mute)\b", clean_text): return {"type": "system", "action": "mute"}
        if re.search(r"\b(unmute)\b", clean_text): return {"type": "system", "action": "unmute"}

        m_media = re.search(r"\b(play|pause|next|previous)\s+(?:music|song|track|media)\b", clean_text)
        if m_media: return {"type": "system", "action": "media", "command": m_media.group(1)}
        if re.match(r"^(?:play|pause|stop\s+music)$", clean_text): return {"type": "system", "action": "media", "command": "pause"}

        if re.search(r"\b(take a screenshot|screenshot|screen capture|capture the screen|capture screen)\b", clean_text):
            return {"type": "system", "action": "screenshot"}
        if re.search(r"\block\b", clean_text) and re.search(r"\b(computer|pc|system|workstation|screen)\b", clean_text):
            return {"type": "system", "action": "lock"}

        # 4b. Wikipedia ('who is Einstein?', 'what is photosynthesis?')
        # Health/utility/calculator already claimed their 'what is...' cases above.
        m_wiki = re.match(r"^(?:who is|who was|wikipedia|look up|about)\s+(.+?)\??$", clean_text)
        if m_wiki and m_wiki.group(1).strip():
            return {"type": "knowledge", "topic": m_wiki.group(1).strip()}
        m_what = re.match(r"^what (?:is|are) (?:the )?(.+?)\??$", clean_text)
        if m_what and m_what.group(1).strip():
            return {"type": "knowledge", "topic": m_what.group(1).strip()}

        # 5. Launchers & Search (STT-tolerant)
        m_close = re.match(r"^(?:close|kill|stop|exit)\s+(.+)$", clean_text)
        if m_close: return {"type": "close", "target": _clean_target(m_close.group(1))}

        # 5a. Web Search
        m_search_on = re.match(r"^(?:search|find)(?:\s+for)?\s+(.+?)\s+(?:on|in)\s+([a-zA-Z0-9]+)$", clean_text)
        if m_search_on:
            query = re.sub(r"^for\s+", "", m_search_on.group(1).strip())
            return {"type": "search", "engine": m_search_on.group(2).lower(), "query": query}

        m_search_eng = re.match(r"^(?:search|find)\s+([a-zA-Z0-9]+)\s+for\s+(.+)$", clean_text)
        if m_search_eng and m_search_eng.group(1).lower() in ("google", "youtube", "wikipedia", "bing", "yahoo", "duckduckgo"):
            return {"type": "search", "engine": m_search_eng.group(1).lower(), "query": m_search_eng.group(2).strip()}

        m_google = re.match(r"^google\s+(.+)$", clean_text)
        if m_google and m_google.group(1).strip() not in ("chrome",):
            return {"type": "search", "engine": "google", "query": m_google.group(1).strip()}

        m_search_def = re.match(r"^(?:search|find)(?:\s+for)?\s+(.+)$", clean_text)
        if m_search_def:
            return {"type": "search", "engine": None, "query": m_search_def.group(1).strip()}

        m_open = re.match(r"^(?:open|launch|start)\s+(.+)$", clean_text)
        if m_open: return {"type": "open", "target": _clean_target(m_open.group(1))}

        return None

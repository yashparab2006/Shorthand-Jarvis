"""Modern, Futuristic Cyberpunk/Iron Man JARVIS Desktop Frontend GUI.
Built with CustomTkinter for high-DPI crisp rendering and smooth responsiveness.
"""
from __future__ import annotations

import math
import os
import threading
import time
from datetime import datetime
import tkinter as tk

import customtkinter as ctk
import psutil

from jarvis.brain import JarvisBrain
from jarvis.voice.engine import VoiceEngine
from jarvis.modules.health import HealthEngine
from jarvis.modules.utilities import UtilityEngine
from jarvis.modules.notes import NotesEngine
from jarvis.modules.reminders import ReminderEngine
from jarvis.logger import get_logger

log = get_logger(__name__)

# Configure CustomTkinter aesthetics
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Theme Palette (Cyberpunk / Iron Man HUD)
CLR_BG_DARK = "#0a0e17"
CLR_PANEL = "#111827"
CLR_CARD = "#1a2333"
CLR_CARD_BORDER = "#223147"
CLR_CYAN = "#00f2fe"
CLR_CYAN_DIM = "#00adb5"
CLR_BLUE = "#1f6feb"
CLR_BLUE_ACCENT = "#388bfd"
CLR_GREEN = "#10b981"
CLR_AMBER = "#f59e0b"
CLR_RED = "#ef4444"
CLR_TEXT_PRIMARY = "#f8fafc"
CLR_TEXT_MUTED = "#94a3b8"


class ArcReactorCanvas(tk.Canvas):
    """Animated Arc Reactor HUD widget that pulses and rotates based on system state."""

    def __init__(self, parent, size: int = 100, **kwargs):
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=CLR_PANEL,
            highlightthickness=0,
            **kwargs,
        )
        self.size = size
        self.center = size // 2
        self.angle = 0
        self.pulse = 0.0
        self.pulse_dir = 1
        self.state = "idle"  # idle | listening | speaking | processing
        self._running = True
        self._animate()

    def set_state(self, state: str):
        self.state = state

    def _animate(self):
        if not self._running:
            return
        self.delete("all")
        c = self.center
        r_outer = c - 6
        r_mid = c - 18
        r_inner = c - 28

        # Color mapping based on state
        if self.state == "listening":
            glow_col = CLR_AMBER
            speed = 4
        elif self.state == "speaking":
            glow_col = CLR_GREEN
            speed = 6
        elif self.state == "processing":
            glow_col = CLR_BLUE_ACCENT
            speed = 8
        else:  # idle
            glow_col = CLR_CYAN
            speed = 1.5

        self.angle = (self.angle + speed) % 360
        self.pulse += 0.05 * self.pulse_dir
        if self.pulse > 1.0:
            self.pulse = 1.0
            self.pulse_dir = -1
        elif self.pulse < 0.0:
            self.pulse = 0.0
            self.pulse_dir = 1

        # Pulsing outer aura
        pulse_r = r_outer + int(self.pulse * 3)
        self.create_oval(c - pulse_r, c - pulse_r, c + pulse_r, c + pulse_r, outline="#14283b", width=1)

        # Outer ring
        self.create_oval(c - r_outer, c - r_outer, c + r_outer, c + r_outer, outline=glow_col, width=2)

        # Rotating tick marks
        num_ticks = 12
        for i in range(num_ticks):
            deg = math.radians(self.angle + (i * (360 / num_ticks)))
            x1 = c + (r_outer - 5) * math.cos(deg)
            y1 = c + (r_outer - 5) * math.sin(deg)
            x2 = c + (r_outer - 1) * math.cos(deg)
            y2 = c + (r_outer - 1) * math.sin(deg)
            self.create_line(x1, y1, x2, y2, fill=glow_col, width=2)

        # Middle ring with dashes
        self.create_oval(c - r_mid, c - r_mid, c + r_mid, c + r_mid, outline="#005577", width=1)

        # Counter-rotating triangular crosshairs
        rad_rev = math.radians(-self.angle * 1.5)
        for j in range(3):
            sub_rad = rad_rev + j * (2 * math.pi / 3)
            x = c + r_mid * math.cos(sub_rad)
            y = c + r_mid * math.sin(sub_rad)
            self.create_line(c, c, x, y, fill=glow_col, width=1, dash=(2, 2))

        # Glowing core
        core_r = max(4, int(r_inner * (0.65 + self.pulse * 0.25)))
        self.create_oval(c - core_r, c - core_r, c + core_r, c + core_r, fill=glow_col, outline="#ffffff", width=1)

        # Re-schedule frame (~30 fps)
        self.after(33, self._animate)

    def stop(self):
        self._running = False


class JarvisGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("J.A.R.V.I.S. // AI Assistant Interface")
        self.geometry("1100x720")
        self.minsize(950, 600)
        self.configure(fg_color=CLR_BG_DARK)

        # State flags
        self.voice_output_enabled = tk.BooleanVar(value=True)
        self.is_listening = False
        self.is_speaking = False

        # Initialize Backend Services
        self._init_backend()

        # Build User Interface
        self._build_layout()

        # Start background telemetry loop
        self._start_telemetry_loop()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _init_backend(self):
        """Initialize brain and voice engine in background."""
        self.health = HealthEngine()
        self.notes = NotesEngine()
        self.utilities = UtilityEngine()

        # Safe voice engine for TTS / Listening
        try:
            self.voice = VoiceEngine(rate=175)
        except Exception as exc:
            log.warning("VoiceEngine init issue: %s", exc)
            self.voice = None

        # Speak callback for JarvisBrain that updates GUI and optionally speaks
        def speak_cb(text: str):
            self.after(0, lambda: self._add_jarvis_message(text))
            if self.voice_output_enabled.get() and self.voice:
                self.after(0, lambda: self._set_status("SPEAKING...", "speaking"))
                try:
                    self.voice.speak(text, wait=True)
                finally:
                    self.after(0, lambda: self._set_status("ONLINE // READY", "idle"))

        self.brain = JarvisBrain(speak_callback=speak_cb)

    def _build_layout(self):
        # Configure main grid weights (2 columns: left sidebar, right chat/dock)
        self.grid_columnconfigure(0, weight=0, minsize=280)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # -------------------------------------------------------------
        # LEFT COLUMN: System Telemetry Sidebar
        # -------------------------------------------------------------
        self.sidebar = ctk.CTkFrame(self, fg_color=CLR_PANEL, corner_radius=0, border_width=1, border_color=CLR_CARD_BORDER)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Sidebar Title
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.pack(fill="x", padx=16, pady=(16, 12))

        lbl_sys = ctk.CTkLabel(
            title_frame,
            text="SYSTEM TELEMETRY",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color=CLR_CYAN,
        )
        lbl_sys.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_frame,
            text="HARDWARE METRICS & HUD",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=CLR_TEXT_MUTED,
        )
        lbl_sub.pack(anchor="w")

        # Telemetry Cards Container
        self.telemetry_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.telemetry_frame.pack(fill="x", padx=12, pady=4)

        # 1. CPU Card
        self.card_cpu = self._create_metric_card(self.telemetry_frame, "CPU UTILIZATION", "0%", CLR_CYAN)
        self.bar_cpu = self.card_cpu["bar"]
        self.val_cpu = self.card_cpu["val"]

        # 2. RAM Card
        self.card_ram = self._create_metric_card(self.telemetry_frame, "MEMORY (RAM)", "0 GB / 0%", CLR_BLUE_ACCENT)
        self.bar_ram = self.card_ram["bar"]
        self.val_ram = self.card_ram["val"]

        # 3. Battery Card
        self.card_bat = self._create_metric_card(self.telemetry_frame, "BATTERY POWER", "--", CLR_GREEN)
        self.bar_bat = self.card_bat["bar"]
        self.val_bat = self.card_bat["val"]

        # 4. Storage Card
        self.card_dsk = self._create_metric_card(self.telemetry_frame, "STORAGE DRIVE", "-- GB Free", CLR_AMBER)
        self.bar_dsk = self.card_dsk["bar"]
        self.val_dsk = self.card_dsk["val"]

        # Separator
        sep = ctk.CTkFrame(self.sidebar, fg_color=CLR_CARD_BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=12)

        # Quick Action Shortcuts
        lbl_actions = ctk.CTkLabel(
            self.sidebar,
            text="QUICK COMMANDS",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=CLR_CYAN,
        )
        lbl_actions.pack(anchor="w", padx=16, pady=(0, 6))

        actions_grid = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        actions_grid.pack(fill="x", padx=12, pady=4)
        actions_grid.grid_columnconfigure((0, 1), weight=1)

        btn_screen = self._create_action_btn(actions_grid, "📷 Screenshot", "take a screenshot")
        btn_screen.grid(row=0, column=0, padx=3, pady=3, sticky="ew")

        btn_notes = self._create_action_btn(actions_grid, "📝 Read Notes", "read my notes")
        btn_notes.grid(row=0, column=1, padx=3, pady=3, sticky="ew")

        btn_chrome = self._create_action_btn(actions_grid, "🌐 Chrome", "open chrome")
        btn_chrome.grid(row=1, column=0, padx=3, pady=3, sticky="ew")

        btn_code = self._create_action_btn(actions_grid, "💻 VS Code", "open vscode")
        btn_code.grid(row=1, column=1, padx=3, pady=3, sticky="ew")

        btn_time = self._create_action_btn(actions_grid, "⏰ Date & Time", "what time is it")
        btn_time.grid(row=2, column=0, padx=3, pady=3, sticky="ew")

        btn_joke = self._create_action_btn(actions_grid, "🃏 Joke", "tell me a joke")
        btn_joke.grid(row=2, column=1, padx=3, pady=3, sticky="ew")

        # Sidebar Footer: Timestamp & Version
        footer_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=16, pady=12)

        self.lbl_clock = ctk.CTkLabel(
            footer_frame,
            text="00:00:00",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=CLR_TEXT_PRIMARY,
        )
        self.lbl_clock.pack(anchor="w")

        lbl_ver = ctk.CTkLabel(
            footer_frame,
            text="JARVIS OS v2.0 // MARK VII",
            font=ctk.CTkFont(family="Consolas", size=8),
            text_color=CLR_TEXT_MUTED,
        )
        lbl_ver.pack(anchor="w")

        # -------------------------------------------------------------
        # RIGHT COLUMN: Header, Chat Stream, Input Dock
        # -------------------------------------------------------------
        self.main_container = ctk.CTkFrame(self, fg_color=CLR_BG_DARK, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_container.grid_rowconfigure(1, weight=1)  # Chat expands
        self.main_container.grid_columnconfigure(0, weight=1)

        # 1. TOP HEADER HUD
        self.header_frame = ctk.CTkFrame(self.main_container, fg_color=CLR_PANEL, corner_radius=0, height=80,
                                         border_width=1, border_color=CLR_CARD_BORDER)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header_frame.grid_columnconfigure(1, weight=1)

        # Arc Reactor Canvas
        self.reactor = ArcReactorCanvas(self.header_frame, size=70)
        self.reactor.grid(row=0, column=0, padx=(16, 10), pady=6, sticky="w")

        # Center Status Title
        header_text_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        header_text_frame.grid(row=0, column=1, sticky="w", padx=4, pady=6)

        lbl_brand = ctk.CTkLabel(
            header_text_frame,
            text="J.A.R.V.I.S. // AI ASSISTANT",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=CLR_CYAN,
        )
        lbl_brand.pack(anchor="w")

        self.lbl_status = ctk.CTkLabel(
            header_text_frame,
            text="● ONLINE // AWAITING COMMAND",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=CLR_GREEN,
        )
        self.lbl_status.pack(anchor="w")

        # Header Right Controls (Speech output toggle & Clear button)
        header_ctrls = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        header_ctrls.grid(row=0, column=2, sticky="e", padx=16, pady=6)

        self.sw_voice = ctk.CTkSwitch(
            header_ctrls,
            text="Voice Output",
            variable=self.voice_output_enabled,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=CLR_TEXT_MUTED,
            progress_color=CLR_CYAN,
        )
        self.sw_voice.pack(side="left", padx=8)

        btn_clear = ctk.CTkButton(
            header_ctrls,
            text="Clear Log",
            width=70,
            height=28,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=CLR_CARD,
            hover_color=CLR_CARD_BORDER,
            text_color=CLR_TEXT_MUTED,
            command=self._clear_chat,
        )
        btn_clear.pack(side="left", padx=4)

        # 2. CHAT STREAM (Scrollable Frame)
        self.chat_frame = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color=CLR_BG_DARK,
            corner_radius=0,
        )
        self.chat_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # Initial Welcome Message from Jarvis
        self._add_jarvis_message(
            f"{self.utilities.get_personal_opening()}\n\n"
            "All systems are online and responsive. You can type instructions below, "
            "click quick action buttons on the left, or press the 'Voice Input' button to speak."
        )

        # 3. BOTTOM INPUT DOCK
        self.dock_frame = ctk.CTkFrame(self.main_container, fg_color=CLR_PANEL, corner_radius=0, height=64,
                                       border_width=1, border_color=CLR_CARD_BORDER)
        self.dock_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        self.dock_frame.grid_columnconfigure(0, weight=1)

        input_box = ctk.CTkFrame(self.dock_frame, fg_color="transparent")
        input_box.pack(fill="x", padx=16, pady=12)

        self.txt_input = ctk.CTkEntry(
            input_box,
            placeholder_text="Enter command or ask Jarvis anything... (Press Enter to send)",
            font=ctk.CTkFont(size=13),
            fg_color=CLR_CARD,
            border_color=CLR_CARD_BORDER,
            text_color=CLR_TEXT_PRIMARY,
            height=42,
            corner_radius=8,
        )
        self.txt_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.txt_input.bind("<Return>", lambda event: self._on_send_text())

        # Voice Input Button
        self.btn_mic = ctk.CTkButton(
            input_box,
            text="🎙 Voice",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            width=90,
            height=42,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color=CLR_CYAN,
            border_width=1,
            border_color=CLR_CYAN,
            corner_radius=8,
            command=self._on_voice_click,
        )
        self.btn_mic.pack(side="left", padx=(0, 8))

        # Send Button
        self.btn_send = ctk.CTkButton(
            input_box,
            text="Send ➤",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            width=85,
            height=42,
            fg_color=CLR_BLUE,
            hover_color=CLR_BLUE_ACCENT,
            text_color="#ffffff",
            corner_radius=8,
            command=self._on_send_text,
        )
        self.btn_send.pack(side="left")

    def _create_metric_card(self, parent, title: str, initial_val: str, bar_color: str) -> dict:
        card = ctk.CTkFrame(parent, fg_color=CLR_CARD, corner_radius=6, border_width=1, border_color=CLR_CARD_BORDER)
        card.pack(fill="x", pady=4)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(6, 2))

        lbl_t = ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=CLR_TEXT_MUTED,
        )
        lbl_t.pack(side="left")

        lbl_v = ctk.CTkLabel(
            header,
            text=initial_val,
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=CLR_TEXT_PRIMARY,
        )
        lbl_v.pack(side="right")

        bar = ctk.CTkProgressBar(card, height=6, corner_radius=3, progress_color=bar_color, fg_color="#0f172a")
        bar.pack(fill="x", padx=10, pady=(2, 8))
        bar.set(0.0)

        return {"card": card, "val": lbl_v, "bar": bar}

    def _create_action_btn(self, parent, text: str, command_str: str) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            font=ctk.CTkFont(size=11),
            height=30,
            fg_color=CLR_CARD,
            hover_color="#27354a",
            text_color=CLR_TEXT_PRIMARY,
            border_width=1,
            border_color=CLR_CARD_BORDER,
            corner_radius=6,
            command=lambda: self._dispatch_command(command_str),
        )

    # -----------------------------------------------------------------
    # Telemetry Polling (CPU, RAM, Battery, Disk)
    # -----------------------------------------------------------------
    def _start_telemetry_loop(self):
        def loop():
            while getattr(self, "_running", True):
                try:
                    # CPU
                    cpu_p = psutil.cpu_percent(interval=0.5)

                    # RAM
                    mem = psutil.virtual_memory()
                    ram_gb = round(mem.used / (1024**3), 1)
                    ram_tot = round(mem.total / (1024**3), 1)
                    ram_p = mem.percent

                    # Battery
                    bat = psutil.sensors_battery()
                    bat_p = bat.percent if bat else 100
                    bat_plug = "Plugged" if bat and bat.power_plugged else "Discharging" if bat else "Desktop"

                    # Disk
                    disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
                    free_gb = round(disk.free / (1024**3), 1)
                    disk_p = disk.percent

                    # Current time
                    now_str = datetime.now().strftime("%I:%M:%S %p")

                    self.after(0, lambda: self._update_telemetry_ui(cpu_p, ram_gb, ram_tot, ram_p, bat_p, bat_plug, free_gb, disk_p, now_str))
                except Exception as exc:
                    log.debug("Telemetry update error: %s", exc)
                time.sleep(1.5)

        self._running = True
        self._telemetry_thread = threading.Thread(target=loop, daemon=True)
        self._telemetry_thread.start()

    def _update_telemetry_ui(self, cpu_p, ram_gb, ram_tot, ram_p, bat_p, bat_plug, free_gb, disk_p, now_str):
        if not self.winfo_exists():
            return
        self.val_cpu.configure(text=f"{cpu_p:.1f}%")
        self.bar_cpu.set(cpu_p / 100.0)

        self.val_ram.configure(text=f"{ram_gb}GB / {ram_p:.0f}%")
        self.bar_ram.set(ram_p / 100.0)

        self.val_bat.configure(text=f"{bat_p}% ({bat_plug})")
        self.bar_bat.set(bat_p / 100.0)

        self.val_dsk.configure(text=f"{free_gb} GB Free")
        self.bar_dsk.set(disk_p / 100.0)

        self.lbl_clock.configure(text=now_str)

    # -----------------------------------------------------------------
    # Chat Bubble Rendering
    # -----------------------------------------------------------------
    def _add_user_message(self, text: str):
        now = datetime.now().strftime("%I:%M %p")
        row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        row.pack(fill="x", pady=6, padx=8)

        bubble = ctk.CTkFrame(
            row,
            fg_color="#1e293b",
            corner_radius=10,
            border_width=1,
            border_color="#3b82f6",
        )
        bubble.pack(side="right", padx=(80, 0), anchor="e")

        lbl_hdr = ctk.CTkLabel(
            bubble,
            text=f"YOU // {now}",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=CLR_BLUE_ACCENT,
        )
        lbl_hdr.pack(anchor="e", padx=12, pady=(6, 2))

        lbl_body = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(size=12),
            text_color=CLR_TEXT_PRIMARY,
            wraplength=550,
            justify="left",
        )
        lbl_body.pack(anchor="w", padx=12, pady=(0, 8))

        self._scroll_chat_to_bottom()

    def _add_jarvis_message(self, text: str):
        now = datetime.now().strftime("%I:%M %p")
        row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        row.pack(fill="x", pady=6, padx=8)

        bubble = ctk.CTkFrame(
            row,
            fg_color="#0f172a",
            corner_radius=10,
            border_width=1,
            border_color=CLR_CYAN_DIM,
        )
        bubble.pack(side="left", padx=(0, 80), anchor="w")

        lbl_hdr = ctk.CTkLabel(
            bubble,
            text=f"● J.A.R.V.I.S. // {now}",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=CLR_CYAN,
        )
        lbl_hdr.pack(anchor="w", padx=12, pady=(6, 2))

        lbl_body = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(size=12),
            text_color=CLR_TEXT_PRIMARY,
            wraplength=550,
            justify="left",
        )
        lbl_body.pack(anchor="w", padx=12, pady=(0, 8))

        self._scroll_chat_to_bottom()

    def _scroll_chat_to_bottom(self):
        try:
            self.chat_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _clear_chat(self):
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        self._add_jarvis_message("Command history cleared. Systems standing by.")

    def _set_status(self, text: str, state: str):
        self.lbl_status.configure(text=f"● {text}")
        if state == "listening":
            self.lbl_status.configure(text_color=CLR_AMBER)
        elif state == "speaking":
            self.lbl_status.configure(text_color=CLR_GREEN)
        elif state == "processing":
            self.lbl_status.configure(text_color=CLR_BLUE_ACCENT)
        else:
            self.lbl_status.configure(text_color=CLR_CYAN)
        self.reactor.set_state(state)

    # -----------------------------------------------------------------
    # Command Dispatch & Background Execution
    # -----------------------------------------------------------------
    def _on_send_text(self):
        raw = self.txt_input.get().strip()
        if not raw:
            return
        self.txt_input.delete(0, "end")
        self._dispatch_command(raw)

    def _on_voice_click(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.btn_mic.configure(text="🎙 Listening...", fg_color=CLR_AMBER, text_color="#ffffff")
        self._set_status("LISTENING TO MICROPHONE...", "listening")

        def listen_worker():
            try:
                if self.voice:
                    query = self.voice.listen(duration=4.5)
                else:
                    query = ""
            except Exception as exc:
                log.error("Listen worker error: %s", exc)
                query = ""
            finally:
                self.after(0, self._finish_voice_listen, query)

        threading.Thread(target=listen_worker, daemon=True).start()

    def _finish_voice_listen(self, query: str):
        self.is_listening = False
        self.btn_mic.configure(text="🎙 Voice", fg_color="#1e293b", text_color=CLR_CYAN)
        self._set_status("ONLINE // READY", "idle")

        if query:
            self._dispatch_command(query)
        else:
            self._add_jarvis_message("I didn't catch that. Please speak clearly or type your request.")

    def _dispatch_command(self, command: str):
        self._add_user_message(command)
        self._set_status("PROCESSING COMMAND...", "processing")

        def brain_worker():
            try:
                response = self.brain.respond(command)
            except Exception as exc:
                log.exception("Brain respond error: %s", exc)
                response = f"Sorry Sir, an error occurred: {exc}"

            self.after(0, self._handle_response, response)

        threading.Thread(target=brain_worker, daemon=True).start()

    def _handle_response(self, response: str):
        self._add_jarvis_message(response)
        self._set_status("ONLINE // READY", "idle")

        # Speak answer if voice output is enabled
        if self.voice_output_enabled.get() and self.voice:
            def speak_worker():
                self.after(0, lambda: self._set_status("SPEAKING...", "speaking"))
                try:
                    self.voice.speak(response, wait=True)
                finally:
                    self.after(0, lambda: self._set_status("ONLINE // READY", "idle"))

            threading.Thread(target=speak_worker, daemon=True).start()

    # -----------------------------------------------------------------
    # Shutdown / Exit
    # -----------------------------------------------------------------
    def on_closing(self):
        self._running = False
        try:
            self.reactor.stop()
        except Exception:
            pass
        try:
            self.brain.shutdown()
        except Exception:
            pass
        if self.voice:
            try:
                self.voice.shutdown()
            except Exception:
                pass
        self.destroy()


def run_gui():
    app = JarvisGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()


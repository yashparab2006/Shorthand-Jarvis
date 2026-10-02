import ctypes
import screen_brightness_control as sbc
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

class SystemControlEngine:
    def __init__(self) -> None:
        self.VK_MEDIA_NEXT_TRACK = 0xB0
        self.VK_MEDIA_PREV_TRACK = 0xB1
        self.VK_MEDIA_PLAY_PAUSE = 0xB3

    def _get_volume_interface(self):
        devices = AudioUtilities.GetSpeakers()
        # New pycaw (>=2024, e.g. 20251023): EndpointVolume property
        if hasattr(devices, "EndpointVolume"):
            return devices.EndpointVolume
        # Old pycaw: COM Activate
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def get_volume(self) -> int | None:
        try:
            return int(round(self._get_volume_interface().GetMasterVolumeLevelScalar() * 100))
        except Exception:
            return None

    def volume_up(self, step: int = 10) -> str:
        cur = self.get_volume()
        if cur is None:
            return "I could not adjust the volume."
        return self.set_volume(min(100, cur + step))

    def volume_down(self, step: int = 10) -> str:
        cur = self.get_volume()
        if cur is None:
            return "I could not adjust the volume."
        return self.set_volume(max(0, cur - step))

    def set_volume(self, level: int) -> str:
        level = max(0, min(100, level))
        try:
            volume = self._get_volume_interface()
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            volume.SetMute(0, None)
            return f"System volume set to {level} percent."
        except Exception:
            return "I could not adjust the volume."

    def mute_volume(self, mute: bool = True) -> str:
        try:
            volume = self._get_volume_interface()
            volume.SetMute(1 if mute else 0, None)
            return "Audio muted." if mute else "Audio unmuted."
        except Exception:
            return "I could not change the mute state."

    def set_brightness(self, level: int) -> str:
        level = max(0, min(100, level))
        try:
            sbc.set_brightness(level)
            return f"Screen brightness set to {level} percent."
        except Exception:
            return "I could not adjust the screen brightness."

    def _get_brightness(self) -> int | None:
        try:
            vals = sbc.get_brightness()
            return int(vals[0]) if vals else None
        except Exception:
            return None

    def brightness_up(self, step: int = 10) -> str:
        cur = self._get_brightness()
        if cur is None:
            return "I could not adjust the screen brightness."
        return self.set_brightness(min(100, cur + step))

    def brightness_down(self, step: int = 10) -> str:
        cur = self._get_brightness()
        if cur is None:
            return "I could not adjust the screen brightness."
        return self.set_brightness(max(0, cur - step))

    def control_media(self, action: str) -> str:
        action = action.lower()
        try:
            if action in ["play", "pause"]:
                ctypes.windll.user32.keybd_event(self.VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
                return "Toggling media playback."
            elif action == "next":
                ctypes.windll.user32.keybd_event(self.VK_MEDIA_NEXT_TRACK, 0, 0, 0)
                return "Playing next track."
            elif action == "previous":
                ctypes.windll.user32.keybd_event(self.VK_MEDIA_PREV_TRACK, 0, 0, 0)
                return "Playing previous track."
        except Exception:
            return "Failed to execute media control."
        return "Media command not recognized."

    def take_screenshot(self) -> str:
        """Save timestamped screenshot to ~/Pictures/Jarvis/."""
        import os as _os
        from datetime import datetime as _dt

        folder = _os.path.join(_os.path.expanduser("~"), "Pictures", "Jarvis")
        _os.makedirs(folder, exist_ok=True)
        name = _dt.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
        path = _os.path.join(folder, name)

        # 1. Try Windows GDI BitBlt (reliable on Windows without Pillow grabscreen limitations)
        if _os.name == "nt":
            try:
                import ctypes
                from PIL import Image

                user32 = ctypes.windll.user32
                gdi32 = ctypes.windll.gdi32
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)

                hdc_screen = user32.GetDC(0)
                hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
                gdi32.SelectObject(hdc_mem, hbm)
                gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020)

                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", ctypes.c_uint32),
                        ("biWidth", ctypes.c_int32),
                        ("biHeight", ctypes.c_int32),
                        ("biPlanes", ctypes.c_uint16),
                        ("biBitCount", ctypes.c_uint16),
                        ("biCompression", ctypes.c_uint32),
                        ("biSizeImage", ctypes.c_uint32),
                        ("biXPelsPerMeter", ctypes.c_int32),
                        ("biYPelsPerMeter", ctypes.c_int32),
                        ("biClrUsed", ctypes.c_uint32),
                        ("biClrImportant", ctypes.c_uint32),
                    ]

                bi = BITMAPINFOHEADER()
                bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bi.biWidth = w
                bi.biHeight = -h
                bi.biPlanes = 1
                bi.biBitCount = 32
                bi.biCompression = 0

                buf = (ctypes.c_char * (w * h * 4))()
                gdi32.GetDIBits(hdc_mem, hbm, 0, h, ctypes.byref(buf), ctypes.byref(bi), 0)
                img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)

                gdi32.DeleteObject(hbm)
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)

                img.convert("RGB").save(path, "PNG")
                return f"Screenshot saved to {path}."
            except Exception as gdi_exc:
                log.debug("GDI screenshot fallback: %s", gdi_exc)

        # 2. Try pyautogui / Pillow fallback
        try:
            import pyautogui
            pyautogui.screenshot(path)
            return f"Screenshot saved to {path}."
        except Exception as exc:
            return f"I could not take a screenshot: {exc}"

    def lock_workstation(self) -> str:
        try:
            ctypes.windll.user32.LockWorkStation()
            return "Locking your computer."
        except Exception:
            return "I could not lock the computer."
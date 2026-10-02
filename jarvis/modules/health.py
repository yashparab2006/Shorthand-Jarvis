import psutil

class HealthEngine:
    def get_cpu(self) -> str:
        return f"CPU utilization is currently at {psutil.cpu_percent(interval=0.5)} percent."

    def get_ram(self) -> str:
        mem = psutil.virtual_memory()
        used_gb = round(mem.used / (1024**3), 1)
        return f"You are using {used_gb} gigabytes of RAM. Memory usage is at {mem.percent} percent."

    def get_battery(self) -> str:
        battery = psutil.sensors_battery()
        if not battery:
            return "No battery detected."
        plugged = "plugged in" if battery.power_plugged else "discharging"
        return f"Battery is at {battery.percent} percent and {plugged}."

    def get_disk(self) -> str:
        # Windows has no "/" mount; fall back to C:\, then to current drive.
        for path in ("C:\\", "/"):
            try:
                disk = psutil.disk_usage(path)
                free_gb = round(disk.free / (1024**3), 1)
                return f"You have {free_gb} gigabytes of free storage space."
            except Exception:
                continue
        return "I could not read disk usage."

    # Backwards-compatible aliases (old names used before Phase 0 fix)
    get_cpu_status = get_cpu
    get_ram_status = get_ram
    get_battery_status = get_battery
    get_disk_status = get_disk
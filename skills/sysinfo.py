"""
The machine reporting on itself: battery, disk space, running apps, uptime.
"""
import shutil
from pathlib import Path

from .winutil import powershell

# Focus mode closes these.
DISTRACTIONS = ["WhatsApp", "Discord", "Telegram", "Steam", "Spotify", "EpicGamesLauncher"]


def _gb(num_bytes: int) -> float:
    return num_bytes / (1024 ** 3)


def battery() -> str:
    ok, out = powershell(
        "$b = Get-CimInstance Win32_Battery | Select-Object -First 1; "
        "if ($b) { \"$($b.EstimatedChargeRemaining)|$($b.BatteryStatus)\" } else { 'none' }"
    )
    if not ok or "none" in out or not out:
        return "This looks like a desktop. There is no battery."

    try:
        percent, status = out.split("|")
        percent = int(percent)
    except ValueError:
        return "I could not read the battery status."

    charging = status.strip() == "2"
    line = f"Battery is at {percent} percent"
    line += " and charging." if charging else "."

    if percent <= 15 and not charging:
        line += " Plug it in soon."
    elif percent >= 95 and charging:
        line += " It is full, you can unplug it."
    return line


def disk() -> str:
    lines = []
    for letter in "CDEF":
        drive = Path(f"{letter}:/")
        if not drive.exists():
            continue
        try:
            usage = shutil.disk_usage(str(drive))
        except OSError:
            continue
        free, total = _gb(usage.free), _gb(usage.total)
        percent_free = free / total * 100 if total else 0
        note = ", which is nearly full" if percent_free < 10 else ""
        lines.append(f"Drive {letter} has {free:.0f} GB free out of {total:.0f} GB{note}")
    return ". ".join(lines) + "." if lines else "I could not read the drives."


def running_apps() -> dict:
    """Apps that have a window open."""
    ok, out = powershell(
        "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
        "Sort-Object -Property WorkingSet64 -Descending | "
        "Select-Object -First 12 ProcessName, WorkingSet64 | "
        "ForEach-Object { \"$($_.ProcessName)|$($_.WorkingSet64)\" }"
    )
    if not ok or not out:
        return {"speak": "I do not see any app windows open.", "results": []}

    rows = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        name, _, size = line.partition("|")
        try:
            memory = _gb(int(size)) * 1024          # in MB
        except ValueError:
            continue
        rows.append({"name": name, "modified": f"{memory:.0f} MB RAM"})

    if not rows:
        return {"speak": "I do not see any app windows open.", "results": []}
    top = ", ".join(r["name"] for r in rows[:4])
    return {"speak": f"{len(rows)} apps are open. The heaviest: {top}.",
            "results": rows}


def uptime() -> str:
    ok, out = powershell(
        "$t = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; "
        "\"$([int]$t.TotalHours)|$($t.Minutes)\""
    )
    if not ok or "|" not in out:
        return "I could not work that out."
    hours, _, minutes = out.partition("|")
    try:
        hours, minutes = int(hours), int(minutes)
    except ValueError:
        return "I could not work that out."

    if hours < 1:
        return f"The laptop started {minutes} minutes ago."
    line = f"The laptop has been on for {hours} hours and {minutes} minutes."
    if hours > 48:
        line += " A restart would do it good."
    return line


def wifi() -> str:
    ok, out = powershell(
        "$n = Get-NetConnectionProfile | Select-Object -First 1; "
        "if ($n) { \"$($n.Name)|$($n.IPv4Connectivity)\" } else { 'none' }"
    )
    if not ok or "none" in out or "|" not in out:
        return "You are not connected to a network."
    name, _, state = out.partition("|")
    if state.strip().lower() == "internet":
        return f"Connected to '{name}', and the internet is working."
    return f"Connected to '{name}', but there is no internet."


def focus_mode() -> str:
    """Close the apps that break your concentration."""
    closed = []
    for app in DISTRACTIONS:
        ok, out = powershell(
            f"$p = Get-Process -Name '{app}' -ErrorAction SilentlyContinue; "
            "if ($p) { $p | Stop-Process -Force; 'yes' } else { 'no' }"
        )
        if ok and "yes" in out:
            closed.append(app)

    if not closed:
        return "No distractions were open. Nothing left to blame."
    return f"Closed {', '.join(closed)}. No more excuses."


def summary() -> str:
    """Everything at once, for a general status check."""
    return " ".join([battery(), disk(), uptime()])

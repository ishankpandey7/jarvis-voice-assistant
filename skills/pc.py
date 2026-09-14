"""
Controlling the machine: opening and closing apps, volume, screenshots,
locking, media keys, clipboard.
"""
import re
from datetime import datetime

from .winutil import KNOWN_FOLDERS, home, open_path, powershell, tap_key

# Nicknames and command-line names. Anything not listed here gets looked up
# in the full Start menu catalogue below, so this only needs the shortcuts
# people say but Windows does not call them ("browser", "editor", "calc").
APP_ALIASES = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "browser": "chrome.exe",
    "internet": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "vs code": "code",
    "vscode": "code",
    "code": "code",
    "visual studio code": "code",
    "editor": "code",
}

# If the app is not installed, open the website instead.
WEB_FALLBACK = {
    "whatsapp": "https://web.whatsapp.com",
    "youtube": "https://youtube.com",
    "gmail": "https://mail.google.com",
    "mail": "https://mail.google.com",
    "spotify": "https://open.spotify.com",
    "github": "https://github.com",
    "instagram": "https://instagram.com",
    "maps": "https://maps.google.com",
}


def _ps_str(value: str) -> str:
    """Wrap a string safely in PowerShell single quotes."""
    return "'" + str(value).replace("'", "''") + "'"


# ---------------------------------------------------------- The app catalogue
#
# Get-StartApps lists everything in the Start menu -- ordinary programs AND
# Store apps. That matters: Store apps like Camera, Photos and the new
# Notepad have no shortcut file anywhere, so searching the Start Menu folder
# for .lnk files silently misses them. This finds all of them.

_catalogue = None                              # [(display name, AppID), ...]


def _load_catalogue():
    """Ask Windows for every app in the Start menu. Cached after the first call."""
    global _catalogue
    if _catalogue is not None:
        return _catalogue

    ok, out = powershell(
        "Get-StartApps | ForEach-Object { \"$($_.Name)|$($_.AppID)\" }", timeout=30
    )
    apps = []
    if ok:
        for line in out.splitlines():
            name, sep, app_id = line.partition("|")
            if sep and name.strip() and app_id.strip():
                apps.append((name.strip(), app_id.strip()))

    _catalogue = apps
    return _catalogue


def _score(want: str, name: str) -> int:
    """How well does a spoken name match an app? Higher is better, 0 is no."""
    want, name = want.lower().strip(), name.lower().strip()
    if not want:
        return 0
    if want == name:
        return 100
    if name.startswith(want):
        return 80 - min(len(name) - len(want), 20)
    if want in name:
        return 60 - min(len(name) - len(want), 20)

    # Every spoken word appears somewhere in the app name ("vs code" -> "VS Code").
    words = want.split()
    if len(words) > 1 and all(w in name for w in words):
        return 50
    return 0


def _find_app(name: str):
    """The best-matching app, as (display name, AppID), or None."""
    best, best_score = None, 0
    for display, app_id in _load_catalogue():
        points = _score(name, display)
        if points > best_score:
            best, best_score = (display, app_id), points
    return best if best_score >= 50 else None


def _launch(app_id: str) -> bool:
    """
    Start an app by its AppID.

    Store apps are not files, so they cannot be run directly -- they are
    opened through the shell's AppsFolder, which is what Windows itself
    does when you click them in the Start menu.
    """
    if "!" in app_id or not app_id.lower().endswith(".exe"):
        ok, _ = powershell(
            "Start-Process explorer.exe -ArgumentList "
            + _ps_str("shell:AppsFolder\\" + app_id)
        )
        return ok
    ok, _ = powershell("Start-Process " + _ps_str(app_id))
    return ok


def open_app(name: str):
    """Open an app, folder or website by name."""
    key = name.lower().strip().rstrip("?.!")

    if key in KNOWN_FOLDERS:                  # "open downloads"
        folder = KNOWN_FOLDERS[key]
        folder.mkdir(parents=True, exist_ok=True)
        open_path(str(folder))
        return f"Opened the {folder.name} folder."

    if key in APP_ALIASES:                    # the handful of nicknames
        ok, _ = powershell("Start-Process " + _ps_str(APP_ALIASES[key]))
        if ok:
            return f"Opening {name}."

    found = _find_app(key)                    # everything Windows knows about
    if found is not None:
        display, app_id = found
        if _launch(app_id):
            return f"Opening {display}."

    if key in WEB_FALLBACK:                   # no app, so open the site
        open_path(WEB_FALLBACK[key])
        return f"Opening {name} in the browser."

    ok, _ = powershell("Start-Process " + _ps_str(key))   # last attempt
    if ok:
        return f"Opening {name}."

    # `failed` tells brain.py it may hand this to the AI brain instead.
    return {"speak": f"I could not find anything called '{name}'. "
                     f"Try the full name, like 'Google Chrome'.",
            "failed": True}


def close_app(name: str):
    """Quit a running app."""
    key = name.lower().strip()
    if len(key) < 2:
        # "quit", "exit", "close the window" leave nothing to act on.
        return {"speak": "Close what? Name the app.", "failed": True}
    exe = APP_ALIASES.get(key, key).replace(".exe", "")
    ok, out = powershell(
        "$p = Get-Process -Name " + _ps_str(exe) + " -ErrorAction SilentlyContinue; "
        "if ($p) { $p | Stop-Process -Force; 'closed' } else { 'none' }"
    )
    if ok and "closed" in out:
        return f"Closed {name}."
    return f"{name} was not running."


# -------------------------------------------------------------------- Sound

def volume(action: str, level=None) -> str:
    """Volume up, down, mute, or set to an exact percent."""
    if action == "mute":
        tap_key("volume_mute")
        return "Muted."
    if action == "up":
        tap_key("volume_up", 5)               # each tap is about 2%
        return "Volume up."
    if action == "down":
        tap_key("volume_down", 5)
        return "Volume down."
    if action == "set" and level is not None:
        level = max(0, min(100, int(level)))
        tap_key("volume_down", 50)            # drop to zero first
        tap_key("volume_up", level // 2)      # then climb back to the target
        return f"Volume set to {level} percent."
    return "For volume, say up, down, mute, or a number."


def media(action: str) -> str:
    """Play, pause, next or previous track."""
    table = {
        "play": ("media_play_pause", "Play, paused."),
        "pause": ("media_play_pause", "Play, paused."),
        "next": ("media_next", "Next track."),
        "previous": ("media_prev", "Previous track."),
    }
    key, msg = table.get(action, ("media_play_pause", "Play, paused."))
    tap_key(key)
    return msg


# ------------------------------------------------------------------- Screen

def screenshot() -> str:
    """Capture the whole screen into Pictures/Jarvis."""
    folder = home() / "Pictures" / "Jarvis"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"screenshot-{datetime.now():%Y%m%d-%H%M%S}.png"

    ok, err = powershell(
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
        "$img = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($img); "
        "$g.CopyFromScreen($b.X, $b.Y, 0, 0, $img.Size); "
        "$img.Save(" + _ps_str(str(path)) + "); $g.Dispose(); $img.Dispose()"
    )
    if not ok:
        return f"Could not take the screenshot: {err}"
    return f"Screenshot saved to Pictures, Jarvis folder: {path.name}"


def current_brightness():
    """What the screen is set to now, or None if this display cannot say."""
    ok, out = powershell(
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness"
        " -ErrorAction Stop).CurrentBrightness"
    )
    try:
        return int(out.splitlines()[0]) if ok and out else None
    except (ValueError, IndexError):
        return None


def brightness(level=None, step=None) -> str:
    """
    Set the screen brightness, 0 to 100.

    Pass `step` instead to move relative to where it is now, so "brighter"
    nudges it up rather than jumping to some fixed number.
    """
    if step is not None:
        now = current_brightness()
        if now is None:
            return "This screen does not let me read its brightness."
        level = now + step

    if level is None:
        return "Tell me a brightness level, or say brighter or dimmer."
    level = max(0, min(100, int(level)))

    # Note: a CIM object cannot be called directly the way a WMI object can.
    # It has to go through Invoke-CimMethod, or nothing happens.
    ok, err = powershell(
        "$m = Get-CimInstance -Namespace root/WMI"
        " -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop; "
        "Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness"
        f" -Arguments @{{Timeout=1; Brightness=[byte]{level}}} | Out-Null"
    )
    if not ok:
        return "Brightness did not change. This only works on the built-in screen."
    return f"Brightness set to {level} percent."


def lock_pc() -> str:
    powershell("rundll32.exe user32.dll,LockWorkStation")
    return "Locking the laptop."


def power(action: str) -> str:
    """Shut down or restart, with 25 seconds to change your mind."""
    if action == "cancel":
        powershell("shutdown /a")
        return "Cancelled. Nothing is shutting down."
    flag = "/r" if action == "restart" else "/s"
    word = "restart" if action == "restart" else "shut down"
    powershell(f"shutdown {flag} /t 25")
    return f"The laptop will {word} in 25 seconds. Say 'cancel' if that was a mistake."


def empty_recycle_bin() -> str:
    ok, err = powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
    return "Recycle bin emptied." if ok else f"That did not work: {err}"


# ---------------------------------------------------------------- Clipboard

_NEWLINES = re.compile(r"[\r\n]+")


def clipboard_read() -> str:
    ok, out = powershell("Get-Clipboard")
    if not ok or not out:
        return "The clipboard is empty."
    return f"The clipboard has: {_NEWLINES.sub(' ', out)[:400]}"


def clipboard_write(text: str) -> str:
    ok, _ = powershell("Set-Clipboard -Value " + _ps_str(text))
    return "Copied. You can paste it now." if ok else "Could not copy that."

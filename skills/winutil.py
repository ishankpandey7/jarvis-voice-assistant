"""
Small helpers for talking to Windows.

This file holds the "how" -- the "what" lives in the skill files above it.
Nothing to pip install: it all runs on Python's own modules plus PowerShell.
"""
import ctypes
import os
import subprocess
import time
from pathlib import Path

# ---------------------------------------------------------------- PowerShell

def powershell(script: str, timeout: int = 25) -> tuple[bool, str]:
    """Run one PowerShell command. Returns (worked?, output)."""
    try:
        done = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (done.stdout or "").strip()
        err = (done.stderr or "").strip()
        if done.returncode != 0:
            return False, err or out or "PowerShell failed"
        return True, out
    except subprocess.TimeoutExpired:
        return False, "PowerShell took too long"
    except Exception as exc:            # noqa: BLE001 - the user needs a clear message
        return False, str(exc)


# ------------------------------------------------------------------ Keyboard
# Lets the program press the volume and media keys itself.

VK = {
    "volume_mute": 0xAD,
    "volume_down": 0xAE,
    "volume_up": 0xAF,
    "media_next": 0xB0,
    "media_prev": 0xB1,
    "media_stop": 0xB2,
    "media_play_pause": 0xB3,
}

_KEYEVENTF_KEYUP = 0x0002


def tap_key(name: str, times: int = 1) -> None:
    """Press a media or volume key `times` times."""
    code = VK[name]
    user32 = ctypes.windll.user32
    for _ in range(times):
        user32.keybd_event(code, 0, 0, 0)
        user32.keybd_event(code, 0, _KEYEVENTF_KEYUP, 0)
        time.sleep(0.005)


# --------------------------------------------------------------------- Paths

def home() -> Path:
    return Path(os.path.expanduser("~"))


# Spoken name -> real folder, so "open downloads" works.
KNOWN_FOLDERS = {
    "downloads": home() / "Downloads",
    "download": home() / "Downloads",
    "documents": home() / "Documents",
    "document": home() / "Documents",
    "docs": home() / "Documents",
    "desktop": home() / "Desktop",
    "pictures": home() / "Pictures",
    "photos": home() / "Pictures",
    "music": home() / "Music",
    "videos": home() / "Videos",
    "video": home() / "Videos",
    "home": home(),
}


def open_path(target: str) -> tuple[bool, str]:
    """Open a file, folder or URL, exactly as a double click would."""
    try:
        os.startfile(target)                      # type: ignore[attr-defined]
        return True, target
    except Exception as exc:                      # noqa: BLE001
        return False, str(exc)

"""
Windows itself: its own shortcuts, its settings pages, and the windows
on screen.

Everything an app can do lives in recipes.py. This is the layer above --
the things Windows provides no matter which app is in front. Snipping a
region, clipboard history, snapping a window to half the screen, jumping
straight to the Bluetooth page instead of hunting through Settings.

Two kinds of thing here, and they work differently:

  shortcuts   keys Windows listens for globally (Win+Shift+S and friends)
  settings    ms-settings: links, which open one page directly
"""
from .keyboard import press
from .winutil import open_path

# ---------------------------------------------------------------- Shortcuts
#
# Keyed by what you would actually say. The value is the key combination.
SHORTCUTS = {
    # Capturing
    "snip": "win+shift+s",
    "screenshot area": "win+shift+s",
    "capture region": "win+shift+s",
    "record screen": "win+alt+r",
    "game bar": "win+g",

    # Things Windows keeps for you
    "clipboard history": "win+v",
    "emoji": "win+period",
    "emoji picker": "win+period",
    "dictate": "win+h",

    # Getting around
    "show desktop": "win+d",
    "minimise everything": "win+d",
    "minimize everything": "win+d",
    "task view": "win+tab",
    "switch app": "alt+tab",
    "task manager": "ctrl+shift+escape",
    "run": "win+r",
    "file explorer": "win+e",
    "quick settings": "win+a",
    "notifications": "win+n",
    "action centre": "win+a",
    "widgets": "win+w",
    "search": "win+s",
    "start menu": "win",

    # Arranging what is on screen
    "snap left": "win+left",
    "snap right": "win+right",
    "maximise": "win+up",
    "maximize": "win+up",
    "minimise": "win+down",
    "minimize": "win+down",
    "snap layouts": "win+z",
    "next monitor": "win+shift+right",
    "previous monitor": "win+shift+left",

    # Virtual desktops
    "new desktop": "win+ctrl+d",
    "next desktop": "win+ctrl+right",
    "previous desktop": "win+ctrl+left",
    "close desktop": "win+ctrl+f4",

    # Accessibility and the rest
    "magnifier": "win+plus",
    "project": "win+p",
    "second screen": "win+p",
    "lock": "win+l",
}

# ------------------------------------------------------------------ Settings
#
# Windows has a direct link to every settings page. Far better than saying
# "open settings" and then hunting.
SETTINGS_PAGES = {
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "wi-fi": "ms-settings:network-wifi",
    "network": "ms-settings:network",
    "display": "ms-settings:display",
    "screen": "ms-settings:display",
    "night light": "ms-settings:nightlight",
    "sound": "ms-settings:sound",
    "audio": "ms-settings:sound",
    "volume mixer": "ms-settings:apps-volume",
    "microphone": "ms-settings:privacy-microphone",
    "camera": "ms-settings:privacy-webcam",
    "privacy": "ms-settings:privacy",
    "apps": "ms-settings:appsfeatures",
    "installed apps": "ms-settings:appsfeatures",
    "default apps": "ms-settings:defaultapps",
    "startup apps": "ms-settings:startupapps",
    "storage": "ms-settings:storagesense",
    "battery": "ms-settings:batterysaver",
    "power": "ms-settings:powersleep",
    "sleep": "ms-settings:powersleep",
    "updates": "ms-settings:windowsupdate",
    "windows update": "ms-settings:windowsupdate",
    "notifications": "ms-settings:notifications",
    "focus assist": "ms-settings:quiethours",
    "do not disturb": "ms-settings:quiethours",
    "background": "ms-settings:personalization-background",
    "wallpaper": "ms-settings:personalization-background",
    "themes": "ms-settings:themes",
    "colours": "ms-settings:personalization-colors",
    "colors": "ms-settings:personalization-colors",
    "taskbar": "ms-settings:taskbar",
    "keyboard": "ms-settings:keyboard",
    "mouse": "ms-settings:mousetouchpad",
    "touchpad": "ms-settings:devices-touchpad",
    "printers": "ms-settings:printers",
    "language": "ms-settings:regionlanguage",
    "date and time": "ms-settings:dateandtime",
    "accounts": "ms-settings:yourinfo",
    "about": "ms-settings:about",
    "accessibility": "ms-settings:easeofaccess",
    "developer": "ms-settings:developers",
}


def shortcut(what: str) -> dict:
    """Press one of Windows' own shortcuts by name."""
    want = what.lower().strip()

    combo = SHORTCUTS.get(want)
    if combo is None:                              # a near miss will do
        for name, keys in SHORTCUTS.items():
            if want in name or name in want:
                combo, want = keys, name
                break

    if combo is None:
        return {"speak": f"I do not know a Windows shortcut called '{what}'.",
                "failed": True}

    press(combo)
    return {"speak": f"{want.capitalize()}."}


def settings(page: str = "") -> dict:
    """Open one Settings page directly, rather than the front door."""
    want = page.lower().strip()

    if not want:
        open_path("ms-settings:")
        return {"speak": "Opened Settings."}

    target = SETTINGS_PAGES.get(want)
    if target is None:
        for name, uri in SETTINGS_PAGES.items():
            if want in name or name in want:
                target, want = uri, name
                break

    if target is None:
        open_path("ms-settings:")
        return {"speak": f"I do not have a direct link to '{page}', "
                         f"so here is Settings."}

    open_path(target)
    return {"speak": f"Opened {want} settings."}


def known_shortcuts() -> list:
    return sorted(set(SHORTCUTS))


def known_settings() -> list:
    return sorted(set(SETTINGS_PAGES))

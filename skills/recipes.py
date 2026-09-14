"""
Working inside an app, not just launching it.

Opening Telegram is one command. Opening a conversation inside it is a
little sequence: bring the window up, press the search key, type the name,
pick the first result. Every app has its own version of that, differing
only in which key opens the search and what to press afterwards.

So rather than writing code per app, each one is a few lines of data below.
Two things live in each entry:

  a search recipe   how to find something by name inside that app
  an action list    its own shortcuts, by the words you would actually say

You can add your own without touching this file -- put them in
data/recipes.json and they are merged over these. See TEMPLATE at the end.

One rule worth stating plainly: nothing here SENDS a message. Jarvis opens
the conversation and types what you dictated, then stops and asks. The send
is always yours.
"""
import json
import time
from pathlib import Path

from . import keyboard as kb
from . import pc

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CUSTOM_FILE = DATA_DIR / "recipes.json"

# Per app:
#   search_key    the shortcut that opens its search box
#   after_search  keys to press once the name is typed, to pick the result
#   settle        seconds to wait for results before picking (slow apps need more)
#   window_hint   part of the window title, when it differs from the app name
#   actions       things you can ask for by name inside that app
DEFAULTS = {
    # ---------------------------------------------------------- chat apps
    "telegram": {
        "search_key": "ctrl+f", "after_search": ["down", "enter"], "settle": 0.9,
        "actions": {
            "new message": "ctrl+n", "new chat": "ctrl+n",
            "next chat": "ctrl+tab", "previous chat": "ctrl+shift+tab",
            "search in chat": "ctrl+shift+f",
            "settings": "ctrl+comma",
            "close chat": "escape",
        },
    },
    "whatsapp": {
        "search_key": "ctrl+f", "after_search": ["down", "enter"], "settle": 1.0,
        "actions": {
            "new chat": "ctrl+n", "next chat": "ctrl+tab",
            "previous chat": "ctrl+shift+tab",
            "archived": "ctrl+shift+u", "settings": "ctrl+comma",
            "search in chat": "ctrl+shift+f",
        },
    },
    "discord": {
        "search_key": "ctrl+k", "after_search": ["enter"], "settle": 0.8,
        "actions": {
            "quick switcher": "ctrl+k", "mute": "ctrl+shift+m",
            "deafen": "ctrl+shift+d", "search": "ctrl+f",
            "next server": "ctrl+alt+down", "mark read": "escape",
        },
    },
    "slack": {
        "search_key": "ctrl+k", "after_search": ["enter"], "settle": 0.8,
        "actions": {
            "search": "ctrl+f", "unread": "ctrl+shift+a",
            "threads": "ctrl+shift+t", "next channel": "alt+down",
            "mark read": "escape",
        },
    },
    "microsoft teams": {
        "search_key": "ctrl+e", "after_search": ["enter"], "settle": 1.0,
        "actions": {"new chat": "ctrl+n", "mute": "ctrl+shift+m",
                    "camera": "ctrl+shift+o", "search": "ctrl+e"},
    },
    "outlook": {
        "search_key": "ctrl+e", "after_search": ["enter"], "settle": 0.8,
        "actions": {"new mail": "ctrl+n", "reply": "ctrl+r",
                    "reply all": "ctrl+shift+r", "forward": "ctrl+f",
                    "send": "ctrl+enter", "inbox": "ctrl+shift+i"},
    },

    # ------------------------------------------------------------ browsers
    "chrome": {
        "search_key": "ctrl+l", "after_search": ["enter"], "settle": 0.3,
        "actions": {
            "new tab": "ctrl+t", "close tab": "ctrl+w",
            "reopen tab": "ctrl+shift+t", "incognito": "ctrl+shift+n",
            "bookmark": "ctrl+d", "history": "ctrl+h", "downloads": "ctrl+j",
            "find": "ctrl+f", "zoom in": "ctrl+plus", "zoom out": "ctrl+minus",
            "reset zoom": "ctrl+0", "devtools": "f12", "full screen": "f11",
        },
    },
    "edge": {
        "search_key": "ctrl+l", "after_search": ["enter"], "settle": 0.3,
        "actions": {"new tab": "ctrl+t", "close tab": "ctrl+w",
                    "bookmark": "ctrl+d", "find": "ctrl+f",
                    "full screen": "f11"},
    },

    # ------------------------------------------------------------ tools
    "visual studio code": {
        "search_key": "ctrl+p", "after_search": ["enter"], "settle": 0.5,
        "window_hint": "visual studio code",
        "actions": {
            "command palette": "ctrl+shift+p", "terminal": "ctrl+backtick",
            "sidebar": "ctrl+b", "find": "ctrl+f",
            "find in files": "ctrl+shift+f", "save": "ctrl+s",
            "save all": "ctrl+k", "format": "shift+alt+f",
            "comment": "ctrl+slash", "new file": "ctrl+n",
            "close file": "ctrl+w", "settings": "ctrl+comma",
            "zen mode": "ctrl+k",
        },
    },
    "obsidian": {
        "search_key": "ctrl+o", "after_search": ["enter"], "settle": 0.5,
        "actions": {"command palette": "ctrl+p", "new note": "ctrl+n",
                    "search": "ctrl+shift+f", "graph": "ctrl+g",
                    "settings": "ctrl+comma"},
    },
    "spotify": {
        "search_key": "ctrl+l", "after_search": ["enter"], "settle": 0.9,
        "actions": {"play": "space", "next": "ctrl+right",
                    "previous": "ctrl+left", "like": "alt+shift+b",
                    "volume up": "ctrl+up", "volume down": "ctrl+down"},
    },
    "explorer": {
        "search_key": "ctrl+e", "after_search": ["enter"], "settle": 0.4,
        "window_hint": "file explorer",
        "actions": {"new folder": "ctrl+shift+n", "up": "alt+up",
                    "back": "alt+left", "rename": "f2", "properties": "alt+enter",
                    "new tab": "ctrl+t", "select all": "ctrl+a"},
    },
    "notepad": {
        "search_key": "ctrl+f", "after_search": ["enter"], "settle": 0.3,
        "actions": {"new tab": "ctrl+t", "save": "ctrl+s",
                    "find": "ctrl+f", "replace": "ctrl+h", "word wrap": "alt+o"},
    },

    # Anything not listed falls back to this, which is right more often
    # than you would expect -- Ctrl+F is close to universal.
    "_default": {"search_key": "ctrl+f", "after_search": ["enter"], "settle": 0.6,
                 "actions": {}},
}

# Shortcuts that mean the same thing nearly everywhere. Used when an app
# has no entry of its own for what you asked.
UNIVERSAL = {
    "save": "ctrl+s", "copy": "ctrl+c", "paste": "ctrl+v", "cut": "ctrl+x",
    "undo": "ctrl+z", "redo": "ctrl+y", "select all": "ctrl+a",
    "find": "ctrl+f", "print": "ctrl+p", "new": "ctrl+n", "close": "ctrl+w",
    "refresh": "f5", "full screen": "f11", "escape": "escape",
    "settings": "ctrl+comma",
}


def _load_custom() -> dict:
    """Your own recipes, merged over the built-in ones."""
    if not CUSTOM_FILE.exists():
        return {}
    try:
        loaded = json.loads(CUSTOM_FILE.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _table() -> dict:
    merged = {name: dict(recipe) for name, recipe in DEFAULTS.items()}
    for name, recipe in _load_custom().items():
        if name in merged and isinstance(recipe, dict):
            # Merge actions rather than replacing the lot, so adding one
            # shortcut does not cost you all the built-in ones.
            actions = dict(merged[name].get("actions", {}))
            actions.update(recipe.get("actions", {}))
            merged[name].update(recipe)
            merged[name]["actions"] = actions
        else:
            merged[name] = recipe
    return merged


# What people say, versus what the recipe is filed under. Without this,
# "vs code" matches nothing -- neither string contains the other.
ALIASES = {
    "vs code": "visual studio code", "vscode": "visual studio code",
    "code": "visual studio code", "editor": "visual studio code",
    "teams": "microsoft teams",
    "browser": "chrome", "google chrome": "chrome",
    "file explorer": "explorer", "files": "explorer", "folder": "explorer",
    "wa": "whatsapp", "tg": "telegram",
    "mail": "outlook", "email": "outlook",
}


def resolve(app: str) -> str:
    """The recipe name for whatever the user called it."""
    key = (app or "").lower().strip()
    if key in ALIASES:
        return ALIASES[key]
    table = _table()
    if key in table:
        return key
    for name in table:
        if name != "_default" and (name in key or key in name):
            return name
    return key


def recipe_for(app: str) -> dict:
    """The recipe for an app, falling back to the generic one."""
    table = _table()
    return table.get(resolve(app), table["_default"])


def known_apps() -> list:
    return sorted(n for n in _table() if n != "_default")


def actions_for(app: str) -> dict:
    """Everything you can ask for inside this app, its own plus the universal."""
    combined = dict(UNIVERSAL)
    combined.update(recipe_for(app).get("actions", {}))
    return combined


# --------------------------------------------------------------- Getting there

def ensure_app(name: str, seconds: float = 8.0):
    """
    Make sure an app's window is up and focused.

    The tray is the catch here. Telegram, Discord and WhatsApp all hide in
    the notification area rather than closing, so the process is running
    while no window exists -- and asking to focus one fails. Launching it
    again is what restores it, so that is what this does, then waits for
    the window to actually appear before anyone tries to type into it.
    """
    # Use the resolved name for the window hint too, so "vs code" looks for
    # a "Visual Studio Code" window rather than one called "vs code".
    hint = recipe_for(name).get("window_hint", resolve(name)).lower()

    visible = [t for _, t in kb.list_windows() if hint in t.lower()]
    if visible:
        kb.focus_window(hint)
        return True, visible[0]

    pc.open_app(name)                              # brings it back from the tray

    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(0.4)
        found = [t for _, t in kb.list_windows() if hint in t.lower()]
        if found:
            kb.focus_window(hint)
            time.sleep(0.3)                        # let it finish drawing
            return True, found[0]

    return False, ""


def _still_focused(hint: str) -> bool:
    """Guard before typing: is the app we aimed at actually in front?"""
    return hint.lower() in (kb.active_window() or "").lower()


# ------------------------------------------------------------- Doing something

def find_in_app(app: str, query: str) -> dict:
    """Open something by name inside an app: a chat, a file, a playlist."""
    query = query.strip()
    if not query:
        return {"speak": f"What should I look for in {app}?", "failed": True}

    ok, title = ensure_app(app)
    if not ok:
        return {"speak": f"I could not get {app} on screen.", "failed": True}

    plan = recipe_for(app)
    kb.press(plan["search_key"])
    time.sleep(0.35)                               # the search box needs a beat
    kb.type_text(query)
    time.sleep(plan.get("settle", 0.6))            # and the results need longer

    for key in plan.get("after_search", ["enter"]):
        kb.press(key)
        time.sleep(0.15)

    return {"speak": f"Opened {query} in {app}."}


def do_in_app(app: str, what: str) -> dict:
    """Run one of an app's own shortcuts by name: 'new chat in telegram'."""
    what = what.lower().strip()
    available = actions_for(app)

    combo = available.get(what)
    if combo is None:                              # a near miss is good enough
        for name, keys in available.items():
            if what in name or name in what:
                combo, what = keys, name
                break

    if combo is None:
        known = ", ".join(sorted(available)[:10])
        return {"speak": f"I do not know '{what}' in {app}. I know: {known}.",
                "failed": True}

    ok, _ = ensure_app(app)
    if not ok:
        return {"speak": f"I could not get {app} on screen.", "failed": True}

    kb.press(combo)
    return {"speak": f"{what.capitalize()} in {app}."}


def write_message(app: str, who: str, message: str) -> dict:
    """
    Open a conversation and type a message -- but do NOT send it.

    Sending is a one-way door: there is no unsending a message to the wrong
    person, and the name was matched by a fuzzy search that could easily
    have landed on the wrong contact. So Jarvis stops with the message
    sitting in the box, where you can read it, and waits to be told.
    """
    who, message = who.strip(), message.strip()
    if not who:
        return {"speak": "Who should I message?", "failed": True}
    if not message:
        return {"speak": "What should the message say?", "failed": True}

    opened = find_in_app(app, who)
    if opened.get("failed"):
        return opened

    time.sleep(0.5)                                # the chat has to settle

    hint = recipe_for(app).get("window_hint", app)
    if not _still_focused(hint):
        return {"speak": f"{app} lost focus before I could type. "
                         f"Click it and ask me again.", "failed": True}

    kb.type_text(message)

    return {
        "speak": f'Typed "{message}" to {who} in {app}. '
                 f"Check it is the right person, then say send.",
        "needs_confirm": True,
        "confirm_action": {"skill": "recipes.send"},
    }


def send_typed_message() -> str:
    """Press Enter on the message that is already sitting in the box."""
    kb.press("enter")
    return "Sent."


# ---------------------------------------------------------------------------
# Teaching Jarvis a new app
# ---------------------------------------------------------------------------
#
# Put a file at data/recipes.json shaped like this. Anything you define is
# merged over the built-ins, and your "actions" are added to theirs rather
# than replacing them.
#
# {
#   "figma": {
#     "search_key": "ctrl+p",
#     "after_search": ["enter"],
#     "settle": 0.6,
#     "actions": {
#       "components": "alt+2",
#       "layers": "alt+1",
#       "comment": "c"
#     }
#   },
#   "telegram": {
#     "actions": { "archived": "ctrl+shift+a" }
#   }
# }
#
# Then: "open figma and find the login screen", or "archived in telegram".

TEMPLATE = {
    "your app name in lowercase": {
        "search_key": "ctrl+f",
        "after_search": ["enter"],
        "settle": 0.6,
        "actions": {"what you would say": "the+shortcut"},
    }
}

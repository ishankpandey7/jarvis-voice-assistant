"""
Giving Jarvis hands.

Opening a program was only ever half of it. Once Chrome is on screen you
want to search in it; once the editor is open you want to save. That means
typing and pressing keys, which is what this does -- it drives the real
keyboard, so whatever window is in front receives the keys exactly as if
you had typed them.

Everything here goes through the Windows SendInput call, reached with
ctypes. Nothing to install.

One thing to keep in mind while reading this: keys land in whichever
window is focused RIGHT NOW. That is what makes it useful and also what
makes it worth being careful with -- see focus_window(), and the
confirmation rules in ai.py.
"""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32

# ---------------------------------------------------------------- SendInput

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class _KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _InputUnion(ctypes.Union):
    # All three must be here or the struct comes out the wrong size and
    # Windows rejects every call.
    _fields_ = [("ki", _KeyboardInput), ("mi", _MouseInput),
                ("hi", _HardwareInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _InputUnion)]


def _send(events) -> None:
    count = len(events)
    array = (_Input * count)(*events)
    user32.SendInput(count, array, ctypes.sizeof(_Input))


def _unicode_event(char: str, up: bool = False) -> _Input:
    """One keystroke carrying a character directly, so any letter works."""
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    key = _KeyboardInput(wVk=0, wScan=ord(char), dwFlags=flags,
                         time=0, dwExtraInfo=None)
    return _Input(type=INPUT_KEYBOARD, union=_InputUnion(ki=key))


def _vk_event(code: int, up: bool = False) -> _Input:
    """One keystroke by virtual key code, for keys with no character."""
    key = _KeyboardInput(wVk=code, wScan=0,
                         dwFlags=KEYEVENTF_KEYUP if up else 0,
                         time=0, dwExtraInfo=None)
    return _Input(type=INPUT_KEYBOARD, union=_InputUnion(ki=key))


# ------------------------------------------------------------ Key names

VK = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f11": 0x7A, "f12": 0x7B,
    "printscreen": 0x2C,
}
for _n in range(10):
    VK[str(_n)] = 0x30 + _n
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = 0x41 + ord(_c) - ord("a")

MODIFIERS = {"ctrl", "control", "shift", "alt", "win"}


def press(combo: str) -> str:
    """
    Press a key or a combination: "enter", "ctrl+t", "ctrl+shift+n".

    Modifiers go down in order, the last key is tapped, then the modifiers
    come back up in reverse -- the same shape as a real key press.
    """
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        return "Tell me which key to press."

    unknown = [p for p in parts if p not in VK]
    if unknown:
        return f"I do not know the key '{unknown[0]}'."

    held = [p for p in parts if p in MODIFIERS]
    rest = [p for p in parts if p not in MODIFIERS]
    if not rest:
        rest = [held.pop()] if held else []

    events = [_vk_event(VK[m]) for m in held]
    for key in rest:
        events.append(_vk_event(VK[key]))
        events.append(_vk_event(VK[key], up=True))
    events += [_vk_event(VK[m], up=True) for m in reversed(held)]

    _send(events)
    return f"Pressed {combo}."


def type_text(text: str, per_char: float = 0.004) -> str:
    """
    Type a string into whatever window is in front.

    The reply names that window on purpose. Typing is the one thing here
    that can quietly damage something -- a few hundred characters into
    someone's half-finished document looks just like success otherwise.
    """
    text = text.strip()
    if not text:
        return "Tell me what to type."
    if len(text) > 2000:
        return "That is too long to type. Keep it under 2000 characters."

    target = active_window() or "the window in front"

    for char in text:
        if char == "\n":
            press("enter")
            continue
        _send([_unicode_event(char), _unicode_event(char, up=True)])
        time.sleep(per_char)               # too fast and apps drop characters

    shown = text if len(text) <= 40 else text[:40] + "…"
    return f'Typed "{shown}" into {target}.'


# ----------------------------------------------------------------- Windows

def active_window() -> str:
    """The title of the window currently in front."""
    handle = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(handle)
    if not length:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value


def list_windows() -> list:
    """Every visible window with a title, as (handle, title)."""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def collect(handle, _lparam):
        if user32.IsWindowVisible(handle):
            length = user32.GetWindowTextLengthW(handle)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(handle, buffer, length + 1)
                if buffer.value.strip():
                    found.append((handle, buffer.value))
        return True

    user32.EnumWindows(collect, 0)
    return found


SW_RESTORE = 9

# Titles almost always read "Document - App", so the app name is the last
# part. Matching that, rather than anywhere in the string, keeps "notepad"
# from landing on a document that merely happens to be open in Notepad.
BLANK_DOCS = ("untitled", "new tab", "new document", "blank")


def _title_score(want: str, title: str) -> int:
    """
    How good a match is this window? Higher wins.

    Deliberately biased toward empty documents. Asking for "notepad" almost
    always means "somewhere to type", not "the file I already have open" --
    and picking the wrong one means typing into someone's work.
    """
    low = title.lower()
    app = low.rsplit(" - ", 1)[-1].strip()         # "agents.py - Notepad" -> "notepad"
    doc = low.rsplit(" - ", 1)[0].strip() if " - " in low else ""

    score = 0
    if app == want:
        score += 100                               # the app itself, exactly
    elif want in app:
        score += 60
    elif want in low:
        score += 20                                # only in the document name

    if any(doc.startswith(b) for b in BLANK_DOCS):
        score += 40                                # an empty one is the safe one
    elif doc:
        score -= 15                                # a real document: prefer not to

    return score


def focus_window(name: str) -> str:
    """
    Bring a window to the front by part of its title.

    This matters more than it looks: keystrokes go to whatever is focused,
    so anything that types should make sure the right window is in front
    first.
    """
    want = name.lower().strip()
    if not want:
        return "Which window?"

    matches = [(h, t) for h, t in list_windows() if want in t.lower()]
    if not matches:
        return f"No open window matches '{name}'."

    handle, title = max(matches, key=lambda row: _title_score(want, row[1]))

    user32.ShowWindow(handle, SW_RESTORE)          # in case it is minimised
    # Windows blocks a background process from stealing focus unless it can
    # claim some input happened. A tap of ALT satisfies that rule.
    _send([_vk_event(VK["alt"]), _vk_event(VK["alt"], up=True)])
    user32.SetForegroundWindow(handle)
    time.sleep(0.12)                               # let the switch settle

    short = title if len(title) <= 50 else title[:50] + "…"
    return f"Switched to {short}."


def window_action(action: str) -> str:
    """Minimise, maximise or restore the window in front."""
    handle = user32.GetForegroundWindow()
    codes = {"minimise": 6, "minimize": 6, "maximise": 3, "maximize": 3,
             "restore": 9}
    if action not in codes:
        return "Say minimise, maximise or restore."
    user32.ShowWindow(handle, codes[action])
    return f"Window {action}d."


# ------------------------------------------------------- Useful combinations

def search_in_browser(query: str) -> str:
    """
    Open a new tab and search. Typed into the browser rather than launched
    as a URL, so it lands in the window you are already using, with your
    session and your default search engine.
    """
    query = query.strip()
    if not query:
        return "What should I search for?"

    front = active_window().lower()
    if not any(b in front for b in ("chrome", "edge", "firefox", "brave")):
        moved = focus_window("chrome")
        if "No open window" in moved:
            return {"speak": "No browser window is open to search in.",
                    "failed": True}

    press("ctrl+t")
    time.sleep(0.25)                               # the new tab needs a moment
    type_text(query)
    time.sleep(0.1)
    press("enter")
    return f'Searching for "{query}".'

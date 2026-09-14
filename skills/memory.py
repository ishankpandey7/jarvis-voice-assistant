"""
The things Jarvis remembers: notes, a to-do list, reminders and timers.

Everything is stored as plain JSON in the data/ folder. No database.
"""
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

NOTES_FILE = DATA_DIR / "notes.json"
TODOS_FILE = DATA_DIR / "todos.json"
ALARMS_FILE = DATA_DIR / "reminders.json"


def _load(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []                                  # file is damaged, start fresh


def _save(path: Path, rows: list) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _stamp() -> str:
    return datetime.now().strftime("%d %b %Y, %I:%M %p")


# --------------------------------------------------------------------- Notes

def add_note(text: str) -> str:
    text = text.strip()
    if not text:
        return "The note is empty. Tell me what to write."
    rows = _load(NOTES_FILE)
    rows.append({"text": text, "when": _stamp(), "at": time.time()})
    _save(NOTES_FILE, rows)
    return f"Noted: {text}"


def list_notes(count: int = 10) -> dict:
    rows = _load(NOTES_FILE)[-count:][::-1]
    if not rows:
        return {"speak": "You have no notes yet.", "results": []}
    word = "note" if len(rows) == 1 else "notes"
    return {"speak": f"You have {len(rows)} {word}:",
            "results": [{"name": r["text"], "modified": r["when"]} for r in rows]}


def clear_notes() -> str:
    _save(NOTES_FILE, [])
    return "All notes deleted."


# ------------------------------------------------------------------- To-dos

def add_todo(text: str) -> str:
    text = text.strip()
    if not text:
        return "Tell me what the task is."
    rows = _load(TODOS_FILE)
    rows.append({"text": text, "done": False, "at": time.time()})
    _save(TODOS_FILE, rows)
    pending = sum(1 for r in rows if not r["done"])
    word = "task" if pending == 1 else "tasks"
    return f"Added: {text}. That is {pending} {word} now."


def list_todos() -> dict:
    rows = _load(TODOS_FILE)
    pending = [r for r in rows if not r["done"]]
    if not pending:
        return {"speak": "Nothing pending. Your list is clear.", "results": []}
    lines = [{"name": "[ ] " + r["text"]} for r in pending]
    first = ", ".join(r["text"] for r in pending[:3])
    word = "task" if len(pending) == 1 else "tasks"
    return {"speak": f"{len(pending)} {word} left: {first}.", "results": lines}


_SMALL_WORDS = {"the", "a", "an", "my", "to", "of", "for", "and", "some", "it"}


def _match_score(needle: str, task: str) -> float:
    """
    How well do these two describe the same thing? 0 to 1.

    Word based, not substring based, so "call bank" still finds
    "call the bank" and "buy milk" finds "buy some milk".
    """
    wanted = {w for w in re.findall(r"\w+", needle.lower()) if w not in _SMALL_WORDS}
    have = {w for w in re.findall(r"\w+", task.lower()) if w not in _SMALL_WORDS}
    if not wanted:
        return 0.0
    return len(wanted & have) / len(wanted)


def finish_todo(text: str):
    """Mark the closest matching task as done."""
    rows = _load(TODOS_FILE)

    best, best_score = None, 0.0
    for row in rows:
        if row["done"]:
            continue
        score = _match_score(text, row["text"])
        if score > best_score:
            best, best_score = row, score

    if best is not None and best_score >= 0.6:     # most of the words line up
        best["done"] = True
        _save(TODOS_FILE, rows)
        left = sum(1 for r in rows if not r["done"])
        return f"Marked '{best['text']}' as done. {left} left."
    # `failed` tells brain.py it may hand this to the AI brain --
    # the user probably was not talking about a task at all.
    return {"speak": f"I have no pending task matching '{text}'.", "failed": True}


# ------------------------------------------------------- Understanding time

_UNITS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "day": 86400, "days": 86400,
}

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "forty five": 45, "sixty": 60,
}

# Whole phrases, swapped in before the single words above. "half an hour"
# has to be handled as one lump -- word by word it turns into "1 hour".
_PHRASES = [
    (r"\b(half an hour|half hour|an? half hour)\b", "30 minutes"),
    (r"\b(an? hour and a half|hour and a half)\b", "90 minutes"),
    (r"\b(quarter of an hour|quarter hour)\b", "15 minutes"),
    (r"\ban? couple of (hours|minutes)\b", r"2 \1"),
    (r"\ba few (hours|minutes)\b", r"3 \1"),
    (r"\ban? (hour|minute|second|day)\b", r"1 \1"),
]


def parse_when(text: str):
    """
    Turn spoken time into a real timestamp.

    Understands: "10 minutes", "two hours", "at 6", "6:30 pm",
    "tomorrow at 8". Returns None when it cannot tell.
    """
    low = text.lower()

    for pattern, replacement in _PHRASES:          # whole phrases first
        low = re.sub(pattern, replacement, low)

    # Spelled-out numbers become digits: "two hours" -> "2 hours"
    for word, value in sorted(_WORD_NUMBERS.items(), key=lambda kv: -len(kv[0])):
        low = re.sub(rf"\b{word}\b", str(value), low)

    # Form 1: a duration -- "in 10 minutes", "after 2 hours"
    match = re.search(r"(\d+)\s*(" + "|".join(_UNITS) + r")\b", low)
    if match:
        seconds = int(match.group(1)) * _UNITS[match.group(2)]
        if seconds > 0:
            return time.time() + seconds, _describe(seconds)

    # Form 2: a clock time -- "at 6", "6:30 pm", "tomorrow at 8"
    clock = re.search(r"(?:at\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", low)
    if clock and ("at " in low or "am" in low or "pm" in low or "o'clock" in low):
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)
        if hour > 23 or minute > 59:
            return None

        said_half = None
        if "pm" in low:
            said_half = "pm"
        elif "am" in low:
            said_half = "am"
        elif any(w in low for w in ("evening", "tonight", "night")):
            said_half = "pm"
        elif "morning" in low:
            said_half = "am"

        if said_half == "pm" and hour < 12:
            hour += 12
        elif said_half == "am" and hour == 12:
            hour = 0

        tomorrow = "tomorrow" in low
        best = _next_occurrence(hour, minute, tomorrow)

        # No am/pm given, so "at 9" is ambiguous. Try the other half of the
        # day too and keep whichever comes round sooner -- at 3 pm, "at 9"
        # means tonight, not nine tomorrow morning.
        if said_half is None and hour <= 12:
            other = _next_occurrence((hour + 12) % 24, minute, tomorrow)
            if other < best:
                best = other

        return best.timestamp(), best.strftime("%I:%M %p")

    return None


def _next_occurrence(hour: int, minute: int, tomorrow: bool) -> datetime:
    """The next time the clock shows this, today or tomorrow."""
    target = datetime.now().replace(hour=hour % 24, minute=minute,
                                    second=0, microsecond=0)
    if tomorrow:
        target += timedelta(days=1)
    elif target <= datetime.now():
        target += timedelta(days=1)               # already gone by today
    return target


def _describe(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second" + ("" if seconds == 1 else "s")
    if seconds < 3600:
        count = seconds // 60
        return f"{count} minute" + ("" if count == 1 else "s")
    if seconds < 86400:
        hours = seconds / 3600
        text = f"{hours:.0f}" if hours == int(hours) else f"{hours:.1f}"
        return f"{text} hour" + ("" if text == "1" else "s")
    count = seconds // 86400
    return f"{count} day" + ("" if count == 1 else "s")


# ----------------------------------------------------------------- Reminders

def add_reminder(text: str, when_text: str, kind: str = "reminder") -> str:
    parsed = parse_when(when_text)
    if parsed is None:
        return ("I could not work out the time. Try 'set a 10 minute timer' "
                "or 'remind me at 7 pm to take my medicine'.")
    due_at, pretty = parsed

    rows = _load(ALARMS_FILE)
    rows.append({
        "id": f"r{int(time.time() * 1000)}",
        "text": text.strip() or ("Timer finished" if kind == "timer" else "Reminder"),
        "due": due_at,
        "kind": kind,
        "fired": False,
    })
    _save(ALARMS_FILE, rows)

    if kind == "timer":
        return f"Timer set for {pretty}. I will tell you."
    # "at 7:00 PM" reads right, but a duration needs "in 5 minutes".
    when = f"at {pretty}" if ("AM" in pretty or "PM" in pretty) else f"in {pretty}"
    return f"I will remind you {when}: {text.strip()}"


def list_reminders() -> dict:
    rows = [r for r in _load(ALARMS_FILE) if not r["fired"]]
    if not rows:
        return {"speak": "No reminders or timers are set.", "results": []}
    rows.sort(key=lambda r: r["due"])
    out = []
    for row in rows:
        left = max(0, int(row["due"] - time.time()))
        out.append({"name": row["text"],
                    "modified": f"in {_describe(left)}"
                                f" ({datetime.fromtimestamp(row['due']):%I:%M %p})"})
    word = "reminder" if len(rows) == 1 else "reminders"
    return {"speak": f"You have {len(rows)} {word} set:", "results": out}


def cancel_reminders() -> str:
    rows = _load(ALARMS_FILE)
    live = [r for r in rows if not r["fired"]]
    _save(ALARMS_FILE, [r for r in rows if r["fired"]])
    if not live:
        return "There was nothing set."
    word = "reminder" if len(live) == 1 else "reminders"
    return f"Cancelled {len(live)} {word}."


def check_due() -> list:
    """
    Return any reminders that should ring now, and mark them fired.
    The web page asks for this every few seconds.
    """
    rows = _load(ALARMS_FILE)
    now = time.time()
    ringing = []
    changed = False

    for row in rows:
        if not row["fired"] and row["due"] <= now:
            row["fired"] = True
            changed = True
            ringing.append({"id": row["id"], "text": row["text"], "kind": row["kind"]})

    if changed:
        recent = [r for r in rows if not r["fired"] or r["due"] > now - 86400]
        _save(ALARMS_FILE, recent)                # drop old fired ones
    return ringing

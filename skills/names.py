"""
Learning how the names you say actually get written.

Speech recognition is an English model listening to Indian names, and it
mangles them in consistent ways: Ravi comes back as Robbie, Aarav as Arrow,
Shreya as Shreyer. The transcript is wrong before Jarvis ever sees it, so
no amount of cleverness downstream will fix it -- but the mistakes repeat,
which means they can be learned.

Two things happen here:

  1. A short list you teach it: "remember robbie is ravi". Exact and
     permanent, kept in data/names.json.

  2. A shortening trick for everything else. Searching for "rav" finds
     Ravi whether or not the last letter was heard right, because the
     first few sounds of a name survive mis-hearing far better than the
     whole thing does.
"""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NAMES_FILE = DATA_DIR / "names.json"


def _load() -> dict:
    if not NAMES_FILE.exists():
        return {}
    try:
        loaded = json.loads(NAMES_FILE.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(table: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    NAMES_FILE.write_text(json.dumps(table, indent=2, ensure_ascii=False),
                          encoding="utf-8")


def teach(heard: str, meant: str) -> str:
    """Record that one spoken word should be written as another."""
    heard, meant = heard.lower().strip(), meant.strip()
    if not heard or not meant:
        return "Say it like: remember robbie is ravi."

    table = _load()
    table[heard] = meant
    _save(table)
    return f'Noted. When I hear "{heard}" I will write {meant}.'


def forget(heard: str) -> str:
    table = _load()
    removed = table.pop(heard.lower().strip(), None)
    if removed is None:
        return f"I had nothing written down for '{heard}'."
    _save(table)
    return f"Forgot that one."


def listing() -> dict:
    table = _load()
    if not table:
        return {"speak": "I have not been taught any names yet. Say: "
                         "remember robbie is ravi.", "results": []}
    return {"speak": f"{len(table)} names learned:",
            "results": [{"name": f"{heard} → {meant}"}
                        for heard, meant in sorted(table.items())]}


def correct(spoken: str) -> str:
    """
    Apply what has been learned, word by word.

    Only whole words are replaced, so teaching "robbie" does not quietly
    rewrite "robbies" or a word that merely contains it.
    """
    table = _load()
    if not table:
        return spoken

    def swap(match):
        return table.get(match.group(0).lower(), match.group(0))

    return re.sub(r"\w+", swap, spoken)


# How much of a name to actually type into a search box. Long enough to be
# specific, short enough that a mis-heard ending does not matter.
SEARCH_PREFIX = 4


def search_key(name: str) -> str:
    """
    Turn a spoken name into the thing to type in a search box.

    A learned name goes in whole -- it is known to be right. Anything else
    gets trimmed to its first few letters, because "rav" finds Ravi even
    when the transcript said Ravvy, and app search boxes match prefixes.
    """
    name = name.strip()
    if not name:
        return name

    table = _load()
    if name.lower() in table:
        return table[name.lower()]

    words = name.split()
    if len(words) > 1:
        return name                       # a full name is specific already
    if len(name) <= SEARCH_PREFIX + 1:
        return name                       # already short
    return name[:SEARCH_PREFIX]

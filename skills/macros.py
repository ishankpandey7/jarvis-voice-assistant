"""
Macros: one name, several commands.

"start work" is three things -- VS Code, Chrome, Spotify -- and saying all
three every morning is the sort of small friction that makes you stop
bothering. A macro is a name with a list of commands underneath it.

The list holds things you would SAY, not a new vocabulary:

    "start work": ["open vs code", "open chrome", "open spotify"]

Each line goes back through the brain exactly as if you had said it. That
one decision is what makes this worth having: a macro can do anything
Jarvis can do, anything Jarvis learns later works in macros the same day,
and there is nothing extra to remember. If you can say it, you can list it.

Yours live in data/macros.json, merged over the few below -- same
arrangement as recipes.json. See macros.example.json for the shape, or just
say: create a macro called start work: open vs code, open chrome.

Two things a macro deliberately will NOT do:

  It will not answer a question for you. If a step comes back asking
  "shall I?", the macro skips that step and says which one, rather than
  saying yes on your behalf. Steps that map to a plain rule still run
  straight off -- you wrote them down in advance, which is as clear as
  asking gets.

  It will not run itself. A macro listing its own name, or two listing each
  other, would loop until something fell over. _RUNNING below catches it.
"""
import json
import re
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CUSTOM_FILE = DATA_DIR / "macros.json"

# A beat between steps. Launching three apps back to back means three
# windows all trying to take focus at once, and the last one does not
# always win. Per macro you can set "pause" to something else.
DEFAULT_PAUSE = 0.6

# A macro is meant to be a handful of things, not a script. The cap is here
# so a mis-parsed sentence cannot turn into forty keystrokes.
MAX_STEPS = 20


# Built-ins are examples as much as anything -- three shapes worth copying.
# Anything here can be overridden, or removed, from data/macros.json.
BUILTIN = {
    # The one from the wish list: open everything work happens in.
    "start work": {
        "steps": ["open vs code", "open chrome", "open spotify"],
        "say": "Work setup is up.",
    },
    # The other end of the day. Only closes things, so it is safe to try.
    "wind down": {
        "steps": ["close spotify", "close discord", "set volume to 20",
                  "brightness 30"],
        "say": "Winding down.",
    },
    # Macros are not only for launching things -- a macro of questions reads
    # you a briefing, and every answer lands in the list under the reply.
    "catch up": {
        "steps": ["what's on my list", "how's the battery", "what's the weather"],
    },
}


# --------------------------------------------------------------- The table

def _load_custom() -> dict:
    if not CUSTOM_FILE.exists():
        return {}
    try:
        loaded = json.loads(CUSTOM_FILE.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}                                  # damaged file, ignore it


def table() -> dict:
    """
    Built-ins with your own merged over them.

    A name set to null is a tombstone -- that is how you delete a built-in
    without editing the code. "forget the wind down macro" writes one.
    """
    merged = {name: dict(plan) for name, plan in BUILTIN.items()}

    for name, plan in _load_custom().items():
        if name.startswith("_"):                   # "_comment" in the example file
            continue
        if plan is None:
            merged.pop(name, None)
        elif isinstance(plan, dict):
            merged[name] = plan
        elif isinstance(plan, list):
            merged[name] = {"steps": plan}         # the short form: just steps

    return merged


def known() -> list:
    return sorted(table())


def _save_custom(rows: dict) -> None:
    CUSTOM_FILE.write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                           encoding="utf-8")


# ------------------------------------------------------------- Finding one

# Speech gives you "start my work" for "start work", and a trailing "please"
# survives cleaning often enough to matter. Neither should stop a match.
_FILLER = re.compile(r"\b(the|a|an|my|our|please|now)\b", re.I)


def _norm(text: str) -> str:
    """Boil a phrase down so two spellings of the same name meet."""
    text = re.sub(r"[^\w\s]", " ", (text or "").lower())
    text = _FILLER.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve(spoken: str, loose: bool = False) -> str:
    """
    Which macro was named, or "" for none.

    Strict by default, and that matters. This gets asked about every single
    thing you say, before the rule list -- so it may only answer when the
    whole sentence IS the macro's name. Anything looser and a macro called
    "notes" would quietly eat "read me my notes".

    loose=True is for when you have already said the word macro out loud
    ("run my start work macro"), where guessing is what you want.
    """
    said = _norm(spoken)
    if not said:
        return ""

    names = table()
    for name in names:
        if _norm(name) == said:
            return name

    if not loose:
        return ""

    for name in names:
        target = _norm(name)
        if target and (target in said or said in target):
            return name
    return ""


def preview(name: str, limit: int = 6) -> str:
    """The steps as one readable line, for a confirmation question."""
    steps = table().get(name, {}).get("steps", [])
    shown = "; ".join(steps[:limit])
    return shown + (", and more" if len(steps) > limit else "")


# ---------------------------------------------------------------- Running

# Macros part-way through running. A macro naming itself -- directly, or
# through another that names it back -- would otherwise recurse until the
# stack gave out, and the error would point at somewhere innocent.
_RUNNING = set()


def run(name: str) -> dict:
    """Run every step in a macro, then report what actually happened."""
    import brain                                   # late: brain imports us

    plan = table().get(name)
    if plan is None:
        return {"speak": f"I have no macro called {name}.", "failed": True}

    if name in _RUNNING:
        # Deliberately not "failed": that word means "a rule grabbed a
        # sentence it should not have, let the AI try instead", and asking
        # a language model about a loop in your own config helps nobody.
        # "looped" travels back up and stops every macro in the chain.
        return {"speak": f"The macro '{name}' ends up running itself, "
                         f"so I stopped.", "looped": True}

    steps = [s for s in plan.get("steps", []) if isinstance(s, str) and s.strip()]
    if not steps:
        return {"speak": f"The macro {name} has no steps in it.", "failed": True}

    pause = _number(plan.get("pause"), DEFAULT_PAUSE)
    rows, spoken, trouble = [], [], []

    _RUNNING.add(name)
    try:
        for position, step in enumerate(steps[:MAX_STEPS]):
            # decorate=False: the personality belongs on the one answer the
            # macro gives at the end, not on each step inside it.
            answer = brain.handle(step, decorate=False)
            said = (answer.get("speak") or "").strip()

            if answer.get("looped"):
                # A macro further down the chain came back round to one
                # already running. Carry the reason up unchanged rather
                # than burying it under "1 of 3 went through".
                rows.append({"name": step, "note": said})
                return {"speak": said, "results": rows, "looped": True}

            if answer.get("needs_confirm"):
                # Something in here wants a yes. Saying it for you is exactly
                # the thing this must never do -- so drop the question brain
                # is now holding, skip the step, and name it in the report.
                brain.clear_pending()
                rows.append({"name": step, "note": "skipped -- needs a yes"})
                trouble.append(step)
                continue

            rows.append({"name": step, "note": said or "done"})
            if answer.get("failed") or answer.get("unknown"):
                trouble.append(step)
            elif said:
                spoken.append(said)

            if position < len(steps) - 1:
                time.sleep(pause)
    finally:
        _RUNNING.discard(name)                     # even if a step threw

    return {"speak": _report(name, plan, steps, spoken, trouble), "results": rows}


def _report(name, plan, steps, spoken, trouble) -> str:
    """
    What to say afterwards.

    A macro of questions should read you the answers; a macro that opens
    things only needs to say it is done. The difference is whether the
    macro gave itself a line to say.
    """
    headline = (plan.get("say") or "").strip()
    if not headline:
        headline = " ".join(spoken) if spoken else f"Ran {name}."

    if not trouble:
        return headline

    missed = "; ".join(trouble)
    worked = len(steps) - len(trouble)
    return f"{headline} {worked} of {len(steps)} went through -- I had trouble with: {missed}."


def _number(value, fallback: float) -> float:
    try:
        return max(0.0, min(10.0, float(value)))   # a typo should not hang it
    except (TypeError, ValueError):
        return fallback


# --------------------------------------------------------------- Teaching

# Where the name stops and the steps start. A colon is the clearest, and
# the words below are how you would say a colon out loud.
_SPLIT = re.compile(r"\s*:\s*|\s+\bthat (?:does|runs|opens|means)\b\s+|"
                    r"\s+\bwhich (?:does|runs|opens)\b\s+|\s+\bto do\b\s+", re.I)

# One step from the next. "and then" has to be tried before plain "and",
# or the split lands on "then" and leaves a stray "and" behind.
_BETWEEN = re.compile(r"\s*,\s*|\s*;\s*|\s+\band then\b\s+|\s+\bafter that\b\s+|"
                      r"\s+\bthen\b\s+|\s+\band\b\s+", re.I)

# Words wrapped around the name when you ask for this out loud.
_NAME_JUNK = re.compile(r"\b(create|make|add|new|define|save|set up|record|"
                        r"teach|teach me|a|an|the|my|macro|routine|combo|"
                        r"shortcut|called|named|that|please)\b", re.I)

# Whatever is left glued to the front of a step once it has been split off.
# "a, then b" splits on the comma, which eats the space that the "then"
# pattern above needed -- so the leftover joining word is cleaned up here
# instead. Longest first: "and then" must be tried before "and".
_STEP_JUNK = re.compile(r"^\s*(and then|after that|then|and|also|next|"
                        r"first|second|third|finally|last(ly)?)\b", re.I)


def parse(text: str):
    """
    Pull a name and a list of steps out of a spoken sentence.

    "create a macro called start work: open chrome, open spotify"
      -> ("start work", ["open chrome", "open spotify"])
    """
    parts = _SPLIT.split(text, maxsplit=1)
    if len(parts) < 2:
        return "", []

    name = re.sub(r"\s+", " ", _NAME_JUNK.sub(" ", parts[0])).strip(" .!?,\"'")

    steps = []
    for piece in _BETWEEN.split(parts[1]):
        piece = _STEP_JUNK.sub(" ", piece or "")
        piece = re.sub(r"\s+", " ", piece).strip(" .!?,\"'")
        if piece:
            steps.append(piece)

    return name, steps[:MAX_STEPS]


def teach(name: str, steps: list) -> dict:
    """Write a macro down. Reads the steps back, because the split can slip."""
    name = re.sub(r"\s+", " ", (name or "")).strip(" .!?,\"'").lower()
    steps = [s for s in steps if s]

    if not name:
        return {"speak": "What should the macro be called? Say: create a macro "
                         "called start work, open chrome and open spotify.",
                "failed": True}
    if len(name) < 2:
        return {"speak": "That name is too short to say out loud reliably.",
                "failed": True}
    if not steps:
        return {"speak": f"What should '{name}' do? Put a colon after the name, "
                         f"then the commands, separated by commas.",
                "failed": True}

    rows = _load_custom()
    rows[name] = {"steps": steps}
    _save_custom(rows)

    listed = "; ".join(steps)
    return {"speak": f"Saved '{name}': {listed}. Say {name} to run it.",
            "results": [{"name": step, "note": "step"} for step in steps]}


def forget(name: str) -> dict:
    """Remove a macro. Built-ins get a null in your file, which hides them."""
    target = resolve(name, loose=True)
    if not target:
        return {"speak": f"I have no macro called {name}.", "failed": True}

    rows = _load_custom()
    if target in BUILTIN:
        rows[target] = None                        # tombstone over the built-in
    else:
        rows.pop(target, None)
    _save_custom(rows)

    return {"speak": f"Forgotten the macro '{target}'."}


# ---------------------------------------------------------------- Telling

def listing() -> dict:
    """Every macro, with its steps in the list underneath."""
    rows = table()
    if not rows:
        return {"speak": "No macros yet. Say: create a macro called start work, "
                         "open chrome and open spotify."}

    names = ", ".join(sorted(rows))
    detail = [{"name": name, "note": "; ".join(rows[name].get("steps", []))}
              for name in sorted(rows)]
    return {"speak": f"{len(rows)} macros: {names}. Say one to run it.",
            "results": detail}


def describe(name: str) -> dict:
    """What is in one macro, without running it."""
    target = resolve(name, loose=True)
    if not target:
        return {"speak": f"I have no macro called '{name}'. Say 'list macros' "
                         f"to hear the ones I have.", "failed": True}

    steps = table()[target].get("steps", [])
    return {"speak": f"'{target}' does {len(steps)} things: " + "; ".join(steps),
            "results": [{"name": step, "note": "step"} for step in steps]}

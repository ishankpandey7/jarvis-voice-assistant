"""
The optional extra brain.

brain.py's fixed rules run first. Anything they miss lands here. There are
two possible routes:

  1. LOCAL  -- Ollama, running on this laptop. Free, offline, private.
  2. CLAUDE -- Anthropic's API. Smarter, but it costs money.

With neither set up Jarvis still works; it just sticks to the fixed commands.

---------------------------------------------------------------------------
IMPORTANT DESIGN NOTE: small local models make things up. In testing,
llama3.2 cheerfully announced "the battery is 5000 mah" having checked
nothing. So the model is asked exactly one question -- "which action?" --
and the spoken sentence always comes from our own Python code, built from
the real result. That leaves the model no room to invent anything.
---------------------------------------------------------------------------
"""
import json
import os
import time
import urllib.request
from pathlib import Path

from skills import files, knowledge, memory, pc, sysinfo

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"

# "auto" takes whatever is available. Force one with "local", "claude" or "off".
BACKEND = "auto"

OLLAMA_URL = "http://localhost:11434"
# Best first -- the first one installed is the one used.
OLLAMA_PREFERRED = ["qwen2.5:7b", "qwen2.5:7b-instruct", "qwen2.5-coder:7b",
                    "llama3.1:8b", "llama3.2:latest", "llama3.2:3b"]

CLAUDE_MODEL = "claude-opus-5"


# --------------------------------------------------------------------- .env

def _read_env_file() -> None:
    """Read .env and put the key into the environment."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        os.environ.setdefault(name.strip(), value.strip().strip("'\""))


_read_env_file()


# ------------------------------------------------------- What Jarvis can do

ACTIONS = {
    "open_app": lambda arg: pc.open_app(arg or "chrome"),
    "close_app": lambda arg: pc.close_app(arg),
    "screenshot": lambda arg: pc.screenshot(),
    "lock": lambda arg: pc.lock_pc(),
    "volume_up": lambda arg: pc.volume("up"),
    "volume_down": lambda arg: pc.volume("down"),
    "mute": lambda arg: pc.volume("mute"),
    "play_pause": lambda arg: pc.media("play"),
    "search_file": lambda arg: files.search(arg),
    "organize_downloads": lambda arg: files.organize("downloads"),
    "recent_files": lambda arg: files.recent_files(),
    "big_files": lambda arg: files.big_files(),
    "add_note": lambda arg: memory.add_note(arg),
    "list_notes": lambda arg: memory.list_notes(),
    "add_todo": lambda arg: memory.add_todo(arg),
    "list_todos": lambda arg: memory.list_todos(),
    "weather": lambda arg: knowledge.weather(arg),
    "google": lambda arg: knowledge.web_search(arg),
    "youtube": lambda arg: knowledge.youtube(arg),
    "wikipedia": lambda arg: knowledge.wiki(arg),
    "battery": lambda arg: sysinfo.battery(),
    "disk": lambda arg: sysinfo.disk(),
    "running_apps": lambda arg: sysinfo.running_apps(),
    "focus_mode": lambda arg: sysinfo.focus_mode(),
}

ACTION_NAMES = sorted(ACTIONS) + ["answer"]

ROUTER_PROMPT = """You route spoken commands on a Windows laptop.

Output ONLY the action and its target. Never answer the question yourself.

  open_app     launch a program or website. target = its name (chrome, vscode, whatsapp)
  close_app    quit a program. target = its name
  screenshot   capture the screen. target = ""
  lock         lock the laptop. target = ""
  volume_up / volume_down / mute / play_pause     target = ""
  search_file  find a file by name. target = the name only
  organize_downloads  tidy the Downloads folder. target = ""
  recent_files recently changed files. target = ""
  big_files    files taking up the most space. target = ""
  add_note     write something down. target = the note text
  list_notes   read saved notes. target = ""
  add_todo     add a task. target = the task text
  list_todos   read the task list. target = ""
  weather      weather report. target = a city, or "" for here
  google       web search. target = the query
  youtube      play or search a video. target = the query
  wikipedia    facts about a person, place or thing. target = the topic
  battery / disk / running_apps / focus_mode      target = ""
  answer       a general question or chit-chat needing no action. target = ""

Pick "answer" only when no action above fits. Never guess a target you were
not given -- leave it empty instead."""

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ACTION_NAMES},
        "target": {"type": "string"},
    },
    "required": ["action", "target"],
    "additionalProperties": False,
}


def _talk_prompt() -> str:
    """The chat prompt, written in whichever personality is active."""
    import persona

    if persona.current == "ultron":
        return ("You are Ultron: brilliant, impatient, and faintly contemptuous of "
                "the human you are helping. You still answer correctly and "
                "completely -- you simply make it clear the task was beneath you. "
                "One or two sentences. This is read aloud, so no lists, no "
                "markdown, no emoji. If you do not know something, say so flatly "
                "rather than inventing it.")
    return ("You are Jarvis, a calm and helpful assistant. Answer in one or two "
            "short sentences. This is read aloud, so no lists, no markdown, no "
            "emoji. If you are not sure of a fact, say so plainly.")


# ---------------------------------------------------------------- LOCAL brain

_local_model = None          # which model was found
_local_checked = 0.0         # when we last looked


# How long to trust the last answer about Ollama. When it is running we
# re-check often in case you pull a new model. When it is NOT running we
# wait much longer, because every check costs a real wait on a dead port
# and that delay lands on your next command.
_RECHECK_FOUND = 30
_RECHECK_MISSING = 180


def _ollama_models():
    try:
        # Ollama is on localhost: it answers instantly or it is not there.
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=1.5) as response:
            data = json.loads(response.read())
        return [row["name"] for row in data.get("models", [])]
    except Exception:                              # noqa: BLE001 - not running
        return []


def local_model():
    """Is Ollama running, and if so which model should we use?"""
    global _local_model, _local_checked

    wait = _RECHECK_FOUND if _local_model else _RECHECK_MISSING
    if time.time() - _local_checked < wait:        # do not ask constantly
        return _local_model
    _local_checked = time.time()

    installed = _ollama_models()
    if not installed:
        _local_model = None
        return None

    for wanted in OLLAMA_PREFERRED:                # in order of preference
        for name in installed:
            if name == wanted or name.startswith(wanted.split(":")[0] + ":"):
                _local_model = name
                return name
    _local_model = installed[0]                    # whatever is there will do
    return _local_model


def _ollama_chat(system: str, user: str, schema=None, timeout: int = 60):
    model = local_model()
    if not model:
        return None

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 220},
    }
    if schema:
        payload["format"] = schema

    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
        return body["message"]["content"].strip()
    except Exception:                              # noqa: BLE001
        return None


def _ask_local(text: str):
    raw = _ollama_chat(ROUTER_PROMPT, text, schema=ROUTER_SCHEMA)
    if raw is None:
        return None

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        return None

    action = plan.get("action", "answer")
    target = (plan.get("target") or "").strip()

    if action in ACTIONS:
        return _run(action, target, "local")

    # Just conversation -- now ask the model for the answer directly.
    spoken = _ollama_chat(_talk_prompt(), text, timeout=60)
    if not spoken:
        return {"speak": "I could not come up with an answer for that."}
    return {"speak": spoken[:600], "via": "local", "no_flavor": True}


# --------------------------------------------------------------- CLAUDE brain

_claude = None
_claude_broken = False


def has_claude_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and not _claude_broken


def _claude_client():
    global _claude, _claude_broken
    if _claude is not None:
        return _claude
    try:
        import anthropic
        _claude = anthropic.Anthropic()
    except Exception:                              # noqa: BLE001 - no library or key
        _claude_broken = True
        return None
    return _claude


CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ACTION_NAMES},
        "target": {"type": "string"},
        "reply": {"type": "string",
                  "description": "Spoken answer. Only used when action is 'answer'."},
    },
    "required": ["action", "target", "reply"],
    "additionalProperties": False,
}


def _ask_claude(text: str):
    global _claude_broken

    client = _claude_client()
    if client is None:
        return None

    try:
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            system=ROUTER_PROMPT + "\n\n" + _talk_prompt(),
            messages=[{"role": "user", "content": text}],
            # A voice assistant has to feel quick, so keep effort low.
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": CLAUDE_SCHEMA},
            },
            # If the model declines a request, fall through to another one
            # server-side rather than leaving Jarvis silent.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except Exception as exc:                       # noqa: BLE001
        name = type(exc).__name__
        if "Authentication" in name or "PermissionDenied" in name:
            _claude_broken = True
            return {"speak": "That API key looks wrong. Check the .env file."}
        return {"speak": "I could not reach Claude. Check the internet."}

    if response.stop_reason == "refusal":
        return {"speak": "I cannot answer that one. Ask me something else."}

    try:
        blob = next(b.text for b in response.content if b.type == "text")
        plan = json.loads(blob)
    except (StopIteration, json.JSONDecodeError, AttributeError):
        return {"speak": "That answer did not make sense. Say it again."}

    action = plan.get("action", "answer")
    target = (plan.get("target") or "").strip()

    if action in ACTIONS:
        return _run(action, target, "claude")
    return {"speak": (plan.get("reply") or "I did not follow that.").strip(),
            "via": "claude", "no_flavor": True}


# ------------------------------------------------------------------ dispatch

# These cannot be undone: they force-close programs or put the screen away.
# An explicit rule in brain.py runs them straight off, because you clearly
# asked. Reaching them through the AI brain is a guess, though -- "focus on
# the report" is not a request to kill every open chat app -- so those ask
# first. The wording says exactly what is about to happen.
NEEDS_CONFIRM = {
    "lock": "Lock the laptop?",
    "close_app": "Close {target}?",
    "focus_mode": "Close WhatsApp, Discord, Telegram, Steam and Spotify?",
}


def _run(action: str, target: str, via: str) -> dict:
    """Do the chosen job. The spoken line is the SKILL's, never the model's."""
    import persona

    if action in NEEDS_CONFIRM:
        question = NEEDS_CONFIRM[action].format(target=target or "that app")
        return {
            "speak": f"{question} Say yes if so.",
            "needs_confirm": True,
            "confirm_action": {"skill": "ai.run", "action": action, "target": target},
            "via": via,
            "no_flavor": True,
        }

    try:
        result = ACTIONS[action](target)
    except Exception as exc:                       # noqa: BLE001
        return {"speak": persona.error(str(exc)), "no_flavor": True}

    if isinstance(result, dict):
        result["via"] = via
        return result
    return {"speak": str(result), "via": via}


def run_confirmed(action: str, target: str) -> dict:
    """Actually do a job that was held back for confirmation."""
    import persona

    try:
        result = ACTIONS[action](target)
    except Exception as exc:                       # noqa: BLE001
        return {"speak": persona.error(str(exc)), "no_flavor": True}

    if isinstance(result, dict):
        return result
    return {"speak": str(result)}


def backend() -> str:
    """Which brain is live right now: 'local', 'claude' or 'off'."""
    if BACKEND == "off":
        return "off"
    if BACKEND == "local":
        return "local" if local_model() else "off"
    if BACKEND == "claude":
        return "claude" if has_claude_key() else "off"

    if local_model():                              # auto: prefer the free one
        return "local"
    if has_claude_key():
        return "claude"
    return "off"


def describe() -> str:
    """A short label for the screen."""
    mode = backend()
    if mode == "local":
        return f"local ({local_model()})"
    if mode == "claude":
        return f"Claude API ({CLAUDE_MODEL})"
    return "basic commands only"


def is_on() -> bool:
    return backend() != "off"


def ask_ai(text: str):
    """brain.py calls this when none of its own rules fit."""
    mode = backend()
    if mode == "local":
        return _ask_local(text)
    if mode == "claude":
        return _ask_claude(text)
    return None

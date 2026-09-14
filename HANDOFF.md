# Jarvis — handoff

Paste this at the start of a new chat. Written for whoever picks the work up.

---

## What this is

A voice assistant on my Windows laptop. I talk, it listens in the browser, a
Python server does the work on the machine, and it answers out loud.

- **Lives at** `C:\dev\project1`
- **GitHub** https://github.com/ishankpandey7/jarvis-voice-assistant (public, `main`)
- **Run it** `python jarvis.py`, or double-click `start.bat`. Opens
  `http://127.0.0.1:8765` by itself.
- **Zero pip dependencies** — Python standard library, PowerShell, ctypes, and
  free keyless web APIs. Please keep it that way unless there is a strong
  reason not to.

## My machine

| | |
|---|---|
| Windows 11, Lenovo LOQ | RTX 3050 (6 GB VRAM), Ryzen 5 7235HS, 24 GB RAM |
| Python | **3.14.4** — very new, so binary wheels are often missing. Check before promising any package. |
| Ollama | installed and running, with `qwen2.5:7b` (the one Jarvis uses), `qwen2.5-coder:7b`, `llama3.2` |
| `gh` CLI | authenticated as `ishankpandey7` |
| Anthropic API key | **none.** The Claude path is written but untested. |

## How it is built

```
jarvis.py      stdlib http.server on 127.0.0.1:8765. Serves web/, takes commands.
brain.py       ~100 regex rules, tried top to bottom, first match wins.
               Specific rules above broad ones -- ORDER IS LOAD-BEARING.
ai.py          Optional second brain: local Ollama, or the Claude API.
persona.py     Two personalities (Jarvis / Ultron) -- lines and voice settings.

skills/
  pc.py        Apps, volume, brightness, screenshots, lock, clipboard
  keyboard.py  Typing and key combos via Windows SendInput (ctypes)
  recipes.py   22 apps: their search key and their own shortcuts, as DATA
  desktop.py   ~40 Windows shortcuts, ~40 ms-settings: pages
  names.py     Learned corrections for names speech recognition mangles
  files.py     Search and tidy
  memory.py    Notes, to-dos, reminders, timers
  knowledge.py Weather (Open-Meteo), Wikipedia, search, arithmetic
  sysinfo.py   Battery, disk, focus mode
  winutil.py   PowerShell and key-press plumbing

web/           index.html, style.css, app.js -- Web Speech API for ears and voice
data/          notes, todos, reminders, names.json, recipes.json. Gitignored.
```

**Three levels of understanding**, tried in order:

1. `brain.py` regex rules — instant
2. local Ollama (`qwen2.5:7b`, ~3 s) — handles loose phrasing
3. Claude API — only if a key is added

A rule that matches but *fails* also falls through to the AI. Irreversible
actions reached through the AI ask for confirmation first; the same actions
reached by a plain rule run immediately.

## Rules I want kept

- **No new dependencies** without asking me first.
- **It never sends messages.** `message ravi saying X` opens the chat and
  types, then stops and waits for me to say `send`. Keep that.
- **Destructive things confirm** when the AI guessed them: lock, close app,
  focus mode (it force-quits apps), typing.
- **Server binds to 127.0.0.1.** Changing that auto-generates an access key
  and warns loudly. Do not weaken it.
- Comments in the code are written to teach me — keep that tone, explain
  *why* rather than restating the code.

---

## Bugs I have hit, and the fixes — do not re-learn these

**Writing Python through a bash heredoc corrupts backslashes.** `\\b` came out
as a literal backspace byte (0x08), silently breaking 41 regex patterns across
three separate incidents. The file looked fine; the patterns just stopped
matching. **Use the Write/Edit tools for any code containing regex.** To check
for damage: count bytes 7, 8, 11, 12 in the `.py` files.

**Windows console is cp1252.** A `print()` containing emoji or Hindi throws
and kills that HTTP request. `jarvis.py` reconfigures stdout to UTF-8 and
wraps logging — keep both.

**`[hidden]` loses to `display: flex/grid`.** An overlay with `display: grid`
ignored its `hidden` attribute and covered the page. `style.css` forces
`[hidden] { display: none !important; }`.

**`Get-CimInstance` objects cannot have methods called on them.** Brightness
silently did nothing until it went through `Invoke-CimMethod`.

**Store apps have no shortcut file.** Camera, Photos, Xbox, the new Notepad —
scanning the Start Menu folder for `.lnk` can never find them. `pc.py` uses
`Get-StartApps` and launches through `shell:AppsFolder`.

**Tray-minimised apps have no visible window.** Telegram, Discord and WhatsApp
run with no window at all, so focusing one fails and relaunching is what
restores it. `recipes.ensure_app()` relaunches, then waits for the window.

**Search boxes do not clear when re-focused.** Pressing Ctrl+F when a search is
already open appends to it. Escape first, then Ctrl+A before typing.

**Python changes need a server restart.** `brain.py` and the skills are
imported once at startup. Files under `web/` are read fresh each request, so
those only need a browser reload.

---

## The long microphone saga — the answer, so nobody repeats it

Speech did not work at all for hours. It was **not** Jarvis. Windows'
**Input volume was 0 and muted** (Settings → System → Sound → Input → Volume).
That setting is **per device**, so switching between the laptop mic and
Bluetooth earbuds changed nothing — both were at zero.

Along the way I built a **Mic check** panel (button in the header) that tests
secure context, browser support, the microphone, *which* microphone, and
Google's speech service separately, measures every input device, and writes
`data/mic-report.json` so it can be read directly rather than described.
It works — use it before theorising.

Two things worth knowing generally:

- Chrome keeps **its own microphone choice per site** and ignores the Windows
  default. Site settings, not Sound settings.
- Chrome's speech recognition runs on **Google's servers**, not locally. A bad
  connection breaks it with a perfect microphone.

---

## What still does not work

**It cannot see the screen.** It sends keystrokes blind. "Click that button"
is impossible. Anything not reachable by a keyboard shortcut is out of reach.
This is the biggest limitation by far.

**Speech mangles Indian names.** Ravi arrives as *Robbie*. Mitigated, not
solved: `remember robbie is Ravi` teaches it permanently, and untaught names
are searched by their first four letters only. Still the weakest part.

**Picking the right search result is a guess.** `find_in_app` types a name and
presses Down then Enter. If the first result is not the one I meant, it opens
the wrong thing. No way to check without seeing the screen.

**Compound commands do not work.** "Open chrome and search for X" is one
sentence; the rules match one thing each. It usually only does the first half.

**No macros.** No way to say one word and have five things happen.

**The Claude API path is untested** — written to the current API, never run,
because I have no key.

**The voice path is only lightly tested by me**, and never by the assistant —
the in-app browser has no speech recognition, so everything was tested by
typing or over HTTP.

---

## How to test

There is no test framework. What I have been doing, and it works well: start
the server, then POST to `/api/command` with assertions.

```python
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # cp1252 console

def ask(t):
    rq = urllib.request.Request("http://127.0.0.1:8765/api/command",
        data=json.dumps({"text": t}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))

CHECKS = [("battery", "how's the battery", lambda d: "percent" in d["speak"])]
```

**33 of these pass right now.** Please keep them passing, and add to them.

To check routing without side effects (some commands really press keys):

```python
import re, brain
for i, (pattern, _) in enumerate(brain.RULES):
    if re.search(pattern, brain.clean("your command"), re.I):
        print("rule", i); break
```

Set `ai.BACKEND = "off"` to test the rules alone.

---

## What I would like next

Roughly in the order I care about:

1. **Macros** — "start work" opens VS Code, Chrome and Spotify together.
   Should be data-driven like `recipes.json`, so I can add my own.
2. **Compound commands** — "open chrome and search for X" in one sentence.
3. **More apps and shortcuts** — keep growing `recipes.py` and `desktop.py`.
4. **Offline speech-to-text** — would drop Chrome and Google entirely, work in
   any browser, let the microphone be chosen in code (the Web Speech API never
   allows that), and keep my voice on the machine. `faster-whisper` is the
   route and **`ctranslate2` does have a `cp314` wheel — I checked.** An
   earlier attempt is in the git history; it was removed as dead code.
5. **Screen awareness** — the real unlock, and much harder.

---

## How to talk to me

I am learning. Explain *why*, not just what. If I report something broken,
diagnose it before building a fix — twice now the cause was somewhere I had
not considered, and once it was a Windows setting rather than the code at all.
Tell me plainly when something is my machine rather than the program.

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

I speak English and Hindi, often in the same sentence. That is a real
requirement, not a nice-to-have.

## How it is built

```
jarvis.py      stdlib http.server on 127.0.0.1:8765. Serves web/, takes commands.
brain.py       ~130 regex rules, tried top to bottom, first match wins.
               Specific rules above broad ones -- ORDER IS LOAD-BEARING.
               Also splits compound commands, before the rules are tried.
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
  macros.py    One name, several commands -- and the step runner that
               compound commands share
  knowledge.py Weather (Open-Meteo), Wikipedia, search, arithmetic
  sysinfo.py   Battery, disk, focus mode
  winutil.py   PowerShell and key-press plumbing

web/           index.html, style.css, app.js -- Web Speech API for ears and voice
data/          notes, todos, reminders, names.json, recipes.json, macros.json.
               Gitignored -- none of my own data is ever committed.

test_jarvis.py   161 checks. Run after any change.
router_score.py  Scores how well the local model picks actions (96%).
```

**Three levels of understanding**, tried in order:

1. `brain.py` regex rules — instant
2. local Ollama (`qwen2.5:7b`, ~3 s cold, can be 10) — handles loose phrasing
3. Claude API — only if a key is added

A rule that matches but *fails* also falls through to the AI. Irreversible
actions reached through the AI ask for confirmation first; the same actions
reached by a plain rule run immediately.

### What sits above the rules

Two things are checked in `handle()` **before** the rule list, because the
rules would otherwise eat them:

- **A macro's bare name.** `start work` would otherwise be read by the broad
  open rule as "start" plus an app called "work". The match is strict — the
  whole sentence has to be the macro's name — so naming a macro `notes` does
  not break `read me my notes`.
- **Compound commands.** `open chrome and play some music` is two things; the
  rules would match the first half and drop the rest without saying so.

### Macros

`skills/macros.py`. A name with a list of commands under it. A step is just
something you would say, so a macro can do anything Jarvis can do, and
anything it learns later works in macros the same day.

Built-ins in the file, mine merged over them from `data/macros.json`, a `null`
deletes a built-in. `create a macro called X: a, then b` saves one by voice.
It will **not** answer a confirmation for me — it skips that step and says
which — and it will **not** run itself.

### Compound commands

`brain.split_commands()`. The running half was already there; the splitting is
the risky half and is deliberately reluctant. Splitting a sentence that was
never two sentences runs something I did not ask for; failing to split just
means I say the second half again.

The rule: **never split after a command that takes dictated words.** If the
part before the join is a note, reminder, search, message or something to
type, the words after the "and" probably belong to it. Every part must also
work as a command on its own.

Ask that **per part**, never of the whole sentence — that was the bug in the
first version. "open chrome and play some music" looks protected as a whole
because the music rule matches the string, but the join comes after
"open chrome", which swallows nothing.

So it refuses `remind me to call mum and dad`, `add milk and eggs to my list`,
`google cats and dogs`, `what is the difference between ram and storage`. 32
cases in the suite, deliberately more refusals than splits.

### Hindi

The common commands work in Hindi as instant rules: `chrome band karo`,
`chrome kholo`, `mera resume dhundo`, `awaaz badhao`, `gaana chalao`,
`kitni jagah bachi hai`, `kitne baje hain`, `mausam kaisa hai`,
`kya kya chal raha hai`, `laptop lock kar do`, `note likho ...`,
`yaad dila dena ...`.

Some Hindi needs no rule at all, because the English word is already in the
sentence: `storage kitna hai`, `internet chal raha hai` and
`kitni battery bachi hai` were caught by the existing rules.

## Rules I want kept

- **No new dependencies** without asking me first.
- **It never sends messages.** `message ravi saying X` opens the chat and
  types, then stops and waits for me to say `send`. Keep that.
- **Destructive things confirm** when the AI guessed them: lock, close app,
  focus mode (it force-quits apps), typing, running a macro.
- **Nothing answers a confirmation on my behalf.** Macros and compound
  commands skip a step that asks, and say which one.
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
for damage: count bytes 7, 8, 11, 12 in the `.py` files. A heredoc will also
turn `"\\n"` into a real newline inside a string literal, which is a syntax
error rather than a silent one — that is the lucky version.

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

**"Open notepad" does not give you a blank Notepad.** Windows 11 Notepad is
single-instance with session restore, so launching it surfaces whatever was
open last — with a real file in it. Same family as the tray problem below:
`open X` does not mean "a fresh X".

This is how a blind `type` / `likho` finds someone's work. It bit me: a test
said "open notepad", got back a window whose title was a file of mine that
happened to be open, checked only that the title *contained* "notepad",
decided that was good enough, and typed into it. Nothing was lost — the edits
were buffer-only and the force-close discarded them — but only by luck.

The lesson is that **Jarvis already said so and I ignored it.** Its reply
named the window it was about to type into, exactly as designed. Naming the
window is the safety feature, and it only works if something reads the name.
When testing anything that types, check the FULL window title against what
you expected, never a substring — and prefer opening a scratch file by path
over trusting an app to start empty.

**Tray-minimised apps have no visible window.** Telegram, Discord and WhatsApp
run with no window at all, so focusing one fails and relaunching is what
restores it. `recipes.ensure_app()` relaunches, then waits for the window.

**Search boxes do not clear when re-focused.** Pressing Ctrl+F when a search is
already open appends to it. Escape first, then Ctrl+A before typing.

**Python changes need a server restart.** `brain.py` and the skills are
imported once at startup. Files under `web/` are read fresh each request, so
those only need a browser reload.

**Two servers can hold port 8765 at once, and the OLDER one answers.**
Windows allows the second bind instead of refusing it, so starting a second
Jarvis looks like it worked while every request still goes to the stale one.
The symptom is alarming and misleading: the rules all seem to have vanished
and the AI answers everything. Check with `netstat -ano | findstr 8765` —
two LISTENING lines means this. `python test_jarvis.py 8766` runs the checks
against a different port so it never fights a server I already have up.

**A word can be a command and a noun.** `resume` is both "carry on playing"
and my CV, and `find my resume` is the first thing I ever ask this. The media
rule takes it only as a bare word or with something playable after it. Watch
for this whenever a new rule uses an everyday English word.

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

**The Claude API path is untested** — written to the current API, never run,
because I have no key.

**The voice path is only lightly tested by me**, and never by the assistant —
the in-app browser has no speech recognition, so everything has been tested by
typing or over HTTP.

---

## How to test

**`python test_jarvis.py`** — the checks live in the repo. **161 pass.**
Four parts:

- **routing** — which rule catches a sentence, without executing it, so it
  can safely cover `lock the laptop` and `close chrome`
- **Hindi** — the same, plus that the target comes out as `chrome` and not
  `chrome band karo`
- **compound** — what splits, and the longer list of what must not
- **macros** — the engine end to end, on a throwaway file
- **live** — real answers over HTTP, read-only commands only

It opens no apps, presses no keys and never touches `data/`. If the server is
not running it skips the live part rather than failing. Add to it.

It asserts which **skill** a rule calls, by reading the lambda's own source. A
pattern only tells you what a rule listens for, not what it does.

**`python router_score.py`** — how often the local model picks the right
action. ~3 minutes (`--quick` for a third). 70% before the router prompt was
rewritten, 96% after. The interesting output is the bucket each phrase falls
into:

- **RULE** — brain.py catches it, the model is never asked. Safe either way.
- **SAVED** — the rules miss it, the model gets it right. The AI earning its keep.
- **GAP** — the rules miss it *and* the model is wrong. Fix these.
- **RISKY** — same, but the model chose something irreversible.

**A SAVED line I say often is the best candidate for a new rule**: it already
works, but it costs 3–10 seconds instead of 0.1. That loop — score it, add a
rule, score it again — is worth more than any single rule in it. The Hindi
commands came out of exactly that loop, not a guess.

One case is left **failing on purpose** (`am i about to die` → battery). Said
out loud at a battery icon it is obvious; written down it is fair to be
confused by. Do not relabel it to make the number look better.

To check routing by hand, without side effects (some commands really press
keys):

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

1. **More apps and shortcuts** — keep growing `recipes.py` and `desktop.py`.
   Also cheap and worth doing: run `router_score.py`, find a **SAVED** line I
   say often, make it a rule.
2. **Offline speech-to-text** — would drop Chrome and Google entirely, work in
   any browser, let the microphone be chosen in code (the Web Speech API never
   allows that), and keep my voice on the machine. `faster-whisper` is the
   route and **`ctranslate2` does have a `cp314` wheel — I checked.** An
   earlier attempt is in the git history; it was removed as dead code.
3. **Screen awareness** — the real unlock, and much harder.

**On fine-tuning a model**, which I asked about: the advice I was given, and
agree with, is not yet. The eval exists now, so any change can be measured;
the hard part of fine-tuning is the dataset, not the training; and a
fine-tuned router goes stale every time a new action is added. If it ever does
happen, do it on **qwen2.5:1.5b** for the speed — a smaller, sharper router —
not on the 7B. Prompting took it 70% → 96% for free.

The one thing prompting could **not** fix: `chrome band karo` still reads as
*open* Chrome, even after being told plainly that *band karo* means close.
`spotify band karo` is fine, `band karo chrome` is fine, `chrome ko band karo`
is fine. One app, one word order, an association too strong to instruct away.
That is what a prompting ceiling looks like — and it is why there is a rule
for it instead.

---

## How to talk to me

I am learning. Explain *why*, not just what. If I report something broken,
diagnose it before building a fix — twice now the cause was somewhere I had
not considered, and once it was a Windows setting rather than the code at all.
Tell me plainly when something is my machine rather than the program.

Measure before changing something you cannot see. The 70% number existed
before any of the router work, and it is the only reason I know the work
helped.

# JARVIS

A voice assistant that runs on your own Windows laptop. You talk, it listens,
it does the thing, and it answers out loud.

It is not the Iron Man Jarvis. But it is **real**, and it does real work:
opens apps, finds files, tidies your Downloads folder, sets reminders,
reports the weather.

It also has an **Ultron** mode, which does exactly the same job while making
it clear the work is beneath it.

---

## Run it

```bash
python jarvis.py
```

Or double-click `start.bat`.

The browser opens on its own. Click the circle in the middle and speak. If you
would rather not talk, there is a box at the bottom to type in.

**Nothing to install.** Python is all you need, and you already have it. No
`pip install`, no account, no API key.

> Open it in Chrome or Edge. The microphone only works in those.

---

## What you can say

Plain English, the way you would ask a person.

### Control the machine
| Say | What happens |
|---|---|
| `open chrome` / `open camera` / `launch vs code` | opens it — every app in your Start menu, Store apps included |
| `close chrome` | quits it |
| `take a screenshot` | saved to Pictures/Jarvis |
| `set volume to 40` / `turn it up` / `mute` | sound |
| `brighter` / `dim the screen` / `set brightness to 70` | screen |
| `lock the laptop` | locks it |
| `focus mode` | closes WhatsApp, Discord, Steam and friends |
| `next track` / `pause the music` | media keys |

### Work inside a specific app
Jarvis knows its way around a handful of apps — which key opens their search,
and what their own shortcuts are.

| Say | What happens |
|---|---|
| `open the chat with ravi in telegram` | brings Telegram up, searches, opens that chat |
| `message ravi on telegram saying I'm late` | opens the chat and **types** it — see below |
| `find budget in obsidian` | opens that note |
| `new chat in telegram` / `command palette in vs code` | that app's own shortcut |
| `incognito in chrome` / `terminal in vs code` | same |
| `what can you do in telegram` | lists what it knows for that app |
| `which apps can you work in` | the whole list |

Built in: Telegram, WhatsApp, Discord, Slack, Teams, Outlook, Chrome, Edge,
Firefox, Brave, VS Code, Obsidian, Notion, Spotify, VLC, Zoom, Steam, Word,
Excel, PowerPoint, Notepad, File Explorer. Anything else falls back to a
generic Ctrl+F search, which is right more often than you would expect.

> **It never sends a message.** `message ravi saying I'm late` opens the chat
> and types the words, then stops:
> *Typed "I'm late" to ravi in telegram. Check it is the right person, then say
> send.* The contact was matched by a fuzzy search and there is no unsending a
> message to the wrong person, so the last key is always yours. Say `send`.

**Teaching it a new app** — copy `recipes.example.json` to `data/recipes.json`
and edit. Your entries merge over the built-ins, and your `actions` are added
to theirs rather than replacing them. No code, and a restart picks it up.

#### Names it keeps mishearing

Speech recognition is an English model listening to Indian names, and it
mangles them the same way every time: Ravi comes back as *Robbie*, Shreya as
*Shreyer*. The transcript is already wrong before Jarvis sees it, so nothing
downstream can rescue it — but the mistakes repeat, so they can be learned.

| Say | What happens |
|---|---|
| `remember robbie is Ravi` | from now on that word is written Ravi |
| `when I say shreyer I mean Shreya` | same thing, said differently |
| `what names do you know` | the list so far |
| `forget robbie` | drops it |

For anything it has *not* been taught, it types only the **first four letters**
into the search box. `Isha` finds Ishank whether or not the ending was heard
right, because the start of a name survives mis-hearing much better than the
whole of it, and search boxes match prefixes. When what it typed differs from
what you said, it tells you: *Searched telegram for Isha, looking for Ishank.*

Learned names live in `data/names.json`, which is never committed.

### Work inside whatever app is in front
Jarvis drives the real keyboard, so these go to the focused window whatever
it is.

| Say | What happens |
|---|---|
| `search for python tutorials` | new tab in your browser, typed and sent |
| `type hello world` | types it into the focused window |
| `switch to chrome` / `bring up notepad` | brings that window to the front |
| `new tab` / `close the tab` / `next tab` | Ctrl+T, Ctrl+W, Ctrl+Tab |
| `go back` / `refresh` / `scroll down` | browsing |
| `select all` / `copy that` / `paste` / `undo` / `save it` | the usual keys |
| `find on page` | Ctrl+F |
| `press ctrl plus shift plus n` | any key or combo you name |
| `what's in front` | tells you which window has focus |

> Typing lands in whichever window is focused, so Jarvis names it back to
> you: *Typed "hello" into agents.py - Notepad.* And if the **AI** guessed
> that you wanted typing — rather than a rule matching plainly — it asks
> first, naming the window before it touches anything.

### Windows itself
The shortcuts and settings pages that exist no matter which app is in front.

| Say | What happens |
|---|---|
| `snip` / `screenshot the area` | the region-select tool (Win+Shift+S) |
| `clipboard history` | everything you copied recently (Win+V) |
| `emoji` | the emoji picker |
| `show the desktop` / `task view` / `task manager` | getting around |
| `snap left` / `snap right` | window to half the screen |
| `new desktop` / `next desktop` | virtual desktops |
| `second screen` | the projection menu |
| `record screen` | Game Bar recording |
| `open bluetooth settings` | straight to that page, not the front door |
| `microphone settings` / `wifi settings` / `night light settings` | same |
| `what windows shortcuts do you know` / `list settings` | what it knows |

Around 40 shortcuts and 40 settings pages, in `skills/desktop.py`. Settings
pages open directly through Windows' own `ms-settings:` links, so
`open storage settings` lands on the page instead of making you hunt for it.

### Files
| Say | What happens |
|---|---|
| `find my resume` | searches by name, gives a list — click one to open it |
| `where are my pdfs` | the newest files of that type |
| `clean up downloads` | sorts them into folders by type |
| `what's taking up space` | files over 50 MB |
| `show me recent files` | the last three days of work |

> `clean up downloads` **asks first** — it tells you how many files go where,
> and only moves them once you say yes.

### Remembering things
| Say | What happens |
|---|---|
| `make a note buy milk tomorrow` | saved |
| `read my notes` | all of them |
| `add call the bank to my list` | added to the to-do list |
| `call the bank is done` | ticked off (it matches loosely, so close enough works) |
| `set a 10 minute timer` | beep plus a desktop notification |
| `remind me at 7 pm to take my medicine` | reminder |

### Looking things up
| Say | What happens |
|---|---|
| `what's the weather` / `weather in Delhi` | current conditions (it works out where you are) |
| `what is photosynthesis` | a short answer from Wikipedia |
| `what is 18 percent of 45` | arithmetic |
| `play some lofi on youtube` | opens YouTube |
| `how's the battery` / `how much space do I have` | machine health |

### In Hindi

The common commands work in Hindi too, as instant rules rather than through
the AI:

| Say | What happens |
|---|---|
| `chrome band karo` / `bandh kar do` | closes it |
| `chrome kholo` / `notion chalu karo` | opens it |
| `mera resume dhundo` / `dhoondo my thesis` | searches for the file |
| `awaaz badhao` / `awaaz kam karo` | volume up / down |
| `gaana chalao` | play/pause |
| `likho hello world` | types it into the window in front |
| `note likho milk lena hai` | saves a **note** — not typed into a window |
| `kitni jagah bachi hai` | disk space |
| `kitne baje hain` / `samay kya hai` / `tareekh kya hai` | time and date |
| `mausam kaisa hai` / `baarish hogi kya` | weather |
| `kya kya chal raha hai` / `kaun se app khule hain` | what's open |
| `laptop lock kar do` | locks it |
| `yaad dila dena 10 minute mein dawai lene ki` | reminder |

Some Hindi needs no rule at all, because the English word is sitting in the
sentence: `storage kitna hai`, `internet chal raha hai` and
`kitni battery bachi hai` were already caught by the storage, internet and
battery rules.

These exist because they were **measured**, not guessed. `router_score.py`
scores how often the local model picks the right action, and it showed
qwen2.5:7b reading `chrome band karo` as *open* Chrome — and still doing it
after the prompt was told in plain words that *band karo* means close:

```
'chrome band karo'     -> open_app    ✗     'band karo chrome'    -> close_app  ✓
'chrome bandh karo'    -> open_app    ✗     'chrome ko band karo' -> close_app  ✓
'spotify band karo'    -> close_app   ✓
```

One app, one word order, an association too strong to instruct away. Which is
the case for rules in a nutshell: **a pattern has no prior to argue with.** It
also answers instantly instead of in three seconds.

### Macros — one name, several commands

Opening VS Code, Chrome and Spotify every morning is three sentences. A macro
makes it one word.

| Say | What happens |
|---|---|
| `start work` | opens VS Code, Chrome and Spotify |
| `create a macro called study: open notion, then brightness 40` | saved, and read back to you |
| `list my macros` | every macro, with its steps |
| `what does the start work macro do` | its steps, without running it |
| `forget the study macro` | gone |

A step is just **something you would say**. There is no second language to
learn — each step goes back through the brain exactly as if you had spoken it,
so anything Jarvis can do, a macro can do, including asking it things:

> `create a macro called morning: what's the weather, what's on my list, how's the battery`

Say `morning` and it reads you all three answers.

Three built-ins ship with it — `start work`, `wind down` and `catch up` — and
you can change or delete any of them. Yours live in `data/macros.json`;
`macros.example.json` in the project root shows the shape, including `pause`
for apps that are slow to take focus.

Two things it deliberately will not do:

> **It will not say yes for you.** If a step asks "shall I?", the macro skips
> that step and tells you which one, rather than answering on your behalf. A
> step you wrote yourself that maps to a plain rule still runs straight off —
> writing it down in advance is as clear as asking gets.
>
> **It will not run itself.** A macro that names itself, or two that name each
> other, would loop forever. It stops and says so.

Saying a macro's name **on its own** beats every other rule — that is why
`start work` opens your three apps instead of hunting for an app called
"work". Anything more than the bare name goes to the normal rules, so calling
a macro `notes` does not break `read me my notes`.

### Two things in one sentence

| Say | What happens |
|---|---|
| `open chrome and play some music` | both |
| `take a screenshot then lock the laptop` | in that order |
| `what's the weather and how's the battery` | reads you both answers |
| `chrome band karo and spotify kholo` | works in Hindi too |

**What it will not do is the interesting half.** Splitting a sentence that was
never two sentences runs something you never asked for, so it refuses far more
often than it splits:

| Say | Why it stays one command |
|---|---|
| `remind me to call mum and dad` | one reminder — "dad" is part of it |
| `add milk and eggs to my list` | one item |
| `google cats and dogs` | one search |
| `what is the difference between ram and storage` | one question |
| `message ravi saying running late and sorry` | one message |

The rule underneath: **never split after a command that takes dictated
words.** If the first half is a note, a reminder, a search, a message or
something to type, then whatever follows the "and" probably belongs to it. If
the first half is `open chrome` — which swallows nothing — the "and" is a
join. Every part also has to work as a command on its own, so
`open chrome and then what` stays whole.

If it refuses a split you wanted, say **`then`** instead of `and`. And if a
step in the middle needs a yes, it is skipped and named rather than answered
for you — same rule as macros.

Forgotten what it does? Just say **`help`**.

---

## The voice

Windows ships with old, robotic text-to-speech voices (Ravi, David, Zira).
Chrome adds Google's neural voices on top, and those sound close to human.

The **Voice** dropdown in the header lists every voice you have, with the
warm, natural-sounding ones sorted to the top and marked with a ★. Pick one
and it reads a sample line so you can hear it straight away. Your choice is
remembered.

If the list only shows Microsoft names, you are not in Chrome — the Google
voices only appear there.

### Ultron mode

The dropdown next to it switches personality. Ultron does exactly the same
work, in a much deeper voice, at a slower pace, and with visible reluctance:

> **You:** how's the battery
> **Ultron:** *Was that so difficult to ask?* Battery is at 70 percent.

The whole page turns red. It is the same assistant underneath — only
`persona.py` changes.

---

## Three brains

Jarvis works at three levels. The first is always on; the other two are
optional.

| | How | Cost | Understanding |
|---|---|---|---|
| **1. Basic** | Fixed patterns (`brain.py`) | Free | Say it fairly directly |
| **2. Local AI** | Ollama, on your laptop | Free | Handles loose phrasing |
| **3. Claude API** | Anthropic's servers | Costs money | Best of the three |

Jarvis always tries **1** first, and it answers instantly. If nothing matches
— or something matches but the work fails — it hands the sentence to **2** or
**3**.

That is why `open chrome` is instant, and
`could you fire up that code editor thing` also works.

### Which one is running?
The **Brain** line when the server starts tells you.

---

## Level 2 — local AI, free and offline

Once this is set up, Jarvis sends nothing anywhere. It all stays on your laptop.

1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model:

```bash
ollama pull qwen2.5:7b
```

3. Restart Jarvis. It finds the model by itself.

**On an RTX 3050 with 6 GB of VRAM:**

Measured on this machine, routing twelve awkwardly-phrased commands:

| Model | Size | Speed | Correct |
|---|---|---|---|
| `llama3.2` (3B) | 2 GB | ~2.6 s | 8 / 12 |
| `qwen2.5-coder:7b` | 4.7 GB | ~3.3 s | 11 / 12 |
| `qwen2.5:7b` | 4.7 GB | ~3.3 s | **12 / 12 — use this one** |

The coder model is tuned for code, which is why the plain one beats it at
understanding people. First run after a reboot takes about 12 seconds while
the model loads into the GPU; every request after that is around 3 seconds.

Jarvis picks the best installed model by itself. Change the order in
`OLLAMA_PREFERRED` in `ai.py` if you want a different one.

> **Two design decisions worth understanding:**
>
> **1. The model never speaks for itself.** Small local models make things up.
> In testing, llama3.2 announced *"the battery is 5000 mah"* having checked
> nothing at all. So the model is only ever asked one question —
> **"which action?"** — and the sentence you hear is always built by Python
> from the real result. It is never given the chance to invent a fact.
>
> **2. A guess never destroys anything.** The AI is fuzzy by design, and fuzzy
> is dangerous near a force-quit. Asked to *"focus on the report"* it picked
> `focus_mode`, which would have killed every open chat app; *"lock in the
> answer"* it read as lock the screen.
>
> So anything irreversible — locking, closing a program, focus mode — runs
> **instantly** when a rule in `brain.py` matches, because then you plainly
> asked for it, and **asks first** when the AI guessed it:
>
> ```
> You:    focus on the report
> Jarvis: Close WhatsApp, Discord, Telegram, Steam and Spotify? Say yes if so.
> You:    no
> Jarvis: Alright, leaving it alone.
> ```
>
> The list in `NEEDS_CONFIRM` in `ai.py` is what gets this treatment.

---

## Level 3 — Claude API, costs money

### What is an API key?
Claude's brain runs on Anthropic's servers. An API key is a secret string
(`sk-ant-...`) that tells them "this request is mine, bill me for it".

It is **separate** from a claude.ai monthly plan. With the API you pay for
what you use, from prepaid credits. $5 is enough to start.

Cost as of September 2026:

| Model | Input / 1M | Output / 1M | Per command |
|---|---|---|---|
| `claude-opus-5` | $5 | $25 | about ₹0.50 |
| `claude-haiku-4-5` | $1 | $5 | about ₹0.10 |

100 commands a day is roughly ₹10 on Haiku, ₹50 on Opus.

### Setting it up
1. Make an account at [console.anthropic.com](https://console.anthropic.com),
   add credits, create a key
2. `pip install anthropic`
3. Create a `.env` file in this folder:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

4. Set `BACKEND = "claude"` in `ai.py` (otherwise it prefers the local model)

`.env` is in `.gitignore`, so it will never reach GitHub. **Do not share the
key with anyone, and keep it out of screenshots.**

---

## Privacy — the honest part

Even with the local model running, **one thing still leaves your laptop: your
voice.**

The listening is done by Chrome's Web Speech API, and Chrome sends the audio
to Google's servers. That is the browser's doing, not Jarvis's.

Two ways around it:
- Type instead of speaking — then nothing leaves the machine
- Later, swap in **Whisper** or **Vosk** for local speech-to-text, and Jarvis
  becomes fully offline

Everything else is already local: notes, to-dos and reminders live in `data/`,
and your files are never uploaded. Only the weather and Wikipedia need the
internet.

### Who can reach the server

Jarvis listens on `127.0.0.1` — **this laptop only**. Nobody on your wifi can
see it. Keep it that way unless you have a reason not to, because Jarvis runs
PowerShell, opens and closes programs, reads your files and clipboard, and can
lock or shut the machine down. There is no login screen in front of any of it.

If you do change `HOST` in `jarvis.py` (to use Jarvis from your phone, say),
the server notices and protects itself:

- it makes a random key at startup and prints the full link with the key in it
- every request without that key gets a `403`
- it prints the laptop's actual network address, not `0.0.0.0`, so the link
  works from another device
- it warns you, in the same window, what you have just opened up

```
   Page   : http://192.168.1.7:8765/?key=wcLhcyRMbqz6hGvL

   ! Listening on the network, not just this laptop.
   ! Anyone with the link above can run commands on this
   ! machine. Use it only on a network you trust, and
   ! close this window when you are done.
```

That key is a speed bump, not real security — the traffic is plain HTTP with
no encryption. Only do this on a network you own.

---

## What each file does

```
jarvis.py          The server. Serves the page, passes commands along.
brain.py           THE BRAIN. "what was said" -> "what to do". The rules live here.
persona.py         Who it sounds like. Jarvis and Ultron, plus the voice settings.
ai.py              The optional extra brain -- Ollama and Claude.
test_jarvis.py     The checks. Run it after changing anything.
router_score.py    Scores how often the local model picks the right action.

skills/
  pc.py            Apps, volume, brightness, screenshots, lock, clipboard
  keyboard.py      Typing, key combos, switching windows
  recipes.py       What each app's own shortcuts are -- the table to edit
  desktop.py       Windows' own shortcuts and its settings pages
  names.py         Names speech recognition keeps getting wrong
  files.py         Searching and tidying
  memory.py        Notes, to-dos, reminders, timers
  macros.py        One name, several commands -- the runner and the table
  knowledge.py     Weather (Open-Meteo), Wikipedia, search, arithmetic
  sysinfo.py       Battery, disk, focus mode
  winutil.py       Small helpers for talking to Windows

web/
  index.html       The page
  style.css        The look, including the Ultron repaint
  app.js           Listening and speaking

data/              Your notes, to-dos, reminders, learned names, your own
                   app recipes and macros. Never committed.
.env               Your API key, if you add one. Never committed.
```

### Adding a command

Add a line to the `RULES` list in `brain.py`:

```python
(r"\b(coffee|tea)\b.*\b(make|brew)\b",
 lambda m, t: "I cannot make coffee, but I can set a timer for it."),
```

Rules are tried top to bottom, so specific ones go above broad ones.

### Adding a personality

Copy a block in `persona.py` and change the lines. `voice.pitch` below 0.5
gives you the deep robot; above 1.3 gets squeaky.

---

## If something goes wrong

**Speech is not working** — press **Mic check** in the header. Speech can fail
in several unrelated ways and they need opposite fixes, so it tests each one
separately and tells you which:

| What it checks | What a failure means |
|---|---|
| Secure context | Open `http://127.0.0.1:8765`, not a network address |
| Browser support | Firefox has none. Use Chrome or Edge |
| Microphone | No device, or Chrome was never given permission |
| **Which** microphone | See below — this one catches most people out |
| Google's speech service | Your connection, not your microphone |

There is also a live level bar: talk, and it should move. If the bar moves but
speech still fails, the microphone is fine and the problem is the last row.

**Two failures worth knowing about:**

*Chrome is listening to your earbuds.* Chrome always uses whatever Windows has
set as the default input, and a web page cannot override that. Bluetooth
earbuds take that spot the moment they connect — so Chrome ends up listening to
buds sitting in their case while you talk to the laptop, and hears silence with
no error at all. Mic check names the device in use and lists the alternatives.
To switch: right-click the speaker icon in the taskbar → Sound settings →
Input → pick your laptop's Microphone Array, then reload the page.

*Chrome's speech recognition runs on Google's servers.* It is not done on your
machine, so a slow, metered or restricted connection breaks it even with a
perfect microphone. This shows up as a `network` error, or as nothing happening
at all. A different network usually fixes it; otherwise use the type box.

**It hears you but picks the wrong thing** — try the local AI (above); it makes
a real difference. Or type the command instead.

**In "Always listening" it hears me but does nothing** — that mode only acts on
speech that starts with its name. Say *"Jarvis, open chrome"*, not *"open
chrome"*. Anything without the name is shown faded, so you can see it heard you
and chose to wait. For one-off commands, click the circle instead — then no
name is needed.

**"Port 8765 is already in use"** — Jarvis is already running. Close the old
window, or change `PORT` in `jarvis.py`.

**It searches again, with the wrong spelling** — two different faults wearing
one face. Pressing a search shortcut when the box is already open does not
clear it, so the new name got appended to the last one; that is fixed. The
spelling itself is speech recognition, not Jarvis — teach it the name (above),
or say a shorter version.

**It opens the app again instead of doing the thing inside it** — this was a
real bug and it is fixed, but the cause is worth knowing. Telegram, Discord and
WhatsApp hide in the notification area rather than closing, so the process runs
with no window at all. Asking to focus one fails, and relaunching is what
restores it — which looked like "it just opens Telegram again". Jarvis now
relaunches, waits for the window to actually appear, and only then types.

**An app won't open** — Jarvis asks Windows for the whole Start menu
(`Get-StartApps`), which covers ordinary programs *and* Store apps like Camera,
Photos and Xbox. Those have no shortcut file anywhere on disk, so anything that
searches the Start Menu folder misses them entirely — this does not. If a name
still does not match, use the full one ("Google Chrome"), or add your own
nickname to `APP_ALIASES` in `skills/pc.py`.

**The volume percentage is slightly off** — Windows volume keys move in steps
of 2%, so asking for 41 gets you 40. That is normal.

**Brightness does nothing** — it only works on a laptop's built-in screen, not
on an external monitor.

---

## Ideas for later

- **Whisper for local speech-to-text** — makes Jarvis fully offline
- **Launch on startup** — put a shortcut to `start.bat` in your Startup folder
- **Control it from your phone** — change `HOST` to `0.0.0.0` in `jarvis.py`;
  it will hand you a key-protected link (see *Who can reach the server*)

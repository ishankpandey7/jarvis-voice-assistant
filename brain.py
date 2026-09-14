"""
The brain.

One job: take what was said and run the right skill.

How it works: a long list of (pattern, what to do). It tries them top to
bottom and the first match wins -- so specific rules sit near the top and
broad ones near the bottom.
"""
import re

import persona
from skills import (desktop, files, keyboard, knowledge, memory, names, pc,
                    recipes, sysinfo)

# When Jarvis asks a question ("shall I?"), the answer waits here.
_pending = {"action": None}

YES = re.compile(r"^\s*(yes|yeah|yep|yup|ok|okay|sure|do it|go ahead|please do|"
                 r"fine|alright|right|confirm)\b", re.I)
NO = re.compile(r"^\s*(no|nope|nah|don't|dont|do not|cancel|stop|leave it|"
                r"never mind|nevermind|forget it)\b", re.I)

# Strip the wake word and filler -- they only confuse the patterns.
_NOISE = re.compile(r"\b(jarvis|jarvees|javis|ultron|please|kindly|just|um|uh)\b", re.I)

# Speech recognition drops apostrophes constantly, and typing does too:
# "whats running", "hows the battery", "im done". Put them back so the
# patterns only ever have to handle one spelling.
_FIXUPS = {
    "whats": "what's", "thats": "that's", "hows": "how's", "wheres": "where's",
    "whos": "who's", "heres": "here's", "theres": "there's", "lets": "let's",
    "im": "i'm", "ive": "i've", "dont": "don't", "doesnt": "doesn't",
    "didnt": "didn't", "isnt": "isn't", "arent": "aren't", "wasnt": "wasn't",
    "cant": "can't", "wont": "won't", "shouldnt": "shouldn't",
    "wouldnt": "wouldn't", "couldnt": "couldn't", "youre": "you're",
    "theyre": "they're", "weve": "we've", "youve": "you've",
}
# Deliberately not here: "its" and "ill" are real words on their own.


def clean(text: str) -> str:
    text = (text or "").replace("’", "'")     # curly apostrophe -> straight
    text = _NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" .!?,")

    # Rebuild missing apostrophes, word by word, keeping the rest untouched.
    return " ".join(_FIXUPS.get(word.lower(), word) for word in text.split())


def reply(speak: str, **extra) -> dict:
    """Every answer has the same shape, to keep the web page simple."""
    out = {"speak": speak, "results": [], "needs_confirm": False}
    out.update(extra)
    return out


def _as_reply(value) -> dict:
    """A skill may return a string or a dict. Make them look the same."""
    if isinstance(value, dict):
        return reply(value.get("speak", ""), **{k: v for k, v in value.items()
                                                if k != "speak"})
    return reply(str(value))


def _voice(text: str) -> dict:
    """A line that is already in the assistant's own voice -- do not decorate it."""
    return reply(text, no_flavor=True)


# ---------------------------------------------------------------------------
# Each rule is (pattern, what to do). `m` is the regex match, `t` the text.
# ---------------------------------------------------------------------------

RULES = [
    # ---- Greetings and help ----------------------------------------------
    (r"^(hi|hello|hey|yo|good (morning|evening|afternoon)|how are you|"
     r"what's up|whats up|are you there|you there)\b",
     lambda m, t: _voice(persona.greeting())),
    # The lookahead keeps "what can you do in telegram" out of general help
    # and lets it reach the per-app answer further down.
    (r"\b(help|what can you do|what can i say|commands|show commands)\b(?!\s+in\b)",
     lambda m, t: HELP_TEXT),
    (r"\b(thanks|thank you|cheers|appreciate it)\b",
     lambda m, t: _voice(persona.thanks())),

    # ---- Teaching it names it keeps mishearing ---------------------------
    # Above everything else: "remember robbie is ravi" must not be read as
    # a reminder, and the words people use here are common ones.
    (r"\b(remember|learn|note) (that )?\"?([\w']+)\"? (is|means|should be) \"?([\w' ]+)\"?",
     lambda m, t: names.teach(m.group(3), m.group(5))),
    (r"\b(when i say|if i say) \"?([\w']+)\"? (i mean|write|use) \"?([\w' ]+)\"?",
     lambda m, t: names.teach(m.group(2), m.group(4))),
    (r"\bforget (the name )?\"?([\w']+)\"?$",
     lambda m, t: names.forget(m.group(2))),
    (r"\bwhat names\b|\bnames (do you|have you) (know|learned)\b|"
     r"\blist (the )?names\b",
     lambda m, t: names.listing()),

    # ---- Time and date ---------------------------------------------------
    (r"\b(what('s| is)? the time|what time is it|time is it|current time)\b",
     lambda m, t: knowledge.clock("time")),
    (r"\b(what('s| is)? the date|what day is it|today's date|todays date)\b",
     lambda m, t: knowledge.clock("date")),

    # ---- Timers and reminders (before the note and file rules) -----------
    (r"\b(timer|alarm)s?\b.*\b(show|list|what|which|any|left|pending)\b|"
     r"\b(show|list|what|which)\b.*\b(timer|alarm|reminder)s?\b",
     lambda m, t: memory.list_reminders()),
    (r"\b(timer|alarm|reminder)s?\b.*\b(cancel|clear|delete|remove|stop|off)\b|"
     r"\b(cancel|clear|delete|stop)\b.*\b(timer|alarm|reminder)s?\b",
     lambda m, t: memory.cancel_reminders()),
    (r"\btimer\b|\b(\d+|one|two|three|five|ten|fifteen|twenty|thirty)\s*"
     r"(second|sec|minute|min|hour|hr)s?\b.*\b(timer|alarm)\b",
     lambda m, t: memory.add_reminder("Timer finished", t, kind="timer")),
    (r"\bremind me\b|\breminder\b|\bdon't let me forget\b",
     lambda m, t: memory.add_reminder(_reminder_text(t), t)),

    # ---- Notes -----------------------------------------------------------
    (r"\bnotes?\b.*\b(clear|delete|erase|remove all|wipe)\b|"
     r"\b(clear|delete|erase)\b.*\bnotes\b",
     lambda m, t: memory.clear_notes()),
    (r"\b(read|show|list|what are|check)\b.*\bnotes?\b|"
     r"\bnotes?\b.*\b(read|show|list|back)\b",
     lambda m, t: memory.list_notes()),
    (r"\b(note down|make a note|take a note|write (this |that )?down|"
     r"new note|add a note|note that)\b|^\s*note[:\-]",
     lambda m, t: memory.add_note(
         _after(t, r"(?:note down|make a note|take a note|"
                   r"write (?:this |that )?down|new note|add a note|note that|note)"
                   r"\s*(?:of|that|:|-)?"))),

    # ---- To-do list ------------------------------------------------------
    (r"\b(what('s| is)? (on )?my (list|todo|to do)|show my (list|tasks|todos)|"
     r"what('s| is)? pending|what('s| is)? left|my tasks)\b",
     lambda m, t: memory.list_todos()),
    # The listing rule above runs first, so "what's on my list" never
    # reaches this one.
    (r"\b(on|to|in)\s+(my|the)\s+(list|todo|to do|tasks?)\b|"
     r"\b(add (a )?task|new task|todo|to do|as a task)\b",
     lambda m, t: memory.add_todo(_todo_text(t))),
    (r"\b(is |i'm |im |i am )?(done|finished|completed)\b|\bmark\b.*\bdone\b",
     lambda m, t: memory.finish_todo(_todo_done_text(t))),

    # ---- Files -----------------------------------------------------------
    (r"\b(clean|clean up|tidy|organi[sz]e|sort|sort out)\b.*"
     r"\b(downloads?|desktop|documents|folder)\b|"
     r"\b(downloads?|desktop|documents)\b.*\b(is a mess|are a mess|messy|"
     r"clean|tidy|organi[sz]e|sort)\b",
     lambda m, t: files.organize(_folder_name(t))),
    (r"\b(recent|latest|newest|last few)\b.*\bfiles?\b|"
     r"\bfiles?\b.*\b(recent|recently|lately|today)\b|"
     r"\bwhat (have i|did i) (been )?work(ed|ing)? on\b",
     lambda m, t: files.recent_files()),
    (r"\b(big|biggest|large|largest|huge|heavy)\b.*\bfiles?\b|"
     r"\bwhat('s| is) (taking|eating|using)\b.*\b(space|room)\b|"
     r"\bfree up space\b",
     lambda m, t: files.big_files()),
    # Searching FILES, not the web. It has to be clear which you meant, so
    # this needs either a file-ish word or a possessive ("find my resume").
    # Without that, "search for python tutorials" would go hunting through
    # your Downloads folder instead of opening a browser.
    (r"\b(find|locate|search for|look for|where is|where are|where's)\b.*"
     r"\b(file|files|photo|photos|picture|document|documents|pdf|pdfs|folder|"
     r"resume|cv|spreadsheet|presentation|song|video|download)s?\b|"
     r"\b(file|photo|document|pdf|excel|presentation|folder)s?\b.*"
     r"\b(find|search|show|list|where)\b|"
     r"\b(find|locate|where'?s?|where is)\s+(my|the)\b",
     lambda m, t: _find_files(t)),

    # ---- Opening things INSIDE an app ------------------------------------
    # These sit above the generic keyboard rules because they are more
    # specific: "open the chat with ravi" must not become "open an app
    # called ravi".
    (r"\b(message|text|dm|write to|send)\b.+\b(saying|that|:)\b",
     lambda m, t: _message(t)),
    (r"\b(open|find|go to|show)\b.*\b(chat|conversation|dm|thread)\b|"
     r"\b(chat|conversation|dm)\b.*\b(with|of|from)\b",
     lambda m, t: _open_chat(t)),
    (r"\b(find|search|look for|open)\b.+\bin (telegram|whatsapp|discord|slack|"
     r"teams|outlook|spotify|obsidian|vs ?code|visual studio code|explorer)\b",
     lambda m, t: _find_inside(t)),
    (r"^\s*send\s*(it|that|the message)?\s*$",
     lambda m, t: recipes.send_typed_message()),
    # Asking ABOUT an app comes before acting IN one, or "what can you do in
    # telegram" is read as a command to perform inside Telegram.
    (r"\bwhich apps can you\b.*\b(search|work|help) (in|inside|with)\b|"
     r"\bwhat apps do you know\b",
     lambda m, t: "I know my way around " + ", ".join(recipes.known_apps())
                  + ". Any other app gets a generic Ctrl+F search."),
    (r"\bwhat can (you|i) do in ([a-z ]+?)\s*$",
     lambda m, t: f"In {m.group(2).strip()} I know: "
                  + ", ".join(sorted(recipes.actions_for(m.group(2).strip()))[:14])
                  + "."),
    # "new chat in telegram", "command palette in vs code", "bookmark in chrome"
    (r"\bin (telegram|whatsapp|discord|slack|teams|outlook|chrome|edge|spotify|"
     r"obsidian|notepad|explorer|vs ?code|visual studio code)\s*$",
     lambda m, t: _do_inside(t, m.group(1))),

    # ---- Working inside whatever app is open -----------------------------
    # Opening a program was only half the job; these do things once it is
    # on screen. They go before the broad open/close rules at the bottom.
    # "find on page" is Ctrl+F, and must come before anything else that
    # matches the word "find".
    (r"\bfind (on|in) (the )?page\b|\bfind in\b|\bsearch (the |this )?page\b",
     lambda m, t: keyboard.press("ctrl+f")),
    # Searching the web. The file-search rule above already took anything
    # that mentioned a file, so what reaches here is a real web search.
    (r"\b(search|look up|google)\b",
     lambda m, t: keyboard.search_in_browser(
         _after(t, r"(?:search|look up|google)\s*(?:for|about|up)?"))),
    (r"\b(type|write|enter)\b\s+(?!a note\b|this down\b)",
     lambda m, t: keyboard.type_text(_typed_text(t))),
    # Bare "focus" is not here on purpose: it would swallow both "focus mode"
    # and the ordinary English "focus on the report".
    (r"\b(switch to|bring up|bring me to|show me the) \w+",
     lambda m, t: keyboard.focus_window(
         _strip_fillers(_after(t, r"(switch to|bring up|bring me to|show me the)")))),
    (r"\bnew tab\b", lambda m, t: keyboard.press("ctrl+t")),
    (r"\bclose (the )?tab\b", lambda m, t: keyboard.press("ctrl+w")),
    (r"\b(reopen|restore)( the)? tab\b", lambda m, t: keyboard.press("ctrl+shift+t")),
    (r"\b(next|switch) tab\b", lambda m, t: keyboard.press("ctrl+tab")),
    (r"\b(go back|back)\b(?!.*\bin a bit\b)", lambda m, t: keyboard.press("alt+left")),
    (r"\bgo forward\b", lambda m, t: keyboard.press("alt+right")),
    (r"\brefresh\b|\breload\b", lambda m, t: keyboard.press("f5")),
    (r"\b(scroll|page) down\b", lambda m, t: keyboard.press("pagedown")),
    (r"\b(scroll|page) up\b", lambda m, t: keyboard.press("pageup")),
    (r"\bselect all\b", lambda m, t: keyboard.press("ctrl+a")),
    (r"\b(copy that|copy it)\b", lambda m, t: keyboard.press("ctrl+c")),
    (r"\bpaste\b", lambda m, t: keyboard.press("ctrl+v")),
    (r"\bundo\b", lambda m, t: keyboard.press("ctrl+z")),
    (r"\bredo\b", lambda m, t: keyboard.press("ctrl+y")),
    (r"\bsave (it|this|the file)?\b(?!.*\bnote\b)",
     lambda m, t: keyboard.press("ctrl+s")),
    (r"\bfind (on|in) (the )?page\b|\bfind in\b", lambda m, t: keyboard.press("ctrl+f")),
    (r"\b(full ?screen|maximi[sz]e)\b", lambda m, t: keyboard.window_action("maximize")),
    (r"\bminimi[sz]e\b", lambda m, t: keyboard.window_action("minimize")),
    (r"\bpress ([a-z0-9+ ]+)$", lambda m, t: keyboard.press(
        m.group(1).strip().replace(" plus ", "+").replace(" ", "+"))),
    (r"\bwhat('s| is) (in front|focused|open right now)\b|\bwhich window\b",
     lambda m, t: f"{keyboard.active_window() or 'Nothing'} is in front."),

    # ---- Windows' own shortcuts and settings pages -----------------------
    # Asking what exists comes before asking to open one, or "list settings"
    # is read as a page named "list".
    (r"\bwhat (windows )?shortcuts\b|\blist (windows )?shortcuts\b|"
     r"\bwhat can you press\b",
     lambda m, t: "Windows shortcuts I know, among others: "
                  + ", ".join(SHORTCUT_HIGHLIGHTS) + "."),
    (r"\bwhat settings\b|\blist settings\b|\bwhich settings\b",
     lambda m, t: "Settings pages I can open directly: "
                  + ", ".join(desktop.known_settings()[:20]) + "."),
    # Then opening one: "open bluetooth settings" should land on that page,
    # not be read as an app called bluetooth.
    (r"\b(open|show|go to|take me to)?\s*([a-z ]+?)\s+settings\b|"
     r"\bsettings for ([a-z ]+)$",
     lambda m, t: desktop.settings(_settings_page(t))),
    (r"\b(snip|screenshot (the )?area|capture (a )?region|select (an )?area)\b",
     lambda m, t: desktop.shortcut("snip")),
    (r"\bclipboard history\b|\bwhat did i copy before\b",
     lambda m, t: desktop.shortcut("clipboard history")),
    (r"\b(emoji|emojis)\b", lambda m, t: desktop.shortcut("emoji")),
    (r"\b(show (the )?desktop|minimi[sz]e everything|hide everything)\b",
     lambda m, t: desktop.shortcut("show desktop")),
    (r"\b(task view|show (all )?windows)\b",
     lambda m, t: desktop.shortcut("task view")),
    (r"\btask manager\b", lambda m, t: desktop.shortcut("task manager")),
    (r"\bsnap (it |this |the window )?(to the )?(left|right)\b",
     lambda m, t: desktop.shortcut("snap " + m.group(3))),
    (r"\b(new|next|previous) desktop\b",
     lambda m, t: desktop.shortcut(m.group(1) + " desktop")),
    (r"\b(next|other|second) (monitor|screen|display)\b",
     lambda m, t: desktop.shortcut("next monitor")),
    (r"\b(second screen|project|extend (the )?display)\b",
     lambda m, t: desktop.shortcut("project")),
    (r"\b(start (menu|recording)|record (the )?screen|game bar)\b",
     lambda m, t: desktop.shortcut(
         "record screen" if "record" in t.lower() else "game bar")),

    # ---- Machine control -------------------------------------------------
    (r"\b(screenshot|screen shot|screen capture|capture the screen|"
     r"take a picture of the screen)\b",
     lambda m, t: pc.screenshot()),
    # "lock" has to be about the machine. A bare "lock in the answer"
    # must not put the screen away.
    (r"\block\s+(the\s+|my\s+)?(laptop|screen|computer|pc|machine)\b|"
     r"^\s*lock\s*(it|up)?\s*$|"
     r"\bi'?m going (away|out)\b|\bback in a bit\b",
     lambda m, t: pc.lock_pc()),
    # Cancelling a shutdown. Kept deliberately narrow: it fires only on a
    # bare "cancel"/"stop", or when shutdown is named. A broad rule here
    # would swallow "stop the music" and run shutdown /a instead.
    (r"^\s*(cancel|abort|stop|wait|never ?mind|don't)"
     r"(\s+(it|that|please))?\s*$|"
     r"\b(cancel|stop|abort|don't)\b.*\b(shut ?down|restart|reboot|"
     r"turning off|powering off)\b",
     lambda m, t: pc.power("cancel")),
    # Shutting down must name the machine, or be the whole sentence.
    # Otherwise "power off the speaker" would turn the laptop off.
    (r"^\s*shut ?down\s*$|"
     r"\bshut ?down\s+(the\s+|my\s+)?(laptop|computer|pc|machine|system)\b|"
     r"\b(power off|turn off)\s+(the\s+|my\s+)?(laptop|computer|pc|machine|system)\b",
     lambda m, t: pc.power("shutdown")),
    (r"^\s*(restart|reboot)\s*$|"
     r"\b(restart|reboot)\s+(the\s+|my\s+)?(laptop|computer|pc|machine|system)\b",
     lambda m, t: pc.power("restart")),
    # Focus mode closes apps, so a stray "focus on the bug" must not reach it.
    (r"\b(focus mode|focus time|deep work|do not disturb)\b|^\s*focus\s*$|"
     r"\b(stop distracting me|kill the distractions|close the distractions)\b",
     lambda m, t: sysinfo.focus_mode()),
    (r"\brecycle bin\b.*\b(empty|clear|clean)\b|\bempty the (recycle )?bin\b",
     lambda m, t: pc.empty_recycle_bin()),

    # ---- Sound and screen ------------------------------------------------
    (r"\b(volume|sound)\b.*?(\d{1,3})\s*(percent|%)?|"
     r"\bset (the )?(volume|sound) to (\d{1,3})\b",
     lambda m, t: pc.volume("set", _first_number(t))),
    (r"\b(mute|silence|be quiet|shut up|no sound)\b",
     lambda m, t: pc.volume("mute")),
    (r"\b(volume|sound|louder)\b.*\b(up|louder|higher|increase|raise)\b|"
     r"\b(turn it up|louder)\b",
     lambda m, t: pc.volume("up")),
    (r"\b(volume|sound|quieter)\b.*\b(down|lower|quieter|decrease|reduce)\b|"
     r"\b(turn it down|quieter)\b",
     lambda m, t: pc.volume("down")),
    (r"\b(brightness|screen)\b.*?(\d{1,3})",
     lambda m, t: pc.brightness(_first_number(t))),
    (r"\bbrightness\b.*\b(up|higher|increase|brighter|raise)\b|\bbrighter\b",
     lambda m, t: pc.brightness(step=+20)),
    (r"\bbrightness\b.*\b(down|lower|decrease|dimmer|reduce)\b|\bdim(mer)?\b",
     lambda m, t: pc.brightness(step=-20)),

    # ---- Music -----------------------------------------------------------
    (r"\b(next|skip)\b.*\b(song|track)\b|\bskip (this|it)\b|\bnext track\b",
     lambda m, t: pc.media("next")),
    (r"\b(previous|last|go back a)\b.*\b(song|track)\b",
     lambda m, t: pc.media("previous")),
    (r"\b(song|music|track|playback)\b.*\b(pause|stop)\b|"
     r"\b(pause|stop)\s+(the\s+)?(music|song|track|playback|playing)\b",
     lambda m, t: pc.media("pause")),
    (r"\bplay\b.*\b(song|music|something)\b|\bplay some\b",
     lambda m, t: _play_music(t)),

    # ---- How the machine is doing ----------------------------------------
    (r"\b(battery|charge|charging|power level)\b", lambda m, t: sysinfo.battery()),
    (r"\b(disk|storage|space|drive|how full)\b", lambda m, t: sysinfo.disk()),
    (r"\b(what('s| is) running|which apps|open apps|running apps|"
     r"what do i have open)\b",
     lambda m, t: sysinfo.running_apps()),
    (r"\b(uptime|how long (has it|have you) been (on|running)|since (the )?boot)\b",
     lambda m, t: sysinfo.uptime()),
    (r"\b(wi-?fi|internet|network|am i online|connection)\b",
     lambda m, t: sysinfo.wifi()),
    (r"\b(status|system|how('s| is) (the )?(laptop|system|everything))\b",
     lambda m, t: sysinfo.summary()),

    # ---- Clipboard -------------------------------------------------------
    (r"\bclipboard\b.*\b(read|show|what|check)\b|\bwhat did i copy\b|"
     r"\bwhat('s| is) (in|on) (the )?clipboard\b",
     lambda m, t: pc.clipboard_read()),
    (r"\bcopy (this|that)\b|\bput (this|that) (on|in) the clipboard\b",
     lambda m, t: pc.clipboard_write(
         _after(t, r"(copy this|copy that|clipboard)\s*(:|-)?"))),

    # ---- The outside world -----------------------------------------------
    (r"\b(weather|forecast|temperature|raining|hot outside|cold outside)\b",
     lambda m, t: knowledge.weather(_city(t))),
    (r"\byoutube\b|\b(play|watch|find)\b.*\bvideo\b",
     lambda m, t: knowledge.youtube(
         _after(t, r"(?:on\s+)?youtube(?:\s+for)?|play|watch|find") or "lofi")),
    (r"\b(map|maps|directions|how do i get to)\b",
     lambda m, t: knowledge.maps(
         _after(t, r"(?:on\s+)?maps?|directions to|how do i get to"))),
    (r"\b(google|search the web|search online|look (this |it )?up)\b",
     lambda m, t: knowledge.web_search(_search_term(t))),
    (r"\d\s*(percent|%|\+|-|\*|/|times|plus|minus|divided|into)|"
     r"\b(calculate|what('s| is) \d|how much is)\b",
     lambda m, t: knowledge.calculate(t)),
    (r"\b(what('s| is| are)|who('s| is| was| were)|tell me about|"
     r"how does .* work|explain)\b",
     lambda m, t: knowledge.wiki(_topic(t))),

    # ---- Opening and closing apps (last -- these are very broad) ---------
    (r"\b(close|quit|exit|kill|shut)\b",
     lambda m, t: pc.close_app(_app_name(t))),
    (r"\b(open|launch|start|run|fire up|bring up|pull up|show me)\b",
     lambda m, t: pc.open_app(_app_name(t))),
]


# ---------------------------------------------------------------------------
# Small helpers for pulling the useful part out of a sentence.
# ---------------------------------------------------------------------------

def _after(text: str, pattern: str) -> str:
    """Everything after the matched words."""
    match = re.search(pattern, text, re.I)
    return text[match.end():].strip(" :-,") if match else ""


def _before(text: str, pattern: str) -> str:
    """Everything before the matched words."""
    match = re.search(pattern, text, re.I)
    return text[:match.start()].strip(" :-,") if match else ""


def _first_number(text: str) -> int:
    match = re.search(r"\d{1,3}", text)
    return int(match.group()) if match else 50


_VERBS = (r"\b(open|launch|start|run|fire up|bring up|pull up|show me|show|"
          r"close|quit|exit|kill|shut(\s?down)?|"
          r"the|a|an|my|that|this|it|up|for me|app|application|program|"
          r"window|please|can you|could you|would you|i want to|i need to)\b")


def _app_name(text: str) -> str:
    """'open chrome' or 'chrome, open it' both give 'chrome'."""
    name = re.sub(_VERBS, " ", text, flags=re.I)
    return re.sub(r"\s+", " ", name).strip(" .!?,")


def _find_files(text: str):
    """
    A name was given -- search by name ("find my resume").
    Only a type was given -- list that type ("where are my PDFs").
    """
    term = _search_term(text)
    if len(term) >= 2:
        return files.search(term)

    for word in files.TYPE_WORDS:
        if re.search(rf"\b{word}s?\b", text, re.I):
            return files.search_by_type(word)
    return files.search(term)                      # empty, and it will say so


def _search_term(text: str) -> str:
    junk = (r"\b(find|search for|search|look for|look up|locate|"
            r"where is|where are|where's|show|list|"
            r"file|files|photo|photos|document|documents|pdf|pdfs|folder|"
            r"google|on the web|online|"
            r"the|a|an|my|that|this|it|for|called|named|about|please)\b")
    term = re.sub(junk, " ", text, flags=re.I)
    return re.sub(r"\s+", " ", term).strip(" .!?,")


def _topic(text: str) -> str:
    junk = (r"\b(what('s| is| are)|who('s| is| was| were)|tell me about|"
            r"explain|how does|how do|work|works|"
            r"the|a|an|my|is|are|was|were|do|does|to|me|please)\b")
    topic = re.sub(junk, " ", text, flags=re.I)
    return re.sub(r"\s+", " ", topic).strip(" .!?,")


def _city(text: str) -> str:
    match = re.search(r"\b(?:in|at|for)\s+([a-z\s]{3,30}?)\s*$", text, re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"\b(?:in|at|for)\s+([a-z\s]{3,30}?)\s+"
                      r"(?:weather|forecast|temperature|today|tomorrow)", text, re.I)
    return match.group(1).strip() if match else ""


def _folder_name(text: str) -> str:
    for name in ("downloads", "desktop", "documents", "pictures", "videos", "music"):
        if name in text.lower():
            return name
    return "downloads"


_LIST_TAIL = r"\b(on|to|in)\s+(my|the)\s+(list|todo|to do|tasks?)\b|\bas a task\b"


def _todo_text(text: str) -> str:
    """
    Pull the task out, whichever way round it was said:
      "add buy milk to my list"      -> after "add"
      "put buy milk on my todo"      -> before "on my todo"
    """
    body = _after(text, r"(?:add (?:a )?task|add|new task|todo|to do)\s*(?::|-)?")
    body = re.sub(_LIST_TAIL, " ", body, flags=re.I)
    body = re.sub(r"\s+", " ", body).strip(" .!?,")
    if body:
        return body

    # Nothing after the keyword, so the task must come before it.
    body = _before(text, _LIST_TAIL + r"|\b(todo|to do)\b")
    body = re.sub(r"^\s*(put|add|stick|throw)\b", " ", body, flags=re.I)
    return re.sub(r"\s+", " ", body).strip(" .!?,")


def _todo_done_text(text: str) -> str:
    """
    Pull the task name out, whichever way it was said:
      "buy milk is done"        -> before the marker
      "mark buy milk as done"   -> after "mark"
      "i'm done with buy milk"  -> after "done with"
    """
    marker = r"\b(done|finished|complete[d]?)\b"

    if re.search(r"\bmark\b", text, re.I):
        body = _after(text, r"mark")
        body = re.sub(r"\b(as )?" + marker, " ", body, flags=re.I)
    else:
        body = _before(text, r"\b(is |i'?m |i am )?" + marker)
        if not _strip_fillers(body):               # nothing useful in front
            body = _after(text, marker + r"\s*(with|on)?")   # so look behind

    return _strip_fillers(body)


def _strip_fillers(text: str) -> str:
    text = re.sub(r"\b(the|a|an|my|that|this|it|i|i'?m|am|is|with|task|item)\b",
                  " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" .!?,")


CHAT_APPS = ("telegram", "whatsapp", "discord", "slack", "teams", "outlook",
             "messenger", "signal", "instagram")


def _which_app(text: str, fallback: str = "telegram") -> str:
    """Which app was named? Falls back to the usual one for chatting."""
    low = text.lower()
    for app in list(CHAT_APPS) + recipes.known_apps():
        if app in low:
            return app
    return fallback


def _open_chat(text: str) -> dict:
    """'open the chat with ravi in telegram' -> find "ravi" inside Telegram."""
    app = _which_app(text)
    who = re.sub(r"\b(open|find|go to|show me|show|the|a|my|chat|conversation|"
                 r"dm|thread|with|of|from|in|on|please)\b", " ", text, flags=re.I)
    who = re.sub(rf"\b{app}\b", " ", who, flags=re.I)
    who = re.sub(r"\s+", " ", who).strip(" .!?,")
    if not who:
        return {"speak": f"Whose chat should I open in {app}?", "failed": True}
    # is_name matters: a person's name is what speech recognition gets
    # wrong most, so it gets the shortening and alias treatment.
    return recipes.find_in_app(app, who, is_name=True)


def _do_inside(text: str, app: str) -> dict:
    """'new chat in telegram' -> press Telegram's own new-chat shortcut."""
    what = _before(text, r"\bin\s+" + re.escape(app) + r"\s*$")
    what = re.sub(r"^\s*(do|the|a|open|press|hit)\b", " ", what, flags=re.I)
    return recipes.do_in_app(app, re.sub(r"\s+", " ", what).strip(" .!?,"))


def _find_inside(text: str) -> dict:
    """'find the budget file in obsidian' -> search inside that app."""
    match = re.search(r"\bin\s+([a-z ]+?)\s*$", text, re.I)
    app = match.group(1).strip() if match else _which_app(text)
    what = _before(text, r"\bin\s+[a-z ]+?\s*$") if match else text
    what = re.sub(r"^\s*(find|search for|search|look for|open)\b", " ", what, flags=re.I)
    what = re.sub(r"\b(the|a|my)\b", " ", what, flags=re.I)
    return recipes.find_in_app(app, re.sub(r"\s+", " ", what).strip(" .!?,"))


def _message(text: str) -> dict:
    """'message ravi on telegram saying I am late' -> type it, do not send."""
    app = _which_app(text)
    body = _after(text, r"\b(saying|that|:)\b")
    head = _before(text, r"\b(saying|that|:)\b")
    who = re.sub(r"\b(message|text|dm|write to|send (a )?(message|text)?( to)?|"
                 r"on|in|to|the|a|my|please)\b", " ", head, flags=re.I)
    who = re.sub(rf"\b{app}\b", " ", who, flags=re.I)
    who = re.sub(r"\s+", " ", who).strip(" .!?,")
    return recipes.write_message(app, who, body)


def _settings_page(text: str) -> str:
    """'open bluetooth settings' -> 'bluetooth'."""
    body = re.sub(r"\b(open|show|go to|take me to|the|my|settings|for|page|"
                  r"please)\b", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", body).strip(" .!?,")


def _typed_text(text: str) -> str:
    """'type hello world' -> 'hello world', quotes stripped if they used any."""
    body = _after(text, r"\b(type|write|enter)\b\s*(out)?\s*(:)?")
    body = re.sub(r"^(this|that|the following)\s*:?\s*", "", body, flags=re.I)
    return body.strip().strip('"“”‘’\'')


def _reminder_text(text: str) -> str:
    """'remind me at 7 to take my medicine' -> 'take my medicine'."""
    body = re.sub(r"\b(remind me|reminder|don't let me forget|set|to|that|about)\b",
                  " ", text, flags=re.I)
    body = re.sub(r"\bat\s+\d{1,2}([:.]\d{2})?\s*(am|pm)?\b", " ", body, flags=re.I)
    body = re.sub(r"\b(in\s+)?\d+\s*(second|sec|minute|min|hour|hr|day)s?\b",
                  " ", body, flags=re.I)
    body = re.sub(r"\b(tomorrow|today|tonight|morning|evening|night|later|"
                  r"o'clock|a|an|the)\b", " ", body, flags=re.I)
    body = re.sub(r"\s+", " ", body).strip(" .!?,")
    return body or "Reminder"


def _play_music(text: str) -> str:
    """A song name means YouTube; otherwise just hit play/pause."""
    song = re.sub(r"\b(play|some|song|songs|music|track|something|me|a|an|the)\b",
                  " ", text, flags=re.I)
    song = re.sub(r"\s+", " ", song).strip(" .!?,")
    if len(song) > 2:
        return knowledge.youtube(song)
    return pc.media("play")


# The ones worth saying out loud, rather than the whole alphabetical list.
# There are more in skills/desktop.py.
SHORTCUT_HIGHLIGHTS = [
    "snip", "clipboard history", "emoji", "show the desktop", "task view",
    "task manager", "snap left", "snap right", "new desktop", "next desktop",
    "second screen", "record screen",
]


HELP_TEXT = (
    "I can open and close apps, change volume and brightness, take screenshots, "
    "lock the laptop, find files, tidy your Downloads folder, keep notes and a "
    "to-do list, set timers and reminders, check the weather, look things up on "
    "Wikipedia, search Google and YouTube, do arithmetic, and report on battery "
    "and disk space. There are examples below -- click one to try it."
)


# ---------------------------------------------------------------------------
# The main job: text in, answer out.
# ---------------------------------------------------------------------------

def handle(raw_text: str) -> dict:
    text = clean(raw_text)
    if not text:
        return _voice("I did not catch that. Say it again.")

    import ai

    # First: was I waiting for an answer to a question?
    waiting = _pending["action"]
    if waiting is not None:
        _pending["action"] = None
        if YES.match(text):
            if waiting["skill"] == "files.organize":
                return _finish(_as_reply(files.organize(waiting["folder"], do_it=True)))
            if waiting["skill"] == "recipes.send":
                return _finish(_as_reply(recipes.send_typed_message()))
            if waiting["skill"] == "ai.run":
                return _finish(_as_reply(
                    ai.run_confirmed(waiting["action"], waiting["target"])))
        if NO.match(text):
            return _voice(persona.declined())
        # Neither yes nor no, so treat it as a fresh command.

    for pattern, action in RULES:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        try:
            result = _as_reply(action(match, text))
        except Exception as exc:                  # noqa: BLE001 - never crash
            return _voice(persona.error(str(exc)))

        # A rule matched but the work did not land (wrong app name, wrong
        # task name). That usually means the rule grabbed a sentence it
        # should not have -- so give the AI brain a turn.
        if result.get("failed") and ai.is_on():
            second = ai.ask_ai(text)
            if second and not second.get("failed"):
                return _finish(_as_reply(second))

        return _finish(result)

    # Nothing matched at all -- straight to the AI brain.
    if ai.is_on():
        answer = ai.ask_ai(text)
        if answer:
            return _finish(_as_reply(answer))

    return reply(persona.unknown(), unknown=True, no_flavor=True)


def _finish(result: dict) -> dict:
    """Remember any pending question, then add the personality."""
    if result.get("needs_confirm") and result.get("confirm_action"):
        _pending["action"] = result["confirm_action"]

    if not result.get("no_flavor"):
        result["speak"] = persona.flavor(result.get("speak", ""))
    return result

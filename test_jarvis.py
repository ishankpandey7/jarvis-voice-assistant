"""
The checks. Run this after changing anything:  python test_jarvis.py

Three parts, and the split matters:

  ROUTING   Does the sentence reach the right rule? Nothing is executed, so
            this can safely cover "lock the laptop" and "close chrome" --
            the commands you would never want a test suite to actually run.

  MACROS    The macro engine, end to end through the brain, using only
            read-only steps and a throwaway macros file.

  LIVE      Real answers over HTTP, exactly as the browser asks for them.
            Read-only commands only, for the same reason. Needs the server
            up; if it is not, this part is skipped rather than failed.

Nothing here opens an app, presses a key, moves a file or touches your own
data/ folder. That is deliberate -- a test run should cost you nothing.
"""
import inspect
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # cp1252 console

import ai
import brain
from skills import macros

# Point it elsewhere with:  python test_jarvis.py 8766
# Worth knowing: if a second Jarvis is started while one is already running,
# Windows lets both hold the port and the OLDER one keeps answering. The
# symptom is a test run where the rules all seem to have vanished and the AI
# answers everything -- that is a stale server, not broken code.
SERVER = "http://127.0.0.1:" + (sys.argv[1] if len(sys.argv) > 1 else "8765")

passed, failed, skipped = 0, 0, 0
failures = []


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        failures.append((label, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not ok and detail:
        print(f"        {detail}")


def section(title):
    print(f"\n{title}\n" + "-" * 70)


# ---------------------------------------------------------------- ROUTING

def rule_source(index):
    """
    Which skill a rule calls, read off the lambda itself.

    Stronger than checking the pattern text: a pattern only tells you what
    the rule listens for, and this tells you what it actually does. It is
    what catches a rule that matches the right sentence and then runs the
    wrong skill.
    """
    if not isinstance(index, int):
        return ""
    try:
        return inspect.getsource(brain.RULES[index][1])
    except (OSError, TypeError):                   # built without source
        return ""


def which_rule(text):
    """The index of the rule that would run, without running it."""
    cleaned = brain.clean(text)
    if macros.resolve(cleaned):
        return "macro"
    for index, (pattern, _) in enumerate(brain.RULES):
        if re.search(pattern, cleaned, re.I):
            return index
    return None


# (what you say, a word that must appear in the rule that catches it).
# Matching on the pattern's text rather than its number means inserting a
# rule above does not invalidate the whole file.
ROUTES = [
    ("hello", "hi|hello"),
    ("help", "help"),
    ("thanks", "thanks"),
    ("remember robbie is ravi", "remember|learn|note"),
    ("what names do you know", "what names"),
    ("what's the time", "time"),
    ("what's the date", "date"),
    ("set a 10 minute timer", "timer"),
    ("show my timers", "timer|alarm"),
    ("remind me to call mum at 6", "remind me"),
    ("read my notes", "notes?"),
    ("what's on my list", "todo|list|tasks?"),
    ("find my resume", "find|search"),
    ("clean up downloads", "tidy|organi|clean"),
    ("open chrome", "open|launch|start"),
    ("close chrome", "close|quit|exit"),
    ("lock the laptop", "lock"),
    ("take a screenshot", "screenshot|screen shot"),
    ("volume up", "volume"),
    ("set volume to 40", "volume"),
    ("brightness 30", "brightness"),
    ("how's the battery", "battery"),
    ("disk space", "disk"),
    ("what's running", "running"),
    ("what's the weather", "weather"),
    ("what is photosynthesis", "what|who|tell me about"),
    ("google python decorators", "google|search the web"),
    ("play some music", "play"),
    ("open bluetooth settings", "settings"),
    ("new chat in telegram", "telegram|whatsapp|discord"),
    ("message ravi saying running late", "message|text|tell"),
    ("what's in the clipboard", "clipboard"),
    ("focus mode", "focus"),
    ("type hello world", "type"),
    ("reopen tab", "tab"),
]

section("ROUTING -- the right rule catches the sentence (nothing runs)")
for phrase, expected in ROUTES:
    index = which_rule(phrase)
    if index is None or index == "macro":
        check(f"{phrase!r} reaches a rule", False, f"matched: {index}")
        continue
    pattern = brain.RULES[index][0]
    check(f"{phrase!r} -> rule {index}", re.search(expected, pattern, re.I) is not None,
          f"rule {index} is {pattern[:70]!r}, expected something matching {expected!r}")

section("ROUTING -- Hindi reaches the same skills, without the AI")
# Measured into existence: router_score.py showed qwen reading "chrome band
# karo" as OPEN chrome and not letting go of it. These make the model
# irrelevant for the common ones -- and instant, which is the bigger win.
for phrase, skill, target in [
    ("chrome band karo", "pc.close_app", "chrome"),
    ("chrome bandh karo", "pc.close_app", "chrome"),
    ("telegram band kar do", "pc.close_app", "telegram"),
    ("spotify band karo", "pc.close_app", "spotify"),
    ("chrome kholo", "pc.open_app", "chrome"),
    ("notion chalu karo", "pc.open_app", "notion"),
    ("mera resume dhundo", "files.search", "resume"),
    ("dhoondo my thesis", "files.search", "thesis"),
    ("awaaz badhao", 'pc.volume("up")', ""),
    ("awaaz kam karo", 'pc.volume("down")', ""),
    ("gaana chalao", 'pc.media("play")', ""),
    ("likho hello world", "keyboard.type_text", "hello world"),
    # Asking-type commands, which used to cost a round trip to the model
    ("kitni jagah bachi hai", "sysinfo.disk", ""),
    ("jagah kitni hai", "sysinfo.disk", ""),
    ("laptop lock kar do", "pc.lock_pc", ""),
    ("screen lock karo", "pc.lock_pc", ""),
    ("mausam kaisa hai", "knowledge.weather", ""),
    ("baarish hogi kya", "knowledge.weather", ""),
    ("kitne baje hain", 'knowledge.clock("time")', ""),
    ("samay kya hai", 'knowledge.clock("time")', ""),
    ("tareekh kya hai", 'knowledge.clock("date")', ""),
    ("kya kya chal raha hai", "sysinfo.running_apps", ""),
    ("kaun se app khule hain", "sysinfo.running_apps", ""),
    ("yaad dila dena dawai lene ki", "memory.add_reminder", ""),
    # A note is a note, even though it says likho
    ("note likho milk lena hai", "memory.add_note", ""),
]:
    index = which_rule(phrase)
    ok = skill in rule_source(index)
    check(f"{phrase!r} -> {skill}", ok, f"rule {index}: {rule_source(index)[:70]!r}")
    if ok and target:
        got = brain._app_name(brain.clean(phrase))
        check(f"   target is {target!r}, not the Hindi verb", got == target,
              f"got {got!r}")

# "resume" is a noun as well as a command, and "find my resume" is the
# first thing anyone asks this. The media rule must not take it.
for phrase, want_media in [("resume it", True), ("resume", True),
                           ("resume the music", True), ("carry on", True),
                           ("find my resume", False), ("where is my resume", False),
                           ("mera resume dhundo", False)]:
    index = which_rule(phrase)
    is_media = 'pc.media("play")' in rule_source(index)
    check(f"{phrase!r} -> {'media keys' if want_media else 'not the media keys'}",
          is_media == want_media, f"rule {index}: {rule_source(index)[:70]!r}")

section("ROUTING -- macro commands do not collide with ordinary ones")
for phrase, expect_macro_rule in [
    ("list my macros", True),
    ("what does the start work macro do", True),
    ("forget the start work macro", True),
    ("create a macro called x: open chrome", True),
    ("run my start work macro", True),
    # the same verbs, without the word macro, must go where they always did
    ("read me my notes", False),
    ("list my todos", False),
    ("forget robbie", False),
    ("make a note buy milk", False),
    ("run chrome", False),
]:
    index = which_rule(phrase)
    is_macro_rule = isinstance(index, int) and 3 <= index <= 7
    check(f"{phrase!r} -> {'macro rule' if expect_macro_rule else 'its own rule'}",
          is_macro_rule == expect_macro_rule, f"landed on rule {index}")


# ----------------------------------------------------------------- MACROS

section("MACROS -- saving, running and refusing")

ai_was, real_file, real_pause = ai.BACKEND, macros.CUSTOM_FILE, macros.DEFAULT_PAUSE
ai.BACKEND = "off"                              # rules only: no guessing
macros.CUSTOM_FILE = Path(__file__).resolve().parent / ".macros-test.json"
macros.DEFAULT_PAUSE = 0.0
macros.CUSTOM_FILE.unlink(missing_ok=True)

try:
    r = brain.handle("create a macro called zz check: what's the time, "
                     "then how's the battery")
    check("a macro can be made by voice", "zz check" in r["speak"], r["speak"])
    check("both steps were parsed out", len(r["results"]) == 2, r["results"])
    check("steps are stored word for word",
          macros.table()["zz check"]["steps"] == ["what's the time",
                                                  "how's the battery"],
          macros.table().get("zz check"))

    r = brain.handle("zz check")
    check("its bare name runs it", len(r["results"]) == 2, r)
    check("every step answered", all(row["note"] for row in r["results"]),
          r["results"])
    check("it reads the answers back when it has no line of its own",
          "percent" in r["speak"].lower(), r["speak"])

    brain.handle("create a macro called zz start: what's the date")
    r = brain.handle("zz start")
    check("a name beginning with a verb still runs as a macro",
          len(r.get("results", [])) == 1, r["speak"])

    brain.clear_pending()
    brain.handle("create a macro called zz ask: what's the date, clean up downloads")
    r = brain.handle("zz ask")
    check("a step wanting a yes is skipped, not answered",
          any("needs a yes" in row["note"] for row in r["results"]), r["results"])
    check("and the skip is said out loud", "trouble" in r["speak"], r["speak"])
    check("no question is left hanging afterwards",
          brain._pending["action"] is None, brain._pending)

    macros.CUSTOM_FILE.write_text('{"zz loop": {"steps": ["zz loop"]}}',
                                  encoding="utf-8")
    r = brain.handle("zz loop")
    check("a macro that runs itself is stopped",
          "running itself" in r["speak"], r["speak"])
    check("and nothing is left marked as running", not macros._RUNNING, macros._RUNNING)

    macros.CUSTOM_FILE.write_text('{"notes": {"steps": ["what\'s the date"]}}',
                                  encoding="utf-8")
    r = brain.handle("read me my notes")
    check("a macro named 'notes' does not swallow 'read me my notes'",
          not r.get("results") or "note" not in (r["results"][0] or {}),
          r["speak"])

    macros.CUSTOM_FILE.unlink(missing_ok=True)
    r = brain.handle("list my macros")
    check("listing names the built-ins",
          "start work" in r["speak"] and "catch up" in r["speak"], r["speak"])
    r = brain.handle("what does the start work macro do")
    check("describe shows the steps without running them",
          "vs code" in r["speak"].lower() and len(r["results"]) == 3, r["speak"])
    r = brain.handle("forget the wind down macro")
    check("a built-in can be removed", "wind down" not in macros.table(),
          macros.known())
    check("removal is a tombstone in your file, not an edit to the code",
          macros._load_custom().get("wind down", "absent") is None,
          macros._load_custom())

    r = ai._run("run_macro", "start work", "local")
    check("a macro the AI only guessed at asks first", r["needs_confirm"], r)
    check("and the question lists what it will do",
          "open chrome" in r["speak"], r["speak"])
    r = ai._run("run_macro", "nonsense name", "local")
    check("an invented macro name is answered plainly, not queried",
          "no macro called" in r["speak"], r["speak"])

    # These two live here, with the AI off, on purpose. Both rules mark a
    # miss as "failed", which by design hands the sentence to the AI -- so
    # with a brain running the answer is a paraphrase, not this text.
    r = brain.handle("run my nonexistent macro")
    check("a macro that does not exist says which ones do",
          "list macros" in r["speak"], r["speak"])

    # The reason "failed" is worth keeping on these rules: people say
    # "macro" as half a longer word far more often than they ask about
    # their own, and the fallthrough is what rescues those.
    r = brain.handle("explain macro economics")
    check("'explain macro economics' is not read as a macro named economics",
          "no macro called" not in r["speak"], r["speak"])
    r = brain.handle("explain the start work macro")
    check("but 'explain THE start work macro' still describes it",
          "vs code" in r["speak"].lower(), r["speak"])
finally:
    macros.CUSTOM_FILE.unlink(missing_ok=True)
    ai.BACKEND, macros.CUSTOM_FILE, macros.DEFAULT_PAUSE = ai_was, real_file, real_pause


# ------------------------------------------------------------------- LIVE

def ask(text):
    request = urllib.request.Request(
        f"{SERVER}/api/command",
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


CHECKS = [
    ("battery", "how's the battery", lambda d: "percent" in d["speak"].lower()),
    ("disk", "how much disk space", lambda d: "gb" in d["speak"].lower()),
    ("time", "what's the time", lambda d: any(c.isdigit() for c in d["speak"])),
    ("date", "what's the date", lambda d: any(c.isdigit() for c in d["speak"])),
    ("uptime", "uptime", lambda d: len(d["speak"]) > 5),
    ("running apps", "what's running", lambda d: len(d["speak"]) > 5),
    ("wifi", "am i online", lambda d: len(d["speak"]) > 5),
    ("arithmetic", "what is 18 percent of 45", lambda d: "8.1" in d["speak"]),
    ("wikipedia", "what is photosynthesis", lambda d: len(d["speak"]) > 30),
    ("weather", "what's the weather", lambda d: len(d["speak"]) > 10),
    ("notes list", "read my notes", lambda d: len(d["speak"]) > 3),
    ("todo list", "what's on my list", lambda d: len(d["speak"]) > 3),
    ("timers", "show my timers", lambda d: len(d["speak"]) > 3),
    ("names", "what names do you know", lambda d: len(d["speak"]) > 3),
    ("help", "help", lambda d: "macro" in d["speak"].lower()),
    ("macro listing", "list my macros", lambda d: "start work" in d["speak"]),
    ("macro describe", "what does the start work macro do",
     lambda d: "chrome" in d["speak"].lower()),
    ("macro name is not stolen", "explain macro economics",
     lambda d: "no macro called" not in d["speak"].lower()),
    ("app recipes", "what can you do in telegram",
     lambda d: len(d["speak"]) > 10),
    ("greeting", "hello", lambda d: len(d["speak"]) > 2),
]

section(f"LIVE -- real answers from {SERVER} (read-only commands)")
try:
    urllib.request.urlopen(f"{SERVER}/api/status", timeout=5).read()
    up = True
except (urllib.error.URLError, OSError) as exc:
    up = False
    skipped = len(CHECKS)
    print(f"  SKIP  server is not running ({exc}). Start it with: python jarvis.py")

if up:
    for label, phrase, test in CHECKS:
        try:
            answer = ask(phrase)
            check(f"{label}: {phrase!r}", test(answer), answer.get("speak"))
        except Exception as exc:                   # noqa: BLE001
            check(f"{label}: {phrase!r}", False, f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------- Verdict

print("\n" + "=" * 70)
print(f"{passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else ""))
for label, detail in failures:
    print(f"  - {label}\n      {detail}")
sys.exit(1 if failed else 0)

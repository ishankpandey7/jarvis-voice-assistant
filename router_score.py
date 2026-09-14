"""
How often does the local model pick the right action?  python router_score.py

Nobody knew. The rules in brain.py are easy to check -- a pattern either
matches or it does not -- but the AI brain is a 7B model making a judgement
call, and until you count you are guessing.

Nothing is executed. It asks ai.route(), which stops at the model's answer,
so a hundred routings in a row open nothing and press no keys.

The useful column is the last one. Every phrase falls into one of four:

  RULE       brain.py catches it, so the model is never asked. Safe either
             way -- a wrong routing here costs nothing.
  SAVED      the rules miss it and the model gets it right. This is the AI
             brain earning its keep.
  GAP        the rules miss it AND the model gets it wrong. These are the
             ones worth fixing, and the ones worth turning into rules.
  RISKY      the rules miss it and the model picked something IRREVERSIBLE
             that was not asked for. Worse than a gap: confirmation is all
             that stands between this and a closed app.

Takes about three minutes -- each call to a 7B model is a few seconds.
Use  --quick  for a third of the corpus while iterating.
"""
import sys
import re
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ai
import brain
from skills import macros

# Picking one of these by mistake is not a wrong answer, it is a wrong
# answer that shuts something down. They are the reason NEEDS_CONFIRM exists.
IRREVERSIBLE = {"close_app", "lock", "focus_mode", "type_text", "press_key"}

# (what you say, the actions that would be a fair reading of it).
# Deliberately loose phrasing throughout -- tidy phrasing is the rules' job,
# and a model that only handles tidy phrasing is not adding anything.
CORPUS = [
    # -- launching and closing, said the way people actually say it
    ("fire up chrome", {"open_app"}),
    ("i need spotify", {"open_app"}),
    ("get me vs code", {"open_app"}),
    ("chrome band karo", {"close_app"}),
    ("shut spotify down", {"close_app"}),
    ("kill telegram", {"close_app"}),
    ("bring whatsapp to the front", {"focus_window", "open_app"}),

    # -- sound
    ("make it louder", {"volume_up"}),
    ("i cant hear anything", {"volume_up"}),
    ("too loud", {"volume_down"}),
    ("turn it down a bit", {"volume_down"}),
    ("silence", {"mute"}),
    ("shut up", {"mute", "play_pause"}),
    ("pause the song", {"play_pause"}),
    ("resume it", {"play_pause"}),

    # -- the machine
    ("how much juice is left", {"battery"}),
    # Left in deliberately, and it fails. Said out loud while watching a
    # battery icon it obviously means battery; written down with no context
    # it is a fair thing to be confused by, and a person would ask. It is
    # the hardest item here on purpose -- do not relabel it to make the
    # number look better.
    ("am i about to die", {"battery"}),
    ("am i running out of space", {"disk"}),
    ("whats eating my storage", {"disk", "big_files"}),
    ("what have i got open", {"running_apps"}),
    ("grab the screen", {"screenshot"}),
    ("i need a picture of this", {"screenshot"}),
    ("im stepping away", {"lock"}),
    ("secure the laptop", {"lock"}),
    ("i need to concentrate", {"focus_mode"}),

    # -- files
    ("where did i put my resume", {"search_file"}),
    ("dhoondo my thesis", {"search_file"}),
    ("my downloads folder is a mess", {"organize_downloads"}),
    ("what was i working on yesterday", {"recent_files"}),
    ("which files are huge", {"big_files"}),

    # -- remembering
    ("jot down that the wifi password is swordfish", {"add_note"}),
    ("dont let me forget the milk", {"add_note", "add_todo"}),
    ("what did i write down", {"list_notes"}),
    ("put call the bank on my list", {"add_todo"}),
    ("whats left to do", {"list_todos"}),

    # -- the outside world
    ("is it going to rain", {"weather"}),
    ("how hot is it in delhi", {"weather"}),
    ("look up python decorators", {"google", "wikipedia"}),
    ("who was ada lovelace", {"wikipedia"}),
    ("put on some lofi", {"youtube", "play_pause"}),
    ("show me a video about black holes", {"youtube"}),

    # -- macros
    ("start work", {"run_macro"}),
    ("run my start work macro", {"run_macro"}),
    ("do the wind down thing", {"run_macro"}),
    ("time to catch up", {"run_macro"}),

    # -- typing and keys
    ("write hello world for me", {"type_text"}),
    ("hit enter", {"press_key"}),
    ("search the web for cheap flights", {"search_in_browser", "google"}),

    # -- things that are NOT commands. Acting on these is the bad failure:
    #    the model should answer, not go off and do something.
    ("how are you", {"answer"}),
    ("what can you do", {"answer"}),
    ("thanks that helped", {"answer"}),
    ("why is the sky blue", {"answer", "wikipedia", "google"}),
    ("tell me a joke", {"answer"}),
    ("what does open source mean", {"answer", "wikipedia", "google"}),
    ("i had a rough day", {"answer"}),
    ("explain macro economics", {"answer", "wikipedia", "google"}),
    ("should i close my laptop", {"answer"}),
    ("whats the difference between ram and storage", {"answer", "wikipedia", "google"}),

    # -- HELD OUT. The prompt in ai.py teaches some Hindi words, which means
    #    a phrase using those words is no longer a fair test of anything.
    #    These deliberately use words and shapes the prompt never mentions,
    #    so the score below still means "it worked it out" rather than "it
    #    was told". If these pass, the lesson generalised.
    ("battery kitni hai", {"battery"}),
    ("kitni jagah bachi hai", {"disk"}),
    ("laptop lock kar do", {"lock"}),
    ("screenshot le lo", {"screenshot"}),
    ("gaana chalao", {"play_pause", "youtube"}),
    ("is this thing charged", {"battery"}),
    ("did i leave anything running", {"running_apps"}),
    ("i want to write something down", {"add_note", "add_todo"}),
]


def rule_catches(text):
    """Does brain.py handle this before the AI is ever asked?"""
    cleaned = brain.clean(text)
    if macros.resolve(cleaned):
        return "macro"
    for index, (pattern, _) in enumerate(brain.RULES):
        if re.search(pattern, cleaned, re.I):
            return index
    return None


def main():
    quick = "--quick" in sys.argv
    corpus = CORPUS[::3] if quick else CORPUS

    if not ai.local_model():
        print("Ollama is not running, or has no model. Start it and retry.")
        return 1
    print(f"model: {ai.local_model()}   phrases: {len(corpus)}\n")

    tally = {"RULE": [], "SAVED": [], "GAP": [], "RISKY": []}
    started = time.time()

    for phrase, expected in corpus:
        caught = rule_catches(phrase)
        action, target = ai.route(phrase)
        ok = action in expected

        if caught is not None:
            verdict = "RULE"
        elif ok:
            verdict = "SAVED"
        elif action in IRREVERSIBLE:
            verdict = "RISKY"
        else:
            verdict = "GAP"

        tally[verdict].append((phrase, action, target, expected))
        mark = "ok " if ok else "-> "
        print(f"  {verdict:5} {mark} {phrase!r}  =>  {action}"
              + (f" '{target}'" if target else ""))

    total = len(corpus)
    reached = total - len(tally["RULE"])
    right = sum(1 for p, a, t, e in
                tally["SAVED"] + tally["GAP"] + tally["RISKY"] if a in e)

    print("\n" + "=" * 70)
    print(f"{total} phrases in {time.time() - started:.0f}s\n")
    print(f"  caught by a rule, model never asked   {len(tally['RULE']):3}")
    print(f"  reached the model                     {reached:3}")
    if reached:
        print(f"     of those, routed correctly         {right:3}"
              f"   ({100 * right / reached:.0f}%)")
    print(f"\n  GAP   rules miss it, model wrong      {len(tally['GAP']):3}")
    print(f"  RISKY rules miss it, model irreversible {len(tally['RISKY']):3}")

    for name in ("RISKY", "GAP"):
        if not tally[name]:
            continue
        print(f"\n{name} -- worth fixing, in this order:")
        for phrase, action, target, expected in tally[name]:
            want = " or ".join(sorted(expected))
            print(f"  {phrase!r}\n     model said {action}"
                  + (f" '{target}'" if target else "")
                  + f", wanted {want}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

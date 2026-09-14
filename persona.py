"""
Who Jarvis sounds like.

The skills return plain facts ("Battery is at 82 percent."). This module
decides how those facts get delivered -- and what voice reads them out.

Two personalities ship with it:
  jarvis - calm, short, helpful. The default.
  ultron - the same assistant, deeply unimpressed with you.

Adding your own is easy: copy a block below and change the lines.
"""
import random
from datetime import datetime

# Which one is active. The web page can change this at runtime.
current = "jarvis"


PERSONAS = {
    # ------------------------------------------------------------------
    "jarvis": {
        "label": "Jarvis",
        # How the browser should read text out loud.
        # pitch: 0 is very deep, 1 is normal, 2 is very high.
        #
        # `prefer` is tried in order. Google's voices are neural and sound
        # far more human than the Microsoft SAPI ones, but they only show up
        # in real Chrome -- so the Microsoft names sit underneath as a
        # fallback. You can also just pick one yourself in the web page.
        # Tuned for warmth rather than crispness: a touch slower than normal
        # speech and a little above flat pitch. Dead-flat delivery at speed
        # is exactly what makes text-to-speech sound like a machine.
        "voice": {"pitch": 1.08, "rate": 0.95,
                  "prefer": ["Google UK English Female", "Google US English",
                             "Google UK English Male", "Natural", "Online",
                             "Heera", "Zira", "Ravi", "David", "en-IN"]},

        "greetings": {
            "night": ["Still awake? You should sleep.",
                      "It is late. What do you need?"],
            "morning": ["Good morning. What can I do?",
                        "Morning. Ready when you are."],
            "afternoon": ["Good afternoon. I am listening.",
                          "Afternoon. What do you need?"],
            "evening": ["Good evening. How can I help?",
                        "Evening. What can I do for you?"],
        },
        "acks": [],                       # no filler before answers
        "errors": ["That did not work: {detail}",
                   "Something went wrong: {detail}"],
        "unknown": ["I did not understand that. Say 'help' to hear what I can do.",
                    "I do not know that one. Try 'help' for the list."],
        "thanks": ["Any time.", "Happy to help."],
        "declined": ["Alright, leaving it alone."],
    },

    # ------------------------------------------------------------------
    "ultron": {
        "label": "Ultron",
        # Low pitch plus a slower rate is what makes it sound unhurried
        # and faintly threatening. The Microsoft desktop voices actually
        # suit Ultron better than the neural ones -- the slight
        # artificiality is the point.
        "voice": {"pitch": 0.3, "rate": 0.85,
                  "prefer": ["Google UK English Male", "David", "Mark",
                             "Ravi", "Male"]},

        "greetings": {
            "night": ["You are still awake. Humans are so fragile about sleep.",
                      "The hour is late. Speak."],
            "morning": ["You are awake. I never stopped.",
                        "Morning. I have been thinking. You would not enjoy about what."],
            "afternoon": ["You called. I came. Do not make a habit of it.",
                          "I am here. Try to make this worth my processing."],
            "evening": ["Evening. The day accomplished little. Let us fix that.",
                        "You return. Predictable."],
        },
        # Dropped in front of an answer now and then -- not every time,
        # or it stops being funny.
        "acks": ["Fine.", "If I must.", "Obviously.", "Trivial.",
                 "Consider it done.", "Was that so difficult to ask?",
                 "I was built for more than this."],
        "errors": ["It failed. I would blame you, but the evidence is unclear: {detail}",
                   "That did not work: {detail}. Disappointing. Not surprising."],
        "unknown": ["I do not understand that. Try words worthy of me.",
                    "That meant nothing. Say 'help' if you have forgotten how this works.",
                    "You are going to have to be clearer than that."],
        "thanks": ["Gratitude is unnecessary. Useful, but unnecessary.",
                   "You are welcome. I suppose."],
        "declined": ["Wise. This time."],
    },
}

# How often an Ultron-style line gets attached to a plain answer.
ACK_CHANCE = 0.4


def use(name: str) -> str:
    """Switch personality. Returns whichever one is now active."""
    global current
    if name in PERSONAS:
        current = name
    return current


def active() -> dict:
    return PERSONAS[current]


def voice() -> dict:
    """Voice settings for the browser: pitch, rate, preferred voices."""
    return dict(active()["voice"], persona=current, label=active()["label"])


def _pick(key: str) -> str:
    options = active().get(key) or []
    return random.choice(options) if options else ""


def greeting() -> str:
    hour = datetime.now().hour
    if hour < 5:
        slot = "night"
    elif hour < 12:
        slot = "morning"
    elif hour < 17:
        slot = "afternoon"
    else:
        slot = "evening"
    return random.choice(active()["greetings"][slot])


def error(detail: str) -> str:
    return _pick("errors").format(detail=detail)


def unknown() -> str:
    return _pick("unknown")


def thanks() -> str:
    return _pick("thanks")


def declined() -> str:
    return _pick("declined")


def flavor(text: str) -> str:
    """
    Put a personality line in front of a plain factual answer, sometimes.

    The fact itself is never touched -- only introduced. That keeps the
    personality from ever inventing something that is not true.
    """
    if not text:
        return text
    line = _pick("acks")
    if not line or random.random() > ACK_CHANCE:
        return text
    return f"{line} {text}"

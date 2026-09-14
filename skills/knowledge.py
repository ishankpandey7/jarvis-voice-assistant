"""
Information from the outside world: weather, Wikipedia, search, arithmetic.

No API key is needed anywhere here -- these are all free services.
"""
import ast
import json
import operator
import re
import urllib.parse
import urllib.request
from datetime import datetime

from .winutil import open_path

_AGENT = {"User-Agent": "Jarvis/1.0 (personal assistant)"}


def _get_json(url: str, timeout: int = 12):
    """Fetch JSON. Returns None if the network is down."""
    try:
        request = urllib.request.Request(url, headers=_AGENT)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception:                              # noqa: BLE001 - no network, no data
        return None


# ------------------------------------------------------------------ Weather
#
# Open-Meteo is the source: free, no key, and far more reliable than
# wttr.in, which times out often enough to be annoying.
#
# Set this if the automatic location guess gets your city wrong.
DEFAULT_CITY = ""

# Open-Meteo reports the sky as a WMO number. These are the ones that matter.
_SKY = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy",
    51: "drizzling", 53: "drizzling", 55: "drizzling heavily",
    56: "freezing drizzle", 57: "freezing drizzle",
    61: "raining lightly", 63: "raining", 65: "raining heavily",
    66: "freezing rain", 67: "freezing rain",
    71: "snowing lightly", 73: "snowing", 75: "snowing heavily",
    77: "snow grains", 80: "showery", 81: "showery", 82: "heavy showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thundery", 96: "thunderstorms with hail", 99: "thunderstorms with hail",
}

_here = None                                       # looked up once, then kept


# Words that mean "where I am", not a place to look up. An AI brain often
# fills the target with one of these, and geocoding "here" finds a real
# village called Here.
_MEANS_HERE = {"here", "now", "today", "outside", "my location", "current location",
               "this place", "local", "where i am", "me"}


def _locate(city: str):
    """Turn a city name into coordinates, or find out where we are."""
    global _here

    if city.strip().lower() in _MEANS_HERE:
        city = ""

    if city.strip():
        found = _get_json(
            "https://geocoding-api.open-meteo.com/v1/search?count=1&format=json&name="
            + urllib.parse.quote(city.strip())
        )
        try:
            top = found["results"][0]
            return top["latitude"], top["longitude"], top["name"]
        except (KeyError, IndexError, TypeError):
            return None

    if _here is not None:
        return _here

    spot = _get_json("https://ipapi.co/json/")     # rough, but no key needed
    try:
        _here = (spot["latitude"], spot["longitude"], spot["city"])
        return _here
    except (KeyError, TypeError):
        return None


def weather(city: str = "") -> str:
    """Current conditions, for a named city or wherever you are."""
    where = _locate(city or DEFAULT_CITY)
    if where is None:
        return ("I could not work out which place you meant. Try naming a city, "
                "like 'weather in Delhi'.")
    lat, lon, name = where

    data = _get_json(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min"
        "&timezone=auto&forecast_days=1"
    )
    if not data:
        return "I could not get the weather. The internet may be down."

    try:
        now = data["current"]
        temp = round(now["temperature_2m"])
        feels = round(now["apparent_temperature"])
        humidity = round(now["relative_humidity_2m"])
        sky = _SKY.get(now["weather_code"], "unsettled")
        high = round(data["daily"]["temperature_2m_max"][0])
        low = round(data["daily"]["temperature_2m_min"][0])
    except (KeyError, IndexError, TypeError):
        return "The weather reply did not make sense."

    line = f"It is {temp} degrees in {name} and {sky}."
    if abs(feels - temp) >= 2:
        line += f" Feels more like {feels}."
    line += f" Humidity {humidity} percent, with a high of {high} and a low of {low}."

    if temp >= 38:
        line += " Stay inside, it is too hot."
    elif "rain" in sky or "shower" in sky or "drizzl" in sky:
        line += " Take an umbrella."
    elif "thunder" in sky:
        line += " Best stay in."
    return line


# ---------------------------------------------------------------- Wikipedia

def wiki(topic: str) -> str:
    """A short answer from Wikipedia."""
    topic = topic.strip()
    if not topic:
        return "What would you like to know about?"

    slug = urllib.parse.quote(topic.replace(" ", "_"))
    data = _get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}")

    if not data or data.get("type", "").endswith("not_found") or not data.get("extract"):
        # No direct page, so search and take the first result.
        found = _get_json(
            "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
            + urllib.parse.quote(topic) + "&format=json&srlimit=1"
        )
        try:
            title = found["query"]["search"][0]["title"]
        except (KeyError, IndexError, TypeError):
            return f"I found nothing about '{topic}'."
        data = _get_json(
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(title.replace(" ", "_"))
        )
        if not data or not data.get("extract"):
            return f"I found nothing about '{topic}'."

    text = data["extract"]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:3])                 # two or three lines is plenty to hear


# ------------------------------------------------------------------- Search

def web_search(query: str) -> str:
    open_path("https://www.google.com/search?q=" + urllib.parse.quote(query))
    return f"Searching Google for '{query}'."


def youtube(query: str) -> str:
    open_path("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query))
    return f"Searching YouTube for '{query}'."


def maps(query: str) -> str:
    open_path("https://www.google.com/maps/search/" + urllib.parse.quote(query))
    return f"Looking up '{query}' on the map."


# --------------------------------------------------------------- Arithmetic
# eval() is dangerous, so this is a small safe calculator instead.

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_evaluate(node.operand))
    raise ValueError("only simple arithmetic is allowed")


_WORD_TO_SIGN = [
    (r"\b(plus|add|and)\b", "+"),
    (r"\b(minus|subtract|less)\b", "-"),
    (r"\b(times|multiplied by|multiply by|multiply|into|x)\b", "*"),
    (r"\b(divided by|divide by|divide|over)\b", "/"),
    (r"\b(to the power of|power)\b", "**"),
]


def calculate(expression: str) -> str:
    """Arithmetic like '18 percent of 45' or '12 times 7'."""
    text = expression.lower().strip()

    percent = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*(?:of|off)?\s*"
                        r"(\d+(?:\.\d+)?)", text)
    if percent:                                    # "18 percent of 45"
        part, whole = float(percent.group(1)), float(percent.group(2))
        return f"{part:g} percent of {whole:g} is {whole * part / 100:g}"

    for pattern, sign in _WORD_TO_SIGN:
        text = re.sub(pattern, sign, text)
    text = re.sub(r"[^0-9+\-*/().% ]", "", text).replace("%", "/100")

    if not re.search(r"\d", text):
        return "I did not follow that. Try '12 times 7' or '18 percent of 45'."
    try:
        answer = _evaluate(ast.parse(text.strip(), mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
        return "I could not work that out."

    if isinstance(answer, float) and answer.is_integer():
        answer = int(answer)
    elif isinstance(answer, float):
        answer = round(answer, 4)
    return f"That is {answer}."


# -------------------------------------------------------------------- Clock

def clock(what: str = "time") -> str:
    now = datetime.now()
    if what == "date":
        return f"Today is {now:%A}, {now:%d %B %Y}."
    return f"It is {now:%I:%M %p}."

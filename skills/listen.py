"""
Speech to text, done on this laptop.

This is optional, and it exists because the browser's own speech recognition
has two problems: it only exists in Chrome and Edge, and it does the actual
recognition on Google's servers -- so it fails on a slow or restricted
connection, and your voice leaves the machine either way.

With faster-whisper installed, the browser only records the audio; the words
are worked out here. Nothing leaves the laptop and any browser will do.

To turn it on:

    pip install faster-whisper

The first run downloads the model (about 75 MB for "base") and takes a few
seconds. After that a short command transcribes in well under a second.

If faster-whisper is not installed, Jarvis simply keeps using the browser's
recognition -- nothing breaks.
"""
import io
import threading
import time

# Bigger models hear better and run slower:
#   tiny   ~75 MB   fastest, makes mistakes on accents
#   base   ~145 MB  good balance -- the default
#   small  ~480 MB  noticeably better on Indian English, still quick
#   medium ~1.5 GB  better again, slower
MODEL_SIZE = "base"

# "auto" tries the GPU and quietly falls back to the processor. CUDA through
# ctranslate2 needs cuDNN installed, which often is not, and the processor is
# fast enough for one spoken sentence anyway.
DEVICE = "auto"

_model = None
_model_error = ""
_lock = threading.Lock()        # two requests must not load the model at once


def available() -> bool:
    """Is local speech to text possible at all?"""
    if _model_error:
        return False
    try:
        import faster_whisper                      # noqa: F401
        return True
    except ImportError:
        return False


def _load():
    """Load the model once, on first use."""
    global _model, _model_error

    if _model is not None or _model_error:
        return _model

    with _lock:
        if _model is not None or _model_error:     # another thread beat us here
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            _model_error = "faster-whisper is not installed"
            return None

        attempts = ([("cuda", "float16"), ("cpu", "int8")] if DEVICE == "auto"
                    else [(DEVICE, "int8" if DEVICE == "cpu" else "float16")])

        for device, precision in attempts:
            try:
                _model = WhisperModel(MODEL_SIZE, device=device,
                                      compute_type=precision)
                print(f"   Ears   : local ({MODEL_SIZE} on {device})")
                return _model
            except Exception as exc:               # noqa: BLE001 - try the next one
                last = exc

        _model_error = f"could not load the model: {last}"
        return None


def describe() -> str:
    if not available():
        return "browser (Chrome's, via Google)"
    return f"local ({MODEL_SIZE})"


def transcribe(audio: bytes) -> dict:
    """
    Turn recorded audio into text.

    Takes whatever the browser recorded -- usually WebM/Opus -- and hands it
    straight to the model, which decodes it itself.
    """
    if not audio:
        return {"text": "", "error": "no audio arrived"}

    model = _load()
    if model is None:
        return {"text": "", "error": _model_error or "local speech is unavailable"}

    started = time.time()
    try:
        segments, info = model.transcribe(
            io.BytesIO(audio),
            language="en",                # commands are in English
            beam_size=1,                  # one pass is plenty for a short phrase
            vad_filter=True,              # drop the silence around the words
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,   # each command stands alone
        )
        text = " ".join(seg.text for seg in segments).strip()
    except Exception as exc:              # noqa: BLE001 - bad audio, bad model, anything
        return {"text": "", "error": str(exc)}

    return {
        "text": text,
        "seconds": round(time.time() - started, 2),
        "heard_seconds": round(getattr(info, "duration", 0), 1),
    }

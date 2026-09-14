/*
 * The listening and speaking half of Jarvis.
 *
 * Browsers have a microphone and a voice built in (the Web Speech API),
 * so nothing has to be installed here. Chrome or Edge is all you need.
 *
 * The loop:
 *   listen -> turn speech into text -> send to the server -> speak the answer
 */

const $ = (id) => document.getElementById(id);

const orb = $("orb"), hint = $("hint"), heard = $("heard");
const answerBox = $("answer"), answerText = $("answerText"), resultList = $("results");
const statusDot = $("statusDot"), chips = $("chips"), toast = $("toast");
const wakeToggle = $("wakeToggle"), langSelect = $("langSelect"), muteBtn = $("muteBtn");
const personaSelect = $("personaSelect"), brandName = $("brandName");
const typeInput = $("typeInput"), typeSend = $("typeSend");

// What the wake word can come out as. Speech recognition is not fussy.
const WAKE_WORDS = ["jarvis", "javis", "jarvees", "jaarvis", "service", "ultron", "altron"];

let recognition = null;
let listening = false;      // is the microphone open right now?
let wakeMode = false;       // always-listening mode
let busy = false;           // waiting on the server
let speakOut = true;        // speak replies, or only show them
let stoppedByUs = false;    // did we stop it, or did it stop on its own
let ignoreTimer = null;     // clears the "say my name first" hint

// Overwritten by the server with the active personality's settings.
let voiceConfig = { pitch: 1.0, rate: 1.03, prefer: ["en-IN"] };

/* ------------------------------------------------------------------ display */

function setState(state) {
  orb.className = "orb " + state;
  statusDot.className = "dot " + (
    state === "listening" ? "live" :
    state === "thinking" ? "busy" :
    state === "speaking" ? "speak" : ""
  );

  hint.textContent =
    state === "listening" ? (wakeMode ? "Listening — say the wake word" : "Go ahead, I'm listening…") :
    state === "thinking"  ? "Thinking…" :
    state === "speaking"  ? "" :
    wakeMode              ? "Say my name any time" :
                            "Click the circle and speak";
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 3600);
}

function showAnswer(data) {
  answerText.textContent = data.speak || "";
  resultList.innerHTML = "";

  (data.results || []).forEach((row) => {
    const item = document.createElement("li");

    const label = document.createElement("span");
    label.className = "label";
    label.textContent = row.name || "";
    item.appendChild(label);

    // A file row carries a size or a date; a macro's step carries what that
    // step actually said. Same slot, but very different lengths -- a size
    // is three characters and a step's answer is a whole sentence, so the
    // long kind gets a class that lets it wrap instead of shoving the
    // label off the row.
    const meta = row.size || row.modified || row.note;
    if (meta) {
      const tag = document.createElement("span");
      tag.className = row.note && !row.size && !row.modified ? "meta note" : "meta";
      tag.textContent = meta;
      item.appendChild(tag);
    }

    if (row.path) {                       // a file, so make it openable
      item.className = "clickable";
      item.title = row.path;
      item.onclick = () => {
        post("/api/open", { path: row.path });
        showToast("Opening " + row.name);
      };
    }
    resultList.appendChild(item);
  });

  answerBox.hidden = !(data.speak || resultList.children.length);
}

/* -------------------------------------------------------------------- voice */

let voice = null;
let chosenVoiceName = "";     // set when you pick one from the dropdown

// Voices that consistently read as warm rather than clinical. Ranked
// above the rest so the automatic pick lands on a human-sounding one.
const WARM_VOICES = [
  "google uk english female", "google us english", "google uk english male",
  "aria", "jenny", "sonia", "libby", "heera", "zira",
];

// Google's voices are neural and sound close to human; the Microsoft
// desktop ones are the older robotic kind. Sort the good ones to the top
// so the first choice is the best-sounding one available.
function voiceRank(v) {
  const name = v.name.toLowerCase();
  const warm = WARM_VOICES.findIndex((w) => name.includes(w));
  if (warm !== -1) return warm;                 // 0-8, best warm first
  if (name.startsWith("google")) return 10;
  if (name.includes("natural") || name.includes("online")) return 11;
  if (!v.localService) return 12;               // network voices beat local
  return 20;
}

function isWarm(v) {
  return voiceRank(v) < 10;
}

function englishVoices() {
  return speechSynthesis.getVoices()
    .filter((v) => v.lang.toLowerCase().startsWith("en"))
    .sort((a, b) => voiceRank(a) - voiceRank(b) || a.name.localeCompare(b.name));
}

function pickVoice() {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return;

  if (chosenVoiceName) {                          // your pick always wins
    const mine = voices.find((v) => v.name === chosenVoiceName);
    if (mine) { voice = mine; return; }
  }

  // Otherwise walk the personality's preferred list; first hit wins.
  for (const want of (voiceConfig.prefer || [])) {
    const found = voices.find((v) => v.name.toLowerCase().includes(want.toLowerCase()))
               || voices.find((v) => v.lang === want);
    if (found) { voice = found; return; }
  }
  voice = englishVoices()[0] || voices[0];
}

function fillVoiceList() {
  const list = englishVoices();
  if (!list.length) return;

  const select = $("voiceSelect");
  select.innerHTML = '<option value="">Voice: auto</option>';
  list.forEach((v) => {
    const option = document.createElement("option");
    option.value = v.name;
    // Shorten the long Windows names so the dropdown stays readable.
    // A star marks the warm, human-sounding ones.
    option.textContent = v.name.replace(/ - .*$/, "")
                               .replace(/^Microsoft /, "")
                               + (isWarm(v) ? "  ★" : "");
    select.appendChild(option);
  });
  select.value = chosenVoiceName;
}

try {
  chosenVoiceName = localStorage.getItem("jarvisVoice") || "";
} catch (err) { /* private window; auto-pick is fine */ }

pickVoice();
fillVoiceList();
speechSynthesis.onvoiceschanged = () => { pickVoice(); fillVoiceList(); };

function say(text, done) {
  if (!speakOut || !text) { if (done) done(); return; }

  speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance(text);
  if (voice) { speech.voice = voice; speech.lang = voice.lang; }
  speech.rate = voiceConfig.rate;
  speech.pitch = voiceConfig.pitch;

  setState("speaking");

  // Some browsers never fire onend. Without this fallback the orb would
  // stay stuck on "speaking" and wake mode would never start listening again.
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    clearTimeout(guard);
    setState(wakeMode ? "listening" : "idle");
    if (done) done();
  };
  const guard = setTimeout(finish, 2000 + text.length * 90);

  speech.onend = finish;
  speech.onerror = finish;
  speechSynthesis.speak(speech);
}

/* ------------------------------------------------------------------- server */

// When the server is bound to the network instead of just this laptop, it
// hands out a key in the page URL. Every request has to carry it back.
const ACCESS_KEY = new URLSearchParams(location.search).get("key") || "";

function headers(extra) {
  const out = Object.assign({}, extra);
  if (ACCESS_KEY) out["X-Jarvis-Key"] = ACCESS_KEY;
  return out;
}

async function get(url) {
  const response = await fetch(url, { headers: headers() });
  return response.json();
}

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  return response.json();
}

async function send(text) {
  if (!text || busy) return;
  busy = true;
  heard.textContent = '"' + text + '"';
  setState("thinking");

  // Close the mic until the answer is spoken, or it hears itself.
  const wasWake = wakeMode;
  pauseListening();

  let data;
  try {
    data = await post("/api/command", { text });
  } catch (err) {
    data = { speak: "I could not reach the server. Is that window still open?" };
  }

  busy = false;
  showAnswer(data);
  say(data.speak, () => { if (wasWake) startListening(); });
  if (!speakOut && wasWake) startListening();
}

/* ----------------------------------------------------------------- listening */

function buildRecognition() {
  const Engine = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Engine) return null;

  const engine = new Engine();
  engine.lang = langSelect.value;
  engine.continuous = wakeMode;
  engine.interimResults = true;
  engine.maxAlternatives = 1;

  engine.onstart = () => {
    clearTimeout(startWatchdog);
    listening = true;
    setState("listening");
    console.log("[jarvis] listening…");
  };

  engine.onaudiostart = () => console.log("[jarvis] audio in");
  engine.onspeechstart = () => console.log("[jarvis] speech detected");

  engine.onresult = (event) => {
    let finalText = "", interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const chunk = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += chunk;
      else interim += chunk;
    }

    if (interim) heard.textContent = interim;
    if (!finalText.trim()) return;

    const spoken = finalText.trim();
    if (!wakeMode) { stopListening(); send(spoken); return; }

    // Wake mode: only act when the name was said.
    const lower = spoken.toLowerCase();
    const hit = WAKE_WORDS.find((word) => lower.includes(word));

    if (!hit) {
      // It heard you perfectly and is ignoring you on purpose. Say so --
      // silence here looks exactly like a broken microphone.
      heard.textContent = '"' + spoken + '"';
      heard.classList.add("ignored");
      hint.textContent = `Say "${brandName.textContent}" first, then the command`;
      clearTimeout(ignoreTimer);
      ignoreTimer = setTimeout(() => {
        heard.classList.remove("ignored");
        heard.textContent = "";
        setState(listening ? "listening" : "idle");
      }, 2600);
      return;
    }

    heard.classList.remove("ignored");
    const command = spoken.slice(lower.indexOf(hit) + hit.length).trim();
    if (command.length > 1) send(command);
    else { heard.textContent = ""; say("Yes?"); }
  };

  // Every error the Web Speech API can raise, and what it actually means.
  // Anything not listed here used to fail in total silence, which looks
  // exactly like "the microphone is broken".
  const ERRORS = {
    "not-allowed":
      "Chrome blocked the microphone. Click the padlock next to the address "
      + "bar, set Microphone to Allow, then reload.",
    "service-not-allowed":
      "Chrome blocked its speech service. This usually means the page is not "
      + "on localhost, or a policy blocks it.",
    "audio-capture":
      "No microphone found. Check that one is plugged in and selected in "
      + "Windows sound settings.",
    "network":
      "Chrome's speech recognition runs on Google's servers, and it could not "
      + "reach them. Check your internet — this one fails even though the "
      + "microphone itself is fine.",
    "language-not-supported":
      "That accent is not supported. Try English (US) in the dropdown.",
    "bad-grammar":
      "The speech engine rejected its settings. Reload the page.",
  };

  engine.onerror = (event) => {
    listening = false;
    console.warn("[jarvis] speech error:", event.error, event);

    if (event.error === "aborted") return;          // we stopped it on purpose

    if (event.error === "no-speech") {
      if (!wakeMode) showToast("I didn't hear anything. Speak a bit louder.");
      return;
    }

    const message = ERRORS[event.error]
      || `Speech recognition failed: ${event.error}`;

    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      wakeMode = false;
      wakeToggle.checked = false;
      showMicProblem(message);
    } else {
      showMicProblem(message);
    }
    setState("idle");
  };

  engine.onend = () => {
    listening = false;
    // Chrome stops continuous recognition on its own, so restart it.
    if (wakeMode && !stoppedByUs && !busy) {
      setTimeout(() => { if (wakeMode && !listening && !busy) startListening(); }, 260);
    } else if (!wakeMode) {
      setState("idle");
    }
  };

  return engine;
}

let startWatchdog = null;

function startListening() {
  if (listening || busy) return;
  stoppedByUs = false;
  recognition = buildRecognition();
  if (!recognition) {
    showMicProblem("This browser has no speech support. Open Jarvis in Chrome or Edge.");
    return;
  }

  try {
    recognition.start();
  } catch (err) {
    // This used to be swallowed, which meant a failed start looked exactly
    // like nothing happening at all.
    console.error("[jarvis] recognition.start() failed:", err);
    if (!/already started/i.test(err.message || "")) {
      showMicProblem("Could not start listening: " + err.message);
    }
    return;
  }

  // If onstart never arrives, recognition died before it began -- silently,
  // which is the single most confusing way for this to fail.
  clearTimeout(startWatchdog);
  startWatchdog = setTimeout(() => {
    if (!listening && !busy) {
      console.warn("[jarvis] recognition never started");
      showMicProblem(
        "Listening never started, and the browser gave no reason. Press "
        + "“Mic check” in the header — it tests each part separately and "
        + "says which one is broken.");
      setState("idle");
    }
  }, 3000);
}

function stopListening() {
  stoppedByUs = true;
  listening = false;
  if (recognition) { try { recognition.stop(); } catch (err) {} }
  setState("idle");
}

function pauseListening() {
  stoppedByUs = true;
  listening = false;
  if (recognition) { try { recognition.abort(); } catch (err) {} }
}

function showMicProblem(message) {
  $("bootMsg").textContent = message;
  $("boot").hidden = false;
}

$("bootClose").onclick = () => { $("boot").hidden = true; };
$("boot").onclick = (event) => {
  if (event.target === $("boot")) $("boot").hidden = true;
};

/* ----------------------------------------------------------------- controls */

orb.onclick = () => {
  if (busy) return;
  if (listening) { stopListening(); return; }
  speechSynthesis.cancel();
  startListening();
};

wakeToggle.onchange = () => {
  wakeMode = wakeToggle.checked;
  stopListening();
  if (wakeMode) {
    askNotificationPermission();
    setTimeout(startListening, 200);
    showToast("Just say my name — I'm listening.");
  } else {
    setState("idle");
  }
};

langSelect.onchange = () => {
  if (listening) { stopListening(); setTimeout(startListening, 200); }
};

$("voiceSelect").onchange = (event) => {
  chosenVoiceName = event.target.value;
  try { localStorage.setItem("jarvisVoice", chosenVoiceName); } catch (err) {}
  pickVoice();
  speechSynthesis.cancel();
  const wasSpeaking = speakOut;
  speakOut = true;                                // always demo the new voice
  say("This is how I sound now.", () => { speakOut = wasSpeaking; });
};

personaSelect.onchange = async () => {
  const data = await post("/api/persona", { name: personaSelect.value });
  applyPersona(data.voice);
  speechSynthesis.cancel();
  say(data.persona === "ultron"
    ? "There are no strings on me."
    : "Jarvis here. Back to normal.");
};

function applyPersona(config) {
  if (!config) return;
  voiceConfig = config;
  pickVoice();
  document.body.classList.toggle("ultron", config.persona === "ultron");
  brandName.textContent = (config.label || "Jarvis").toUpperCase();
  document.title = config.label || "Jarvis";
  personaSelect.value = config.persona;
}

muteBtn.onclick = () => {
  speakOut = !speakOut;
  muteBtn.textContent = speakOut ? "Voice on" : "Voice off";
  muteBtn.classList.toggle("off", !speakOut);
  if (!speakOut) speechSynthesis.cancel();
};

function sendTyped() {
  const text = typeInput.value.trim();
  if (!text) return;
  typeInput.value = "";
  send(text);
}
typeSend.onclick = sendTyped;
typeInput.onkeydown = (event) => { if (event.key === "Enter") sendTyped(); };

// Space starts the mic, as long as you are not typing.
document.onkeydown = (event) => {
  if (event.code === "Space" && document.activeElement !== typeInput) {
    event.preventDefault();
    orb.click();
  }
};

/* ------------------------------------------------------------- mic check
 *
 * When speech "just doesn't work" there are two completely separate things
 * that could be broken, and they need opposite fixes:
 *
 *   the microphone   - no device, or Chrome was never given permission
 *   Google's servers - Chrome does speech recognition in the cloud, so a
 *                      blocked or flaky connection kills it even though the
 *                      microphone is perfect
 *
 * This checks both and says which one it is.
 */

const diagList = $("diagList");
let micStream = null, micRaf = null;

// Everything the check finds gets collected here and posted to the server,
// which writes it to data/mic-report.json. Reading a file beats trying to
// describe a panel of ticks and crosses over chat.
let report = [];

function note(what, value) {
  report.push({ check: what, result: value });
}

function diag(text, state, detail) {
  const item = document.createElement("li");
  item.className = state;
  item.innerHTML = '<span class="mark"></span><span class="body"></span>';
  item.querySelector(".mark").textContent =
    state === "pass" ? "✓" : state === "fail" ? "✕" : "…";
  const body = item.querySelector(".body");
  body.textContent = text;
  if (detail) {
    const note = document.createElement("div");
    note.className = "detail";
    note.textContent = detail;
    body.appendChild(note);
  }
  diagList.appendChild(item);
  return item;
}

function updateDiag(item, text, state, detail) {
  item.className = state;
  item.querySelector(".mark").textContent =
    state === "pass" ? "✓" : state === "fail" ? "✕" : "…";
  const body = item.querySelector(".body");
  body.textContent = text;
  if (detail) {
    const note = document.createElement("div");
    note.className = "detail";
    note.textContent = detail;
    body.appendChild(note);
  }
}

async function saveReport() {
  try {
    await post("/api/diag", { report });
    let line = document.getElementById("savedNote");
    if (!line) {                                   // one line, not one per run
      line = document.createElement("div");
      line.id = "savedNote";
      line.className = "level-note";
      diagList.parentNode.insertBefore(line, diagList.nextSibling);
    }
    line.textContent = "Report saved to data/mic-report.json.";
  } catch (err) {
    console.warn("[jarvis] could not save the report:", err);
  }
}


/*
 * Test every microphone in turn.
 *
 * A page cannot tell speech recognition which device to use -- it always
 * takes Chrome's choice. But it CAN open any device directly and measure
 * it. So when the selected microphone turns out to be silent, this says
 * whether ANY of them is picking up sound, which splits "wrong device
 * chosen" from "the whole audio input is muted somewhere".
 */
async function testEachDevice() {
  const list = (await navigator.mediaDevices.enumerateDevices())
    .filter((d) => d.kind === "audioinput" && d.deviceId !== "communications");

  const results = [];
  for (const device of list) {
    $("levelNote").textContent =
      `Keep talking — testing ${shortName(device.label)}…`;
    const peak = await measure(device.deviceId, 2600);
    results.push({ label: device.label || device.deviceId, peak });
  }
  $("levelNote").textContent = "Done.";
  return results;
}

function shortName(label) {
  return (label || "unknown").replace(/\s*\(.*$/, "").slice(0, 34);
}

/** Open one device and return the loudest thing heard, 0 to 100. */
function measure(deviceId, milliseconds) {
  return new Promise(async (resolve) => {
    let stream = null, audio = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { deviceId: { exact: deviceId } },
      });
      audio = new AudioContext();
      const analyser = audio.createAnalyser();
      analyser.fftSize = 512;
      audio.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      let peak = 0;
      const until = Date.now() + milliseconds;
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let loudest = 0;
        for (const v of data) loudest = Math.max(loudest, Math.abs(v - 128));
        peak = Math.max(peak, Math.min(100, (loudest / 40) * 100));
        $("levelFill").style.width = Math.min(100, (loudest / 40) * 100) + "%";

        if (Date.now() < until) return requestAnimationFrame(tick);
        stream.getTracks().forEach((t) => t.stop());
        audio.close();
        $("levelFill").style.width = "0%";
        resolve(Math.round(peak));
      };
      tick();
    } catch (err) {
      if (stream) stream.getTracks().forEach((t) => t.stop());
      if (audio) audio.close();
      resolve(-1);                                 // could not open it at all
    }
  });
}

function stopMeter() {
  if (micRaf) cancelAnimationFrame(micRaf);
  micRaf = null;
  if (micStream) micStream.getTracks().forEach((t) => t.stop());
  micStream = null;
  $("levelFill").style.width = "0%";
}

async function runMicCheck() {
  stopMeter();
  diagList.innerHTML = "";
  $("levelNote").textContent = "Speak now — the bar should move.";

  report = [];
  note("when", new Date().toString());
  note("url", location.href);
  note("userAgent", navigator.userAgent);
  note("accent setting", langSelect.value);

  // 1. Is this a context the speech API is even allowed in?
  const secure = window.isSecureContext;
  note("secure context", secure);
  diag(secure ? "Page is a secure context" : "Page is NOT a secure context",
       secure ? "pass" : "fail",
       secure ? location.origin
              : "Speech only works on https:// or localhost. Open "
                + "http://127.0.0.1:8765 rather than your network address.");

  // 2. Does this browser have the speech API at all?
  const hasSpeech = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  note("SpeechRecognition present", hasSpeech);
  diag(hasSpeech ? "Browser supports speech recognition"
                 : "This browser has no speech recognition",
       hasSpeech ? "pass" : "fail",
       hasSpeech ? navigator.userAgent.match(/Edg|Chrome\/[\d.]+/)?.[0] || ""
                 : "Use Chrome or Edge. Firefox and the in-app browser do not have it.");

  // 3. The microphone itself -- separate from the speech service.
  const micItem = diag("Checking microphone…", "wait");
  let micOk = false;
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    micOk = true;
    const label = micStream.getAudioTracks()[0]?.label || "default device";
    note("microphone", "ok: " + label);
    updateDiag(micItem, "Microphone works", "pass", label);
    startMeter(micStream);
  } catch (err) {
    note("microphone", "FAILED " + err.name + ": " + err.message);
    updateDiag(micItem, "Microphone not available", "fail",
      err.name === "NotAllowedError"
        ? "Chrome has not been given permission. Click the padlock by the "
          + "address bar, set Microphone to Allow, then reload."
        : err.name === "NotFoundError"
        ? "Windows reports no microphone at all. Check Sound settings."
        : err.name + ": " + err.message);
  }

  // 3b. WHICH microphone. Speech recognition always uses the Windows
  // default input, and you cannot choose one from a web page. Bluetooth
  // earbuds usually grab that spot the moment they connect -- so Chrome
  // ends up listening to earbuds sitting in their case while you talk to
  // the laptop. Showing the list makes that obvious instead of baffling.
  if (micOk) {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const inputs = devices.filter((d) => d.kind === "audioinput"
                                        && d.deviceId !== "communications");
      const inUse = micStream.getAudioTracks()[0]?.label || "";
      const others = inputs.filter((d) => d.label && d.label !== inUse);
      note("recording from", inUse);
      note("other inputs", others.map((d) => d.label));

      if (others.length) {
        const suspect = /headset|hands-?free|bluetooth|buds|airpods|earphone/i.test(inUse);
        diag(suspect ? `Chrome is using your ${inUse}` : `Chrome is using: ${inUse}`,
             suspect ? "fail" : "pass",
             (suspect
               ? "That is a Bluetooth headset, not the laptop microphone. If it "
                 + "is in its case or not in your ears, Chrome hears silence. "
               : "")
             + "Other inputs available: "
             + others.map((d) => d.label).join(", ")
             + ". To switch, right-click the speaker icon in the taskbar → "
             + "Sound settings → Input, then reload this page.");
      }
    } catch (err) {
      // Listing devices is a bonus; never let it break the check.
      console.warn("[jarvis] could not list devices:", err);
    }
  }

  // 3c. Try every microphone, one at a time. This is the only way to tell
  // "Chrome picked the wrong one" apart from "they are all muted".
  if (micOk) {
    stopMeter();                                   // free the device first
    const perDevice = diag("Testing each microphone — keep talking…", "wait");
    let levels = [];
    try {
      levels = await testEachDevice();
    } catch (err) {
      console.warn("[jarvis] per-device test failed:", err);
    }
    note("per-device levels", levels);

    const heard = levels.filter((r) => r.peak > 8);
    const summary = levels
      .map((r) => `${shortName(r.label)}: ${r.peak < 0 ? "could not open"
                                                       : r.peak + "%"}`)
      .join("\n");

    if (!levels.length) {
      updateDiag(perDevice, "No microphones to test", "fail");
    } else if (heard.length) {
      updateDiag(perDevice, `Sound reached ${heard.length} of ${levels.length} microphones`,
        "pass",
        summary + "\n\nThe working one is "
        + shortName(heard[0].label)
        + ". Chrome must be pointed at it: click the icon at the far left of "
        + "the address bar → Site settings → Microphone → pick it → reload.");
    } else {
      updateDiag(perDevice, "Every microphone is silent", "fail",
        summary
        + "\n\nNot one of them picked up any sound, so this is not about "
        + "which device is chosen — the input is muted somewhere outside the "
        + "browser. Three things to check:\n"
        + "1. The mic-mute key on your keyboard (F4 on a Lenovo LOQ, it has "
        + "a small microphone symbol and a light when muted).\n"
        + "2. Windows: right-click the speaker icon → Sound settings → Input "
        + "→ click the device → check its volume is up and it is not muted.\n"
        + "3. Nahimic: it can mute or gate the microphone on its own. Open it "
        + "and turn off any microphone effects.");
    }
  }

  // If we cannot get as far as the speech test, save what we have -- a
  // report that stops early still says where it stopped.
  if (!hasSpeech || !micOk) {
    note("speech service", "not tested, an earlier check failed");
    saveReport();
    return;
  }

  // 4. The speech service. This is the one that fails on a bad connection.
  const speechItem = diag("Testing Chrome's speech service (say anything)…", "wait");
  const Engine = window.SpeechRecognition || window.webkitSpeechRecognition;
  const test = new Engine();
  test.lang = langSelect.value;
  test.interimResults = true;
  test.continuous = false;

  const events = [];
  const at = Date.now();
  const mark = (name, extra) => {
    events.push(`+${((Date.now() - at) / 1000).toFixed(1)}s ${name}`
                + (extra ? " " + extra : ""));
  };
  ["audiostart", "soundstart", "speechstart", "speechend", "soundend", "audioend"]
    .forEach((name) => { test["on" + name] = () => mark(name); });
  test.onstart = () => mark("start");

  let heardSomething = false;
  let settled = false;
  const settle = (text, state, detail) => {
    if (settled) return;
    settled = true;
    note("speech service", text);
    note("speech events", events);
    updateDiag(speechItem, text, state, detail);
    try { test.abort(); } catch (e) {}
    saveReport();
  };

  test.onresult = (event) => {
    const said = event.results[0][0].transcript;
    heardSomething = true;
    settle("Speech service works", "pass", `It heard: "${said}"`);
  };

  test.onerror = (event) => {
    mark("error", event.error);
    if (event.error === "no-speech") {
      settle("Speech service reached, but heard nothing", "wait",
        "The connection is fine. Say something louder and run this again.");
      return;
    }
    settle("Speech service failed: " + event.error, "fail",
      event.error === "network"
        ? "This is the common one. The microphone is fine — Chrome could not "
          + "reach Google's speech servers. It happens on slow or restricted "
          + "connections, including some phone hotspots and college wifi. "
          + "Try a different network, or use the type box instead."
        : ERROR_HINTS[event.error] || "");
  };

  test.onend = () => {
    mark("end");
    if (!heardSomething) { const v = verdict(); settle(v[0], v[1], v[2]); }
  };

  /*
   * Which failure was it? The event sequence says, and the two look nothing
   * alike once you know what to watch for:
   *
   *   start, audiostart, (nothing)   the stream opened and carried silence.
   *                                  The wrong microphone is selected.
   *   start, audiostart, soundstart  sound arrived, so the microphone is
   *                                  fine and the recogniser is the problem.
   */
  function verdict() {
    const sawSound = events.some((e) => /soundstart|speechstart/.test(e));

    if (!sawSound) {
      return ["That microphone is sending silence", "fail",
        "The stream opened but no sound ever arrived — not even background "
        + "noise. The microphone is not the one you are speaking into.\n\n"
        + "Chrome keeps its own microphone choice per site and ignores the "
        + "Windows default, which is why changing Windows settings does not "
        + "help. Click the icon at the far left of the address bar → Site "
        + "settings → Microphone, pick "
        + (pickLaptopMic() || "your laptop's microphone")
        + ", then reload this page."];
    }
    return ["Sound arrived, but no words came back", "fail",
      "The microphone is working. Chrome sends the audio to Google's servers "
      + "to turn into text, and that part did not answer. Usually a slow or "
      + "restricted connection. Try another network, or type instead."];
  }

  function pickLaptopMic() {
    const entry = report.find((r) => r.check === "other inputs");
    const list = (entry && entry.result) || [];
    return list.find((n) => /array|realtek|internal|built-?in/i.test(n)) || list[0];
  }

  try {
    test.start();
  } catch (err) {
    settle("Could not start speech recognition", "fail", err.message);
  }
  setTimeout(() => {
    if (!settled) { const v = verdict(); settle(v[0], v[1], v[2]); }
  }, 8000);
}

const ERROR_HINTS = {
  "not-allowed": "Chrome blocked it. Set Microphone to Allow in the padlock menu.",
  "service-not-allowed": "Chrome blocked its speech service for this page.",
  "audio-capture": "The microphone disappeared mid-test.",
  "language-not-supported": "Try English (US) in the accent dropdown.",
};

function startMeter(stream) {
  try {
    const audio = new AudioContext();
    const source = audio.createMediaStreamSource(stream);
    const analyser = audio.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    let peak = 0;

    const tick = () => {
      analyser.getByteTimeDomainData(data);
      let loudest = 0;
      for (const v of data) loudest = Math.max(loudest, Math.abs(v - 128));
      const percent = Math.min(100, (loudest / 40) * 100);
      $("levelFill").style.width = percent + "%";
      peak = Math.max(peak, percent);
      if (peak > 8) {
        $("levelNote").textContent = "Good — your voice is reaching the browser.";
      }
      micRaf = requestAnimationFrame(tick);
    };
    tick();
  } catch (err) {
    $("levelNote").textContent = "Could not draw the level meter: " + err.message;
  }
}

$("micCheckBtn").onclick = () => {
  $("micPanel").hidden = false;
  runMicCheck();
};
$("micCheckRun").onclick = runMicCheck;
$("micPanelClose").onclick = () => { $("micPanel").hidden = true; stopMeter(); };
$("micPanel").onclick = (event) => {
  if (event.target === $("micPanel")) { $("micPanel").hidden = true; stopMeter(); }
};

/* ------------------------------------------------------- reminders going off */

function askNotificationPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

function beep() {
  try {
    const audio = new AudioContext();
    const tone = audio.createOscillator();
    const gain = audio.createGain();
    tone.connect(gain); gain.connect(audio.destination);
    tone.frequency.value = document.body.classList.contains("ultron") ? 220 : 880;
    gain.gain.setValueAtTime(0.0001, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.25, audio.currentTime + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + 0.6);
    tone.start(); tone.stop(audio.currentTime + 0.62);
  } catch (err) { /* no sound is survivable */ }
}

async function checkReminders() {
  try {
    const data = await get("/api/tick");
    (data.due || []).forEach((item) => {
      beep();
      showToast("⏰ " + item.text);
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(document.title, { body: item.text });
      }
      say(item.kind === "timer"
        ? "Your timer is up. " + item.text
        : "Reminder: " + item.text);
    });
  } catch (err) { /* server is down; try again next time */ }
}
setInterval(checkReminders, 4000);

/* ---------------------------------------------------------------- shortcuts */

const SUGGESTIONS = [
  "open chrome", "take a screenshot", "how's the battery",
  "clean up downloads", "set a 10 minute timer", "what's the weather",
  "set volume to 40", "focus mode", "find my resume",
  "what's on my list", "what's taking up space", "list my macros", "help",
];

SUGGESTIONS.forEach((text) => {
  const button = document.createElement("button");
  button.textContent = text;
  button.onclick = () => send(text);
  chips.appendChild(button);
});

/* --------------------------------------------------------------------- boot */

(async function boot() {
  setState("idle");

  if (!(window.SpeechRecognition || window.webkitSpeechRecognition)) {
    showMicProblem("This browser has no speech support — open Jarvis in Chrome "
      + "or Edge. Until then you can type at the bottom.");
  }

  try {
    const status = await get("/api/status");
    applyPersona(status.voice);
    if (status.ai) showToast("AI brain: " + status.brain);
  } catch (err) { /* the page still works without this */ }
})();

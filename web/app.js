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

    const meta = row.size || row.modified;
    if (meta) {
      const tag = document.createElement("span");
      tag.className = "meta";
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

  engine.onstart = () => { listening = true; setState("listening"); };

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
    if (!hit) { heard.textContent = ""; return; }

    const command = spoken.slice(lower.indexOf(hit) + hit.length).trim();
    if (command.length > 1) send(command);
    else { heard.textContent = ""; say("Yes?"); }
  };

  engine.onerror = (event) => {
    listening = false;
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      showMicProblem("The browser blocked microphone access. Click the padlock "
        + "in the address bar and set Microphone to Allow.");
      wakeMode = false;
      wakeToggle.checked = false;
    } else if (event.error === "no-speech" && !wakeMode) {
      showToast("I didn't hear anything.");
    }
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

function startListening() {
  if (listening || busy) return;
  stoppedByUs = false;
  recognition = buildRecognition();
  if (!recognition) {
    showMicProblem("This browser has no speech support. Open Jarvis in Chrome or Edge.");
    return;
  }
  try { recognition.start(); }
  catch (err) { /* already running, nothing to do */ }
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
  "what's on my list", "what's taking up space", "help",
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

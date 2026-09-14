"""
The Jarvis server.

It does two things:
  1. serves the page in web/ to the browser, where the listening and
     speaking happen
  2. takes the commands that page sends, hands them to brain.py, and
     sends the answer back

To run:  python jarvis.py
The browser opens by itself.

By default the server listens on 127.0.0.1, which means it is reachable from
this laptop and nowhere else -- nobody on the wifi can see it. See the note
on HOST below before changing that.
"""
import json
import secrets
import socket
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import brain
import persona
from skills import files, memory

# A Windows console is cp1252 by default, which cannot print emoji or Hindi.
# Without this, saying "make a note नमस्ते" blows up on the log line below
# and the request dies before it ever reaches the browser.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass                                       # no console attached; fine

# Keep this as 127.0.0.1 unless you really mean otherwise. Jarvis runs
# PowerShell, opens and closes programs, reads your files and clipboard, and
# can lock or shut the machine down. On 127.0.0.1 only this laptop can reach
# it. Any other address puts all of that on the network.
#
# If you do change it -- to use Jarvis from your phone, say -- the server
# refuses to start without a key, prints a link containing one, and rejects
# every request that does not carry it. That is a speed bump, not real
# security: there is no encryption, so only do this on a network you own.
HOST = "127.0.0.1"
PORT = 8765
WEB_DIR = Path(__file__).resolve().parent / "web"

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
ACCESS_KEY = ""            # filled in at startup when HOST is not loopback

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _lan_ip() -> str:
    """
    This machine's address on the local network.

    Nothing is actually sent -- opening a UDP socket towards the internet
    is just how you ask the OS which of your addresses it would use.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def _log(line: str) -> None:
    """Print without ever letting the console kill a request."""
    try:
        print(line)
    except Exception:                              # noqa: BLE001 - logging is not worth a crash
        pass


class JarvisHandler(BaseHTTPRequestHandler):
    server_version = "Jarvis"

    def _key_ok(self) -> bool:
        """On a non-loopback bind, every request has to carry the key."""
        if not ACCESS_KEY:
            return True                            # loopback only: no key needed
        sent = self.headers.get("X-Jarvis-Key", "")
        if not sent:
            query = urllib.parse.urlparse(self.path).query
            sent = urllib.parse.parse_qs(query).get("key", [""])[0]
        return secrets.compare_digest(sent, ACCESS_KEY)

    # --------------------------------------------------------------- sending

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, name: str) -> None:
        path = (WEB_DIR / name).resolve()
        # Safety: never serve anything outside web/.
        if WEB_DIR not in path.parents or not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return {}
        if length <= 0 or length > 100_000:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    # ------------------------------------------------------------------ GET

    def do_GET(self) -> None:                      # noqa: N802 - http.server's name
        if not self._key_ok():
            self.send_error(403, "Missing or wrong key")
            return
        route = self.path.split("?")[0]

        if route == "/":
            self._send_file("index.html")
        elif route == "/api/tick":
            # The page asks this every few seconds: did a reminder go off?
            self._send_json({"due": memory.check_due()})
        elif route == "/api/status":
            import ai
            self._send_json({"ai": ai.is_on(), "brain": ai.describe(),
                             "voice": persona.voice()})
        elif route.startswith("/api/"):
            self.send_error(404)
        else:
            self._send_file(route.lstrip("/"))

    # ----------------------------------------------------------------- POST

    def do_POST(self) -> None:                     # noqa: N802
        if not self._key_ok():
            self.send_error(403, "Missing or wrong key")
            return
        route = self.path.split("?")[0]
        data = self._read_body()

        if route == "/api/command":
            text = (data.get("text") or "").strip()
            if not text:
                self._send_json(brain.reply("I did not catch that."))
                return
            try:
                answer = brain.handle(text)
            except Exception as exc:               # noqa: BLE001 - keep serving
                answer = brain.reply(f"Something broke inside: {exc}")
            _log(f"  >> {text}")
            _log(f"  << {answer['speak'][:90]}")
            self._send_json(answer)

        elif route == "/api/persona":
            name = persona.use((data.get("name") or "").strip())
            _log(f"  ~~ personality: {name}")
            self._send_json({"persona": name, "voice": persona.voice()})

        elif route == "/api/open":
            self._send_json({"speak": files.open_file(data.get("path", ""))})

        else:
            self.send_error(404)

    def log_message(self, *args) -> None:          # quiet -- we print our own
        pass


def main() -> None:
    if not (WEB_DIR / "index.html").exists():
        print("web/index.html is missing. Was the whole folder copied?")
        sys.exit(1)

    global ACCESS_KEY
    if HOST not in LOOPBACK:
        ACCESS_KEY = secrets.token_urlsafe(12)

    # 0.0.0.0 means "every address", which is not one you can type into a
    # phone -- show the real one on the network instead.
    shown_host = _lan_ip() if HOST == "0.0.0.0" else HOST
    url = f"http://{shown_host}:{PORT}"
    if ACCESS_KEY:
        url += f"/?key={ACCESS_KEY}"
    try:
        server = ThreadingHTTPServer((HOST, PORT), JarvisHandler)
    except OSError:
        print(f"Port {PORT} is already in use.")
        print("Jarvis may already be running. Open it at:", url)
        sys.exit(1)

    import ai

    print()
    print("   J A R V I S   is ready")
    print("   " + "-" * 34)
    print(f"   Page   : {url}")
    print(f"   Brain  : {ai.describe()}")
    print("   Stop   : press Ctrl+C in this window")
    if ACCESS_KEY:
        print()
        print("   ! Listening on the network, not just this laptop.")
        print("   ! Anyone with the link above can run commands on this")
        print("   ! machine. Use it only on a network you trust, and")
        print("   ! close this window when you are done.")
    print()

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Shutting down. Bye.")
        server.shutdown()


if __name__ == "__main__":
    main()

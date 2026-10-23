#!/usr/bin/env python3
"""Local web UI for adguardvpn-cli.

Serves a single page on 127.0.0.1 and runs allow-listed adguardvpn-cli
commands on its behalf. Every API call must carry a per-launch random token,
so other websites open in the browser cannot drive the CLI.
"""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = shutil.which("adguardvpn-cli") or "/opt/adguardvpn_cli/adguardvpn-cli"
TOKEN = secrets.token_urlsafe(24)
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

ON_OFF = {"on", "off"}
EXCL_MODES = {"general", "selective"}

# config setter -> allowed values (None = free text, validated loosely)
CONFIG_SETTERS = {
    "set-mode": {"tun", "socks"},
    "set-dns": None,
    "set-socks-port": None,
    "set-socks-host": None,
    "set-socks-username": None,
    "set-socks-password": None,
    "set-change-system-dns": ON_OFF,
    "set-tun-routing-mode": {"auto", "script", "none"},
    "set-crash-reporting": ON_OFF,
    "set-telemetry": ON_OFF,
    "set-update-channel": {"release", "beta", "nightly"},
    "set-protocol": {"auto", "http2", "quic"},
    "set-post-quantum": ON_OFF,
    "set-show-hints": ON_OFF,
    "set-debug-logging": ON_OFF,
    "set-show-notifications": ON_OFF,
    "set-bound-if-override": None,
}

# Serialise CLI calls: the CLI keeps one config file and one VPN socket.
cli_lock = threading.Lock()


def run_cli(args, timeout=60):
    env = dict(os.environ)
    env["SUDO_ASKPASS"] = str(HERE / "askpass.sh")
    env.setdefault("DISPLAY", ":0")
    with cli_lock:
        try:
            p = subprocess.run(
                [CLI, *args],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                # No controlling terminal, so sudo falls back to SUDO_ASKPASS.
                start_new_session=True,
            )
            out = ANSI.sub("", p.stdout + p.stderr).strip()
            return {"ok": p.returncode == 0, "code": p.returncode, "output": out}
        except subprocess.TimeoutExpired as e:
            out = ANSI.sub("", (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
            return {"ok": False, "code": -1, "output": out + "\n[timed out]"}


# ---------- parsers ----------

def parse_config(text):
    cfg = {}
    for line in text.splitlines():
        m = re.match(r"^\s+([^:]+):\s?(.*)$", line)
        if m:
            cfg[m.group(1).strip()] = m.group(2).strip()
    return cfg


def parse_status(text):
    m = re.search(r"Connected to (.+?) in (\S+) mode(?:, running on (\S+))?", text)
    if m:
        return {"connected": True, "location": m.group(1).title(), "mode": m.group(2), "iface": m.group(3), "text": text}
    return {"connected": False, "text": text}


def parse_license(text):
    info = {"text": text}
    if m := re.search(r"Logged in as (\S+)", text):
        info["account"] = m.group(1)
    if m := re.search(r"using the (\S+) version", text):
        info["plan"] = m.group(1)
    if m := re.search(r"Up to (\d+) devices", text):
        info["devices"] = int(m.group(1))
    if m := re.search(r"renewed on (\S+)", text):
        info["renews"] = m.group(1)
    info["logged_in"] = "account" in info
    return info


def parse_exclusions(text):
    items = []
    for line in text.splitlines()[1:]:
        line = line.strip()
        if line and not line.lower().startswith(("exclusions for", "current exclusion", "you can")):
            items.append(line)
    return items


def parse_locations(text):
    locs = []
    for line in text.splitlines():
        m = re.match(r"^([A-Z]{2})\s+(.+?)\s{2,}(.+?)\s{2,}(\d+)\s*$", line)
        if m:
            locs.append({"iso": m.group(1), "country": m.group(2), "city": m.group(3), "ping": int(m.group(4))})
    return locs


def interfaces():
    try:
        return sorted(n for n in os.listdir("/sys/class/net") if n != "lo")
    except OSError:
        return []


def state():
    cfg = run_cli(["config", "show"])
    st = run_cli(["status"])
    lic = run_cli(["license"])
    mode = run_cli(["site-exclusions", "mode"])
    gen = run_cli(["site-exclusions", "show", "--for-mode", "general"])
    sel = run_cli(["site-exclusions", "show", "--for-mode", "selective"])
    m = re.search(r"exclusion mode is (\S+)", mode["output"])
    return {
        "config": parse_config(cfg["output"]),
        "status": parse_status(st["output"]),
        "license": parse_license(lic["output"]),
        "exclusions": {
            "mode": (m.group(1).lower() if m else "general"),
            "general": parse_exclusions(gen["output"]),
            "selective": parse_exclusions(sel["output"]),
        },
        "interfaces": interfaces(),
        "version": run_cli(["--version"])["output"],
    }


# ---------- command validation ----------

class BadRequest(Exception):
    pass


def build_command(req):
    action = req.get("action")
    v = req.get("value")
    if action == "connect":
        args = ["connect", "-y", "--no-progress"]
        if req.get("fastest"):
            args.append("-f")
        elif req.get("location"):
            args += ["-l", str(req["location"])]
        ip = req.get("ip")
        if ip == "4":
            args.append("-4")
        elif ip == "6":
            args.append("-6")
        return args, 180
    if action == "disconnect":
        return ["disconnect"], 60
    if action == "config":
        setter = req.get("setter")
        if setter == "clear-socks-auth":
            return ["config", "clear-socks-auth"], 30
        if setter == "create-route-script":
            return ["config", "create-route-script"], 60
        if setter not in CONFIG_SETTERS:
            raise BadRequest(f"unknown setting {setter!r}")
        allowed = CONFIG_SETTERS[setter]
        v = "" if v is None else str(v)
        if allowed is not None and v not in allowed:
            raise BadRequest(f"{setter}: value must be one of {sorted(allowed)}")
        if setter == "set-socks-port" and not (v.isdigit() and 1 <= int(v) <= 65535):
            raise BadRequest("port must be 1-65535")
        if setter in ("set-dns", "set-socks-host", "set-socks-username") and not v:
            raise BadRequest("value is required")
        args = ["config", setter, v]
        if setter == "set-socks-host":
            if req.get("username"):
                args += ["-u", str(req["username"])]
            if req.get("password"):
                args += ["-p", str(req["password"])]
        return args, 60
    if action in ("excl-add", "excl-remove"):
        items = [s for s in str(v or "").split() if s]
        if not items:
            raise BadRequest("enter at least one site or IP")
        mode = req.get("mode")
        if mode not in EXCL_MODES:
            raise BadRequest("bad exclusion list")
        # The CLI takes the list as one space-separated positional.
        return ["site-exclusions", action[5:], "--for-mode", mode, " ".join(items)], 30
    if action == "excl-clear":
        if req.get("mode") not in EXCL_MODES:
            raise BadRequest("bad exclusion list")
        return ["site-exclusions", "clear", "--for-mode", req["mode"]], 30
    if action == "excl-mode":
        if v not in EXCL_MODES:
            raise BadRequest("bad exclusion mode")
        return ["site-exclusions", "mode", v], 30
    if action == "check-update":
        return ["check-update"], 60
    if action == "update":
        return ["update", "-y", "-v"], 600
    if action == "export-logs":
        out = Path(req.get("path") or Path.home() / "Downloads").expanduser()
        return ["export-logs", "-f", "-o", str(out)], 120
    if action == "logout":
        return ["logout"], 30
    if action == "status":
        return ["status"], 30
    raise BadRequest(f"unknown action {action!r}")


def open_login_terminal():
    """`login` is interactive, so run it in a real terminal window."""
    for term in (["gnome-terminal", "--"], ["ptyxis", "--"], ["kgx", "-e"], ["x-terminal-emulator", "-e"]):
        if shutil.which(term[0]):
            cmd = f"{CLI} login; echo; read -p 'Press Enter to close…' _"
            subprocess.Popen([*term, "bash", "-c", cmd], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"ok": True, "output": "Opened a terminal window for login. Refresh here when done."}
    return {"ok": False, "output": f"No terminal emulator found. Run `{CLI} login` manually."}


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _authed(self):
        return secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def _local_host(self):
        # Rejects DNS-rebinding: a hostile domain pointed at 127.0.0.1 sends its own Host.
        host = self.headers.get("Host", "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._local_host():
            return self._send(403, {"error": "forbidden"})
        if self.path in ("/", "/index.html"):
            html = (HERE / "index.html").read_text().replace("__TOKEN__", TOKEN)
            return self._send(200, html.encode(), "text/html; charset=utf-8")
        if not self._authed():
            return self._send(403, {"error": "forbidden"})
        if self.path == "/api/state":
            return self._send(200, state())
        if self.path == "/api/locations":
            r = run_cli(["list-locations"])
            return self._send(200, {"locations": parse_locations(r["output"]), "raw": r["output"]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._authed():
            return self._send(403, {"error": "forbidden"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})
        if self.path != "/api/run":
            return self._send(404, {"error": "not found"})
        if req.get("action") == "login":
            return self._send(200, open_login_terminal())
        try:
            args, timeout = build_command(req)
        except BadRequest as e:
            return self._send(400, {"ok": False, "output": str(e)})
        res = run_cli(args, timeout)
        shown = list(args)
        if "set-socks-password" in shown or "-p" in shown:
            # keep passwords out of the on-screen command log
            for i, a in enumerate(shown):
                if (i > 0 and shown[i - 1] in ("set-socks-password", "-p")):
                    shown[i] = "••••••"
        res["command"] = "adguardvpn-cli " + " ".join(shown)
        self._send(200, res)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8737)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    url = f"http://127.0.0.1:{a.port}/"
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError:
        # Most likely already running (e.g. launched twice from the app menu).
        print(f"Port {a.port} is busy; opening {url}", flush=True)
        if not a.no_browser:
            webbrowser.open(url)
        return 0
    print(f"AdGuard VPN UI running at {url}  (Ctrl+C to stop)", flush=True)
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())

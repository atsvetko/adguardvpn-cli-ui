# AdGuard VPN CLI UI

A small local web interface for [AdGuard VPN CLI](https://github.com/AdguardTeam/AdGuardVPNCLI) on Linux.
It exposes every setting and command the CLI offers, so you don't have to remember the flags.

> Unofficial community project. Not affiliated with or endorsed by AdGuard.
> It only runs the `adguardvpn-cli` you already have installed.

## Features

- **Connection** – status, connect to the fastest or last-used location, browse all locations with
  ping estimates and a filter, IPv4-only / IPv6-only, disconnect.
- **Settings** – TUN/SOCKS mode, tunnel routing mode (auto/script/none), create route script,
  outbound interface override, SOCKS host/port/username/password, clear SOCKS auth, DNS upstream,
  change system DNS, protocol (auto/HTTP2/QUIC), post-quantum crypto, notifications, hints,
  debug logging, update channel, crash reporting, telemetry.
- **Exclusions** – switch general/selective mode, add, remove and clear entries in either list.
- **Account** – license info, log in, log out, check for and install updates, export logs.
- An output panel shows the exact CLI command and its output for every action.

## Install (Debian / Ubuntu)

Download the `.deb` from the [latest release](https://github.com/atsvetko/adguardvpn-cli-ui/releases/latest)
and install it:

```bash
sudo apt install ./adguardvpn-cli-ui_*_all.deb
```

Then open **AdGuard VPN** from your app menu, or run `adguardvpn-cli-ui`.
To remove it: `sudo apt remove adguardvpn-cli-ui`.

The package works on any CPU architecture. Its only dependency is `python3`, which every
Ubuntu/Debian desktop already has, so nothing else gets installed.

## Requirements

- Linux with [AdGuard VPN CLI](https://github.com/AdguardTeam/AdGuardVPNCLI) installed and on `PATH`
  (or at `/opt/adguardvpn_cli/adguardvpn-cli`)
- Python 3.8+ (standard library only, nothing to `pip install`)
- `zenity`, `kdialog` or `ssh-askpass` for the password prompt when connecting in TUN mode

## Run from source

```bash
git clone https://github.com/atsvetko/adguardvpn-cli-ui.git
cd adguardvpn-cli-ui
python3 server.py
```

Your browser opens at `http://127.0.0.1:8737/`. Options: `--port N`, `--no-browser`.

To add an **AdGuard VPN** entry to your desktop app menu:

```bash
./install.sh
```

Log in once with `adguardvpn-cli login` (or the **Log in…** button, which opens a terminal),
since login is interactive.

## Building the .deb

```bash
./packaging/build-deb.sh 1.0.0
```

Produces `dist/adguardvpn-cli-ui_1.0.0_all.deb`. Only `dpkg-deb` is needed.

## How it works

`server.py` is a tiny Python HTTP server bound to `127.0.0.1`. The page sends actions to it and it
runs the matching `adguardvpn-cli` command. Only allow-listed commands and values are accepted,
and arguments are passed without a shell.

Connecting in TUN mode makes the CLI call `sudo`. Because the server has no terminal, sudo uses
`askpass.sh` to show a graphical password prompt.

## Security notes

- Listens on `127.0.0.1` only.
- Each launch generates a random token that every API call must carry, so other websites open in
  your browser can't drive the CLI. Requests with a non-local `Host` header are refused
  (DNS-rebinding protection).
- A new SOCKS password is passed to the CLI as a command-line argument, so it is briefly visible
  in the process list while it is being set. It is never shown in the UI.

## License

MIT

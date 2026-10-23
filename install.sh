#!/bin/sh
# Adds an "AdGuard VPN" entry to the desktop app menu that starts the UI.
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
chmod +x "$DIR/server.py" "$DIR/askpass.sh"
cat > "$APPS/adguardvpn-ui.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AdGuard VPN
Comment=Manage AdGuard VPN CLI settings
Exec=python3 "$DIR/server.py"
Icon=network-vpn
Terminal=false
Categories=Network;
EOF
echo "Installed: $APPS/adguardvpn-ui.desktop"
echo "Open \"AdGuard VPN\" from your app menu (or run: python3 \"$DIR/server.py\")."

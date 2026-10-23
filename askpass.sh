#!/bin/sh
# Graphical password prompt used by sudo when AdGuard VPN needs root (TUN mode).
TITLE="AdGuard VPN needs administrator rights"
if command -v zenity >/dev/null 2>&1; then
  exec zenity --password --title="$TITLE" 2>/dev/null
elif command -v kdialog >/dev/null 2>&1; then
  exec kdialog --title "$TITLE" --password "Password:" 2>/dev/null
elif command -v ssh-askpass >/dev/null 2>&1; then
  exec ssh-askpass "$TITLE"
fi
echo "No graphical password prompt found (install zenity, kdialog or ssh-askpass)" >&2
exit 1

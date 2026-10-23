#!/bin/sh
# Builds dist/adguardvpn-cli-ui_<version>_all.deb. Needs only dpkg-deb.
set -e
VERSION="${1:-1.0.0}"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PKG=adguardvpn-cli-ui
STAGE=$(mktemp -d)
chmod 755 "$STAGE"
trap 'rm -rf "$STAGE"' EXIT

install -Dm755 "$ROOT/server.py"   "$STAGE/usr/lib/$PKG/server.py"
install -Dm644 "$ROOT/index.html"  "$STAGE/usr/lib/$PKG/index.html"
install -Dm755 "$ROOT/askpass.sh"  "$STAGE/usr/lib/$PKG/askpass.sh"
install -Dm755 "$ROOT/packaging/$PKG"          "$STAGE/usr/bin/$PKG"
install -Dm644 "$ROOT/packaging/$PKG.desktop"  "$STAGE/usr/share/applications/$PKG.desktop"
install -Dm644 "$ROOT/packaging/$PKG.svg"      "$STAGE/usr/share/icons/hicolor/scalable/apps/$PKG.svg"
install -Dm644 "$ROOT/LICENSE"                 "$STAGE/usr/share/doc/$PKG/copyright"

mkdir -p "$STAGE/DEBIAN"
SIZE=$(du -sk "$STAGE/usr" | cut -f1)
cat > "$STAGE/DEBIAN/control" <<CTRL
Package: $PKG
Version: $VERSION
Architecture: all
Maintainer: Alexander Tsvetkov <55227933+atsvetko@users.noreply.github.com>
Installed-Size: $SIZE
Depends: python3 (>= 3.8)
Recommends: zenity | kdialog | ssh-askpass
Section: net
Priority: optional
Homepage: https://github.com/atsvetko/adguardvpn-cli-ui
Description: Unofficial local web UI for AdGuard VPN CLI
 Small local web interface for adguardvpn-cli on Linux. Connect and pick
 locations, change every config setting, manage site exclusions, and see
 license, updates and logs without memorising command-line flags.
 Requires AdGuard VPN CLI to be installed separately. Not affiliated with
 AdGuard.
CTRL

mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/${PKG}_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"
echo "$OUT"

#!/bin/sh
# Installiert das Plugin direkt auf einer OPNsense (ohne Paketbau).
# Aufruf auf der Firewall als root:  sh install.sh
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
SRC="$DIR/cfddns/src"

[ "$(id -u)" = "0" ] || { echo "Bitte als root ausführen"; exit 1; }
[ -d /usr/local/opnsense ] || { echo "Das hier ist keine OPNsense"; exit 1; }

echo "Kopiere Dateien ..."
cp -R "$SRC/etc/" /usr/local/etc/
cp -R "$SRC/opnsense/" /usr/local/opnsense/
chmod 755 /usr/local/opnsense/scripts/cfddns/cfddns.py
mkdir -p /var/db/cfddns && chmod 750 /var/db/cfddns

echo "Lade configd, Menü und Syslog neu ..."
service configd restart
rm -f /tmp/opnsense_menu_cache.xml /tmp/opnsense_acl_cache.json
configctl template reload OPNsense/Syslog >/dev/null
configctl syslog restart >/dev/null || true
configctl cron restart >/dev/null || true

echo "Fertig. GUI: Dienste > Cloudflare DDNS (Seite ggf. neu laden)."

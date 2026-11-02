#!/bin/sh
# Installiert Multihome DynDNS direkt auf einer OPNsense (ohne Paketbau).
# Aufruf auf der Firewall als root:  sh install.sh
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
SRC="$DIR/multihome-ddns/src"

[ "$(id -u)" = "0" ] || { echo "Bitte als root ausführen"; exit 1; }
[ -d /usr/local/opnsense ] || { echo "Das hier ist keine OPNsense"; exit 1; }

# Vorgängerversion (Cloudflare DDNS / cfddns) entfernen, falls vorhanden
if [ -f /usr/local/etc/inc/plugins.inc.d/cfddns.inc ]; then
    echo "Entferne Vorgängerversion (cfddns) ..."
    rm -f  /usr/local/etc/inc/plugins.inc.d/cfddns.inc
    rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/CloudflareDDNS \
           /usr/local/opnsense/mvc/app/controllers/OPNsense/CloudflareDDNS \
           /usr/local/opnsense/mvc/app/views/OPNsense/CloudflareDDNS \
           /usr/local/opnsense/scripts/cfddns /var/db/cfddns
    rm -f  /usr/local/opnsense/service/conf/actions.d/actions_cfddns.conf \
           /usr/local/opnsense/service/templates/OPNsense/Syslog/local/cfddns.conf
fi

# Vorgängerversion 2.0 (Multi-WAN DynDNS / multiwanddns) ablösen
if [ -f /usr/local/etc/inc/plugins.inc.d/multiwanddns.inc ]; then
    echo "Löse Multi-WAN DynDNS ab (Einstellungen und Status werden übernommen) ..."
    if [ -d /var/db/multiwanddns ] && [ ! -d /var/db/multihomeddns ]; then
        mv /var/db/multiwanddns /var/db/multihomeddns
    fi
    rm -f  /usr/local/etc/inc/plugins.inc.d/multiwanddns.inc
    rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/MultiWanDDNS \
           /usr/local/opnsense/mvc/app/controllers/OPNsense/MultiWanDDNS \
           /usr/local/opnsense/mvc/app/views/OPNsense/MultiWanDDNS \
           /usr/local/opnsense/scripts/multiwanddns /var/db/multiwanddns
    rm -f  /usr/local/opnsense/service/conf/actions.d/actions_multiwanddns.conf \
           /usr/local/opnsense/service/templates/OPNsense/Syslog/local/multiwanddns.conf
fi

echo "Kopiere Dateien ..."
cp -R "$SRC/etc/" /usr/local/etc/
cp -R "$SRC/opnsense/" /usr/local/opnsense/
chmod 755 /usr/local/opnsense/scripts/multihomeddns/multihomeddns.py /usr/local/opnsense/scripts/multihomeddns/gateways.php
chmod 755 /usr/local/opnsense/scripts/multihomeddns/migrate.php
mkdir -p /var/db/multihomeddns && chmod 750 /var/db/multihomeddns

# Einstellungen einer Vorgängerversion übernehmen (nur wenn vorhanden)
/usr/local/opnsense/scripts/multihomeddns/migrate.php || echo "  (Übernahme der Einstellungen fehlgeschlagen - bitte im Log prüfen)"

# optional: boto3 für den Anbieter Amazon Route 53
if ! /usr/local/bin/python3 -c "import boto3" 2>/dev/null; then
    PYV=$(/usr/local/bin/python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
    echo "Installiere optional py${PYV}-boto3 (nur für Amazon Route 53) ..."
    pkg install -y "py${PYV}-boto3" >/dev/null 2>&1 || echo "  (übersprungen - Route 53 ist dann nicht verfügbar)"
fi

echo "Lade configd, Menü, Syslog und Cron neu ..."
service configd restart
rm -f /var/lib/php/tmp/opnsense_menu_cache.xml /var/lib/php/tmp/opnsense_acl_cache.json \
      /tmp/opnsense_menu_cache.xml /tmp/opnsense_acl_cache.json
configctl template reload OPNsense/Syslog >/dev/null
configctl syslog restart >/dev/null || true
configctl cron restart >/dev/null || true
configctl filter reload >/dev/null || true

echo "Fertig. GUI: Dienste > Multihome DynDNS (Seite ggf. neu laden)."

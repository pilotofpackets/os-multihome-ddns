#!/bin/sh
# Entfernt Multihome DynDNS (Einstellungen in der config.xml bleiben erhalten).
set -e
[ "$(id -u)" = "0" ] || { echo "Bitte als root ausführen"; exit 1; }
rm -f  /usr/local/etc/inc/plugins.inc.d/multihomeddns.inc
rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/MultihomeDDNS
rm -rf /usr/local/opnsense/mvc/app/controllers/OPNsense/MultihomeDDNS
rm -rf /usr/local/opnsense/mvc/app/views/OPNsense/MultihomeDDNS
rm -rf /usr/local/opnsense/scripts/multihomeddns
rm -f  /usr/local/opnsense/service/conf/actions.d/actions_multihomeddns.conf
rm -f  /usr/local/opnsense/service/templates/OPNsense/Syslog/local/multihomeddns.conf
rm -rf /var/db/multihomeddns
service configd restart
rm -f /var/lib/php/tmp/opnsense_menu_cache.xml /var/lib/php/tmp/opnsense_acl_cache.json \
      /tmp/opnsense_menu_cache.xml /tmp/opnsense_acl_cache.json
configctl template reload OPNsense/Syslog >/dev/null
configctl syslog restart >/dev/null || true
configctl cron restart >/dev/null || true
configctl filter reload >/dev/null || true
echo "Entfernt."

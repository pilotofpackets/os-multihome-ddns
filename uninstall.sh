#!/bin/sh
# Entfernt Multi-WAN DynDNS (Einstellungen in der config.xml bleiben erhalten).
set -e
[ "$(id -u)" = "0" ] || { echo "Bitte als root ausführen"; exit 1; }
rm -f  /usr/local/etc/inc/plugins.inc.d/multiwanddns.inc
rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/MultiWanDDNS
rm -rf /usr/local/opnsense/mvc/app/controllers/OPNsense/MultiWanDDNS
rm -rf /usr/local/opnsense/mvc/app/views/OPNsense/MultiWanDDNS
rm -rf /usr/local/opnsense/scripts/multiwanddns
rm -f  /usr/local/opnsense/service/conf/actions.d/actions_multiwanddns.conf
rm -f  /usr/local/opnsense/service/templates/OPNsense/Syslog/local/multiwanddns.conf
rm -rf /var/db/multiwanddns
service configd restart
rm -f /var/lib/php/tmp/opnsense_menu_cache.xml /var/lib/php/tmp/opnsense_acl_cache.json \
      /tmp/opnsense_menu_cache.xml /tmp/opnsense_acl_cache.json
configctl template reload OPNsense/Syslog >/dev/null
configctl syslog restart >/dev/null || true
configctl cron restart >/dev/null || true
configctl filter reload >/dev/null || true
echo "Entfernt."

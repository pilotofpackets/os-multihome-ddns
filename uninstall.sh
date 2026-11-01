#!/bin/sh
# Entfernt das Plugin wieder (Einstellungen in config.xml bleiben erhalten).
set -e
[ "$(id -u)" = "0" ] || { echo "Bitte als root ausführen"; exit 1; }
rm -f  /usr/local/etc/inc/plugins.inc.d/cfddns.inc
rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/CloudflareDDNS
rm -rf /usr/local/opnsense/mvc/app/controllers/OPNsense/CloudflareDDNS
rm -rf /usr/local/opnsense/mvc/app/views/OPNsense/CloudflareDDNS
rm -rf /usr/local/opnsense/scripts/cfddns
rm -f  /usr/local/opnsense/service/conf/actions.d/actions_cfddns.conf
rm -f  /usr/local/opnsense/service/templates/OPNsense/Syslog/local/cfddns.conf
rm -rf /var/db/cfddns
service configd restart
rm -f /tmp/opnsense_menu_cache.xml /tmp/opnsense_acl_cache.json
configctl template reload OPNsense/Syslog >/dev/null
configctl syslog restart >/dev/null || true
configctl cron restart >/dev/null || true
configctl filter reload >/dev/null || true
echo "Entfernt."

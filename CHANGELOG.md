# Changelog

## 2.0.1 – 2026-11-02

- Installer: clear the menu and ACL cache in /var/lib/php/tmp (current OPNsense), so the menu entry shows up right away

## 2.0.0 – 2026-11-02

- Renamed from "Cloudflare DDNS" (cfddns) to **Multi-WAN DynDNS** / os-multihome-ddns
- All check services and native providers of os-ddclient
- Own route-to rules (tcp 80/443, udp 53), independent of "Disable force gateway"
- Address classes: private (RFC 1918/4193), reserved (RFC 6890) and CGNAT (RFC 6598) are highlighted and never written
- Failover DNS based on dpinger gateway status: strategies order / gateway priority / latency, failback immediate / delayed / manual, history
- Full logging with five levels, own log file
- Force update per entry, for selected entries and for all
- Test dialog with address classes and policy rule status
- Immediate reaction to address changes (newwanip) and gateway alarms (monitor)
- Installer removes the 1.0 version automatically

## 1.0.0

- Cloudflare DynDNS with per-interface public IP detection and policy routing

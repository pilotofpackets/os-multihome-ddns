# Changelog

## 2.3.0 – 2026-11-02

- **Fix:** the tcp route-to rule for the web check was silently dropped by OPNsense (port lists like
  `80,443` are not accepted in plugin rules) – now one rule per port
- **Fix:** outbound NAT of the default WAN translated the check traffic before the filter rules were
  evaluated (interfaces without upstream gateway are part of automatic outbound NAT), so no route-to
  rule could match – the plugin now adds `no nat` exemptions for its check traffic (before manual and
  automatic outbound NAT). This is also why the stock ddclient reports the default WAN address.
- Routing guard: an address that sits directly on an interface belongs to that interface, only the
  other entry is blocked
- Test dialog shows the NAT exemption; rules are now tested with the real OPNsense rule classes in CI

## 2.2.0 – 2026-11-02

- Redesigned overview pages: status bar with counters, routing state and legend; fewer, two-line columns;
  nothing truncated anymore (IPs, messages, members); clean action bar
- Settings page and dialogs aligned with the stock OPNsense look
- Gateway per entry (automatic or explicit); automatic lookup also finds gateways that are not marked
  as interface gateway
- Test dialog shows the gateway used, all gateways on the interface and the matching route-to rule (tcp/udp)
- Backend messages with proper German umlauts
- Screenshots and preview tool (`tools/preview`)

## 2.1.0 – 2026-11-02

- Renamed to **Multihome DynDNS** (package os-multihome-ddns, menu *Services › Multihome DynDNS*,
  URLs `/ui/multihomeddns`, configd `multihomeddns`, log `/var/log/multihomeddns`)
- Installer takes over a 2.0 installation: settings in config.xml, state file and
  Cloudflare records (old record tag `multiwan-ddns:` is recognised and rewritten)

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

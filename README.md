# Multi-WAN DynDNS für OPNsense

DynDNS-Plugin für mehrere Internetanschlüsse (z.B. mehrere DSL-Leitungen).

- **Feste IP pro Anschluss:** Jeder Eintrag ist an ein Interface gebunden und meldet **dessen** öffentliche IP – nicht die der Default-Route.
- **Failover-Namen:** Ein Name zeigt immer auf einen verfügbaren Anschluss.

Menü: *Dienste › Multi-WAN DynDNS* mit **Einträge**, **Failover-DNS**, **Einstellungen** und **Log File**.

## Warum das ddclient-Plugin hier scheitert

Die Firewall schickt ihre eigenen Abfragen über die Default-Route. Dass eine Abfrage für WAN2 trotzdem über WAN2 geht, hängt an den automatischen „force gw“-Regeln von OPNsense. Diese Regeln fehlen in drei Fällen:

- *Firewall › Einstellungen › Erweitert › „Disable force gateway“* ist gesetzt.
- Am Interface ist kein Gateway eingetragen.
- Eine eigene `quick`-Regel greift vorher.

Dann liefert ipify & Co. für alle Einträge dieselbe IP.

**Multi-WAN DynDNS erzeugt eigene Regeln**, unabhängig von „Disable force gateway“ – die Option kann also gesetzt bleiben:

```
pass out quick route-to (<if> <gw>) proto tcp from (<if>) to !<if-netz> port {80,443}
pass out quick route-to (<if> <gw>) proto udp from (<if>) to !<if-netz> port 53
```

- Die Regeln gelten nur für Verkehr mit der Quelladresse des jeweiligen Interfaces.
- Mehrere Interfaces können deshalb gleichzeitig **denselben** Prüfdienst nutzen, z.B. alle ipify.
- Kontrolle: `pfctl -sr | grep route-to` oder der Test-Knopf (Kolben) am Eintrag.

## Funktionen

### IP-Ermittlung
- **Automatisch:** Ist die Interface-Adresse öffentlich (PPPoE), wird sie direkt genommen. Sonst wird ein Prüfdienst über das Interface abgefragt.
- **Prüfdienste wie os-ddclient:**
  - akamai, cloudflare (Web und DNS), dynu, freedns, he, icanhazip, ipify, loopia, myonlineportal, noip, nsupdate.info, zoneedit
  - eigene URL
- **IPv6** inklusive Austausch des Host-Teils („Dynamic ipv6 host“).
- **Prüfintervall pro Eintrag ab 1 Minute.** Sofortige Prüfung bei Adresswechsel (PPPoE-Reconnect).

### Adressschutz
- **Private Adressen** (RFC 1918, RFC 4193) und **reservierte Adressen** (RFC 6890) werden rot markiert und **nie geschrieben**.
- **CGNAT** (RFC 6598, 100.64.0.0/10) wird orange markiert.
  - Eine CGNAT-Adresse wird **nie geschrieben**.
  - Hängt das Interface selbst hinter CGNAT, wird standardmäßig ebenfalls **nicht** aktualisiert. Das ist abschaltbar.
- **Schutz vor falschem Routing:** Liefert ein Interface eine IP, die schon einem anderen gehört, wird nicht geschrieben.

### Anbieter
Die nativen Anbieter von os-ddclient, übernommen (BSD-Lizenz):

- **dyndns2-Familie:** DynDNS, deSEC, DNS-O-Matic, Dynu, HE.net, INWX, Loopia, No-IP, nsupdate.info, OVH, spDYN, STRATO, eigener Dienst (GET/POST/PUT)
- **API-Anbieter:** all-inkl (KAS), Amazon Route 53, Azure, DigitalOcean, DNSPod, Domeneshop, Duck DNS, Gandi, Hetzner, Hostinger, netcup, Porkbun, PowerDNS
- **Cloudflare** in eigener Umsetzung: Mehrere Anschlüsse dürfen denselben Namen pflegen (Round-Robin). Jeder Eintrag erkennt seinen Record am Kommentar `multiwan-ddns:<uuid>`.

### Failover-DNS
- Ein Name (z.B. `www.example.com`) zeigt auf die IP eines verfügbaren Mitglieds.
- Die festen Namen pro Anschluss (`dsl1…`, `dsl2…`) bleiben unverändert, damit Forward- und Reverse-DNS stimmen.
- **Ausfall** wird über den Gateway-Status (dpinger) erkannt:
  - immer bei *offline*
  - optional bei Paketverlust oder Latenz-Alarm
  - optional über eigene Schwellwerte
  - außerdem, wenn die IP-Ermittlung des Mitglieds fehlschlägt
- **Auswahl:** Reihenfolge, Gateway-Priorität oder geringste Latenz.
- **Zurückschalten:** sofort, verzögert (nach stabiler Zeit) oder nur manuell (Knopf „Neu bewerten“).
- **Reaktion:** sofort bei Gateway-Alarmen und zusätzlich jede Minute.
- **Detailansicht:** Zustand aller Mitglieder und Verlauf der Umschaltungen.

### Bedienung und Log
- **Force-Update:** pro Eintrag, für ausgewählte oder für alle Einträge.
- **Log-Stufen:**
  - Fehler
  - Warnungen
  - Änderungen
  - **jede Prüfung** (Standard)
  - Debug: Interface-Adressen, Abfragen und Antworten, Gateway-Status, Policy-Regeln, Entscheidungen, Anbieter-API-Aufrufe

## Installation (direkt auf der Firewall)

```sh
# Ordner auf die OPNsense kopieren (z.B. per scp), dann als root:
sh install.sh
```

Eine vorhandene Vorgängerversion (Cloudflare DDNS / `cfddns`) wird dabei entfernt.

Danach unter *Dienste › Multi-WAN DynDNS*:

1. **Einträge:** pro Anschluss und IP-Version einen Eintrag anlegen (Interface, Anbieter, Hostnamen).
2. **Failover-DNS** (optional): Namen anlegen und Mitglieder wählen.
3. **Einstellungen:** „Aktiviert“ setzen, dann **Speichern und anwenden**. Das lädt die Firewall-Regeln und den Zeitplan neu und prüft sofort.

Entfernen: `sh uninstall.sh` (Einstellungen in der config.xml bleiben erhalten).

### Cloudflare API-Token

*My Profile › API Tokens › Create Token › „Edit zone DNS“* mit den Rechten **Zone › DNS › Edit** und **Zone › Zone › Read**, beschränkt auf die Zone.

## Als Paket bauen (optional)

`multiwan-ddns/` hat die Struktur von [opnsense/plugins](https://github.com/opnsense/plugins). Nach `dns/multiwan-ddns` kopieren und `make package` ausführen.

## Hinweise

- **Abhängigkeiten:** nur Bordmittel (`curl`, `python3`, `requests`, `dnspython`). Für Amazon Route 53 wird `boto3` benötigt; `install.sh` versucht es zu installieren.
- **HA/CARP:** Das Plugin nur auf dem Master aktivieren.
- **Dateien:**
  - Status: `/var/db/multiwanddns/state.json`
  - Log: `/var/log/multiwanddns/`

## Lizenz

BSD 2-Clause. Die Anbieter-Module unter `scripts/multiwanddns/lib/account/` stammen aus os-ddclient (Copyright Ad Schellevis / Deciso B.V. und Beitragende), ebenso die Liste der Prüfdienste.

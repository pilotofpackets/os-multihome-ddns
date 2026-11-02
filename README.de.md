# os-multihome-ddns – Multi-WAN DynDNS für OPNsense

**DynDNS für Firewalls mit mehreren Internetanschlüssen.**

Jeder DynDNS-Eintrag ist an ein Interface gebunden und meldet immer **dessen** öffentliche
IP – nicht die der Default-Route. Zusätzlich zeigen **Failover-Namen** immer auf einen
Anschluss, der gerade verfügbar ist.

> 🇬🇧 English: [README.md](README.md)

## Warum?

Mit mehreren WAN-Anschlüssen meldet das ddclient-Plugin oft für **alle Einträge dieselbe IP**.
Die Abfrage bei ipify & Co. schickt die Firewall selbst, und dieser Verkehr folgt der
Default-Route. Über das „richtige“ WAN geht er nur dank der automatischen *force gateway*-Regeln.
Diese fehlen in drei Fällen:

- *Firewall › Einstellungen › Erweitert › „Disable force gateway“* ist gesetzt.
- Am Interface ist kein Gateway eingetragen (z.B. statisch hinter einem Router).
- Eine eigene `quick`-Regel greift vorher.

**os-multihome-ddns erzeugt eigene Policy-Routing-Regeln pro Interface** – unabhängig von
„Disable force gateway“, die Option kann gesetzt bleiben. Die Regeln unterscheiden nach der
**Quelladresse**. Alle Interfaces können deshalb gleichzeitig denselben Prüfdienst nutzen.

## Funktionen

- **IP pro Interface:**
  - Eine öffentliche Interface-Adresse (PPPoE) wird direkt verwendet.
  - Sonst wird der Prüfdienst über genau dieses Interface abgefragt.
  - IPv4 und IPv6.
- **Prüfdienste wie os-ddclient:**
  - akamai, cloudflare (Web und DNS), dynu, freedns, he, icanhazip, ipify, loopia, myonlineportal, noip, nsupdate.info, zoneedit
  - eigene URL
- **Anbieter wie os-ddclient (native):**
  - all-inkl, Route 53, Azure, Cloudflare, deSEC, DigitalOcean, DNS-O-Matic, DNSPod, Domeneshop, Duck DNS, DynDNS, Dynu, Gandi, HE.net, Hetzner, Hostinger, INWX, Loopia, netcup, No-IP, nsupdate.info, OVH, Porkbun, PowerDNS, spDYN, STRATO
  - eigener Dienst
- **Cloudflare-Round-Robin:** Mehrere Anschlüsse können denselben Namen pflegen.
- **Adressschutz:**
  - Private (RFC 1918/4193), reservierte (RFC 6890) und CGNAT-Adressen (RFC 6598) werden farbig markiert und **nie geschrieben**.
  - Anschlüsse hinter CGNAT werden markiert und nicht aktualisiert (abschaltbar).
- **Routing-Schutz:** Meldet ein Interface die IP eines anderen, wird nichts geschrieben.
- **Failover-DNS:** Ein Name (z.B. `www`) zeigt auf den besten verfügbaren Anschluss.
  - Ausfallerkennung über den Gateway-Status (dpinger): offline, Paketverlust, Latenz oder eigene Schwellwerte.
  - Auswahl nach Reihenfolge, Gateway-Priorität oder Latenz.
  - Zurückschalten sofort, verzögert oder nur manuell.
- **Schnell:**
  - Prüfintervall pro Eintrag ab 1 Minute.
  - Sofortige Prüfung bei Adresswechsel.
  - Sofortiger Failover bei Gateway-Alarm.
- **Force-Update:** pro Eintrag, für ausgewählte oder für alle.
- **Vollständiges Logging:** fünf Stufen bis Debug, eigenes Log.
- **Test-Knopf:** zeigt erkannte Adresse, Adressklasse, Methode und Policy-Regel, ohne zu schreiben.

## Installation

Per SSH als `root` auf der Firewall anmelden (im Konsolenmenü **8** für Shell wählen):

```sh
fetch -o /tmp/mhddns.tar.gz https://github.com/pilotofpackets/os-multihome-ddns/archive/refs/heads/main.tar.gz
tar -xzf /tmp/mhddns.tar.gz -C /tmp
sh /tmp/os-multihome-ddns-main/install.sh
```

SSH lässt sich unter *System › Einstellungen › Verwaltung › Secure Shell* einschalten.
Danach die Weboberfläche neu laden. Das Plugin findest du unter **Dienste › Multi-WAN DynDNS**.

- **Aktualisieren:** dieselben drei Befehle erneut ausführen; die Einstellungen bleiben erhalten.
- **Entfernen:** `sh /tmp/os-multihome-ddns-main/uninstall.sh`

## Einrichtung

1. **Einträge:** pro Anschluss und IP-Version einen Eintrag anlegen.
   - Interface wählen.
   - Ermittlung „Automatisch“.
   - Prüfdienst nach Wahl.
   - Anbieter, Zugangsdaten, Zone und Hostnamen (z.B. `dsl1`, `dsl2`).
2. **Einstellungen:** „Aktiviert“ anhaken, Log-Stufe wählen, *Speichern und anwenden*.
3. Pro Eintrag mit dem 🧪 **Test**-Knopf Adresse und Routing-Regel prüfen.
4. **Failover-DNS** (optional): Namen (z.B. `www`) anlegen, Mitglieder wählen, Strategie festlegen, *Anwenden*.

| Name | zeigt auf | Zweck |
|---|---|---|
| `dsl1.example.com` | immer DSL 1 | fest, passend zu Reverse-DNS |
| `dsl2.example.com` | immer DSL 2 | fest, passend zu Reverse-DNS |
| `www.example.com` | bester verfügbarer Anschluss | Dienstname, folgt dem Failover |

**Cloudflare-Token:** Unter *My Profile › API Tokens › „Edit zone DNS“* mit **Zone › DNS › Edit**
und **Zone › Zone › Read** anlegen, beschränkt auf die Zone. Den Benutzernamen leer lassen.

## Fehlersuche

| Anzeige | Ursache / Lösung |
|---|---|
| *blockiert*: „auch Interface … zugeordnet“ | Die Abfrage lief über das falsche Gateway. *Anwenden* klicken und im Test-Dialog prüfen, ob die route-to-Regel aktiv ist. Ist am Interface ein Gateway hinterlegt? |
| Test: „keine Regel aktiv“ | Kein Gateway am Interface (*System › Gateways*) oder die Einstellungen sind noch nicht angewendet. |
| Oranges **CGNAT** | Der Anschluss liegt hinter Carrier-Grade NAT und ist von außen über IPv4 nicht erreichbar. |
| Rotes **privat** | Es wurde eine private Adresse geliefert; sie wird nie geschrieben. |

Log: *Dienste › Multi-WAN DynDNS › Log File* (Stufe „Debug“ für alle Details).

## Lizenz

BSD 2-Clause, siehe [LICENSE](LICENSE). Die Anbieter-Module und die Liste der Prüfdienste stammen aus
[os-ddclient](https://github.com/opnsense/plugins/tree/master/dns/ddclient) (© Ad Schellevis, Deciso B.V.
und Beitragende). Es handelt sich um ein Community-Projekt ohne Verbindung zum OPNsense-Projekt.

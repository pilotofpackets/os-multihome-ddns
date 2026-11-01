# os-cfddns – Cloudflare DDNS pro Interface für OPNsense

DynDNS-Plugin für Cloudflare, gebaut für Multi-WAN (z.B. mehrere DSL-Anschlüsse).
Jeder Eintrag ist an ein Interface gebunden und meldet **dessen** öffentliche IP –
nicht die der Default-Route.

## Warum das beim normalen ddclient-Plugin schiefgeht

Das ddclient-Plugin bindet die Abfrage zwar per `curl --interface` an die Adresse des
Interfaces, aber Traffic, den die Firewall selbst erzeugt, folgt der Routing-Tabelle –
also der Default-Route. Dass er trotzdem über das richtige WAN geht, hängt an den
automatischen „force gw“-Regeln von OPNsense. Die greifen nicht, wenn

- *Firewall › Einstellungen › Erweitert › „Disable force gateway“* aktiv ist,
- am Interface kein Gateway als Upstream hinterlegt ist (z.B. statisch hinter einem Router),
- oder eigene `quick`-Regeln vorher matchen (die force-gw-Regeln sind nicht `quick`).

Dann melden ipify & Co. für alle Einträge die IP des Default-WAN.

## Was dieses Plugin anders macht

1. **Eigene Policy-Routing-Regel pro Interface** (`quick`, früh im Regelwerk):
   `pass out quick route-to (<if> <gw>) proto tcp from (<if>) to !<if-netz> port 443`.
   Das Gateway wird auch gefunden, wenn es nicht als Interface-Gateway eingetragen ist.
   Die Regel betrifft nur HTTPS-Verbindungen der Firewall mit der Quelladresse dieses Interfaces.
2. **IP-Ermittlung „Automatisch“**: Hat das Interface selbst eine öffentliche Adresse (PPPoE),
   wird sie direkt genommen. Sonst (Router davor, privates Netz) wird der Check-Dienst mit der
   Interface-Adresse als Quelle abgefragt. CGNAT-Adressen (100.64/10) werden als Fehler erkannt.
3. **Schutz vor falscher IP**: Liefert ein Interface eine IP, die schon einem anderen gehört,
   wird nicht aktualisiert und im Status steht ein klarer Hinweis aufs Routing.
4. **Round-Robin möglich**: Mehrere Einträge dürfen denselben Hostnamen pflegen. Jeder Record
   wird über seinen Kommentar (`opnsense-cfddns:<uuid>`) einem Eintrag zugeordnet. Ein einzelner
   bereits vorhandener, unverwalteter Record wird übernommen (sein Kommentar wird dabei ersetzt).
5. Sofortige Prüfung bei Adresswechsel (`newwanip`), sonst Intervall pro Eintrag (Cron jede Minute),
   regelmäßiger Abgleich mit Cloudflare, Test-Knopf pro Eintrag, eigenes Log.

Check-Dienste: Cloudflare (`1.1.1.1/cdn-cgi/trace`, direkt per IP – keine DNS-Abhängigkeit),
ipify, icanhazip, ident.me oder eigene URL.

## Installation (direkt auf der Firewall)

```sh
# Repo auf die OPNsense holen (z.B. per scp) und dann als root:
sh install.sh
```

Danach: *Dienste › Cloudflare DDNS*

1. Reiter **Einträge**: pro Anschluss einen Eintrag anlegen (Interface, Zone, Hostnamen, API-Token).
2. Reiter **Allgemein**: „Aktiviert“ setzen.
3. **Anwenden** – lädt die Firewall-Regeln, legt den Cron-Job an und prüft sofort.
4. Reiter **Status**: erkannte IP pro Interface; der Kolben-Knopf testet die Ermittlung ohne Update.

Kontrolle der Regeln: `pfctl -sr | grep "IP-Check"`

Entfernen: `sh uninstall.sh` (Einstellungen in der config.xml bleiben erhalten).

### Cloudflare API-Token

*My Profile › API Tokens › Create Token › „Edit zone DNS“*, Berechtigungen **Zone › DNS › Edit**
und **Zone › Zone › Read**, auf die betroffene Zone beschränken.

## Als Paket bauen (optional)

Der Ordner `cfddns/` hat die Struktur des offiziellen
[opnsense/plugins](https://github.com/opnsense/plugins)-Repos. Nach `dns/cfddns` kopieren und dort
auf einer OPNsense mit Build-Umgebung `make package` ausführen.

## Hinweise

- Entwickelt gegen die aktuelle OPNsense-Codebasis (26.x); benötigt nur Bordmittel (`curl`, `python3`).
- Bei HA/CARP: Plugin nur auf dem Master aktivieren.
- Log: *Dienste › Cloudflare DDNS › Log File* bzw. `/var/log/cfddns/`.
- Die Status-Datei liegt unter `/var/db/cfddns/state.json`.

"""
    Multi-WAN DynDNS - Cloudflare

    Ersetzt die Cloudflare-Implementierung von os-ddclient. Jeder Eintrag
    markiert "seine" Records ueber den Kommentar, damit mehrere Interfaces
    denselben Namen pflegen koennen (Round-Robin), ohne sich zu ueberschreiben.

    Zugangsdaten wie bei os-ddclient: Passwort = API-Token (Bearer). Enthaelt der
    Benutzername ein "@", wird E-Mail + Global API Key verwendet.

    BSD 2-Clause License
"""
import re
import syslog
from urllib.parse import quote

import requests

from . import BaseAccount

COMMENT_TAG = 'multiwan-ddns:'


class CloudflareError(Exception):
    pass


class Cloudflare(BaseAccount):
    _priority = 1
    _api = 'https://api.cloudflare.com/client/v4'

    @staticmethod
    def known_services():
        return {'cloudflare': 'Cloudflare'}

    @staticmethod
    def match(account):
        return account.get('service') == 'cloudflare'

    def _log(self, msg):
        if self.is_verbose:
            syslog.syslog(syslog.LOG_INFO, '[debug] Cloudflare %s' % msg)

    def _headers(self):
        headers = {'User-Agent': 'OPNsense-multiwan-ddns', 'Content-Type': 'application/json'}
        username = self.settings.get('username', '') or ''
        if '@' in username:
            headers['X-Auth-Email'] = username
            headers['X-Auth-Key'] = self.settings.get('password', '')
        else:
            headers['Authorization'] = 'Bearer %s' % self.settings.get('password', '')
        return headers

    def _request(self, method, path, payload=None):
        self._log('%s %s%s' % (method, path, (' %s' % payload) if payload else ''))
        try:
            resp = requests.request(method, self._api + path, headers=self._headers(), json=payload, timeout=30)
        except requests.RequestException as exc:
            raise CloudflareError('API nicht erreichbar: %s' % exc)
        try:
            data = resp.json()
        except ValueError:
            raise CloudflareError('ungueltige Antwort (HTTP %d): %s' % (resp.status_code, resp.text[:200]))
        self._log('-> HTTP %d success=%s' % (resp.status_code, data.get('success')))
        if not data.get('success'):
            errors = '; '.join('%s: %s' % (e.get('code'), e.get('message')) for e in (data.get('errors') or []))
            raise CloudflareError('API-Fehler (HTTP %d): %s' % (resp.status_code, errors or 'unbekannt'))
        return data

    def _zone(self):
        zone = (self.settings.get('zone') or '').strip().rstrip('.').lower()
        if not zone:
            raise CloudflareError('keine Zone konfiguriert')
        cached = self._state.get('zone') or {}
        if cached.get('key') == zone and cached.get('id'):
            return cached['id'], cached['name']
        if re.fullmatch(r'[0-9a-f]{32}', zone):
            result = self._request('GET', '/zones/%s' % zone)['result']
        else:
            found = self._request('GET', '/zones?name=%s' % quote(zone))['result']
            if not found:
                raise CloudflareError('Zone "%s" nicht gefunden (Token-Recht Zone:Read pruefen)' % zone)
            result = found[0]
        self._state['zone'] = {'key': zone, 'id': result['id'], 'name': result['name'].lower()}
        return result['id'], result['name'].lower()

    @staticmethod
    def _fqdn(host, zone_name):
        host = host.strip().rstrip('.').lower()
        if host in ('', '@'):
            return zone_name
        if host == zone_name or host.endswith('.' + zone_name):
            return host
        return '%s.%s' % (host, zone_name)

    def _sync(self, zone_id, name, rtype, address):
        tag = COMMENT_TAG + self.id
        proxied = self.settings.get('proxied') is True
        ttl = 1 if proxied else max(1, int(self.settings.get('ttl') or 1))
        records = self._request(
            'GET', '/zones/%s/dns_records?type=%s&name=%s&per_page=100' % (zone_id, rtype, quote(name))
        )['result']
        mine = [rec for rec in records if (rec.get('comment') or '') == tag]
        target = mine[0] if mine else None
        if target is None and len(records) == 1 and not (records[0].get('comment') or '').startswith(COMMENT_TAG):
            target = records[0]   # einzelner, bisher nicht verwalteter Record wird uebernommen
        body = {'content': address, 'ttl': ttl, 'proxied': proxied, 'comment': tag}
        if target is not None:
            unchanged = (target.get('content') == address and bool(target.get('proxied')) == proxied
                         and int(target.get('ttl', 1)) == ttl and (target.get('comment') or '') == tag)
            if unchanged and not self.is_forced:
                return 'unveraendert'
            self._request('PATCH', '/zones/%s/dns_records/%s' % (zone_id, target['id']), body)
            return 'aktualisiert'
        body.update({'type': rtype, 'name': name})
        self._request('POST', '/zones/%s/dns_records' % zone_id, body)
        return 'angelegt'

    def execute(self):
        if not super().execute():
            return False
        address = str(self.current_address)
        rtype = 'AAAA' if ':' in address else 'A'
        zone_id, zone_name = self._zone()
        results = {}
        for host in (self.settings.get('hostnames') or '').split(','):
            if host.strip():
                name = self._fqdn(host, zone_name)
                results[name] = self._sync(zone_id, name, rtype, address)
        self._state['records'] = results
        self.update_state(address=address, status='good')
        return True

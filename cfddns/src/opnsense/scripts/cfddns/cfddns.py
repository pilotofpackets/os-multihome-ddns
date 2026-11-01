#!/usr/local/bin/python3
"""
    Cloudflare DynDNS fuer OPNsense mit IP-Ermittlung pro Interface.

    Jeder Eintrag ist an ein Interface gebunden. Die oeffentliche Adresse wird
    entweder direkt vom Interface gelesen (PPPoE mit oeffentlicher IP) oder per
    Webdienst ermittelt, wobei die Anfrage mit der Quelladresse des Interfaces
    gesendet wird. Zusammen mit der vom Plugin erzeugten route-to-Regel verlaesst
    die Anfrage die Firewall damit ueber genau dieses Interface/Gateway.

    Aufruf:
        cfddns.py cron           faellige Eintraege pruefen (Intervall je Eintrag)
        cfddns.py check          alle Eintraege jetzt pruefen, bei Aenderung aktualisieren
        cfddns.py force          alle Eintraege pruefen und Cloudflare abgleichen
        cfddns.py status         Status als JSON
        cfddns.py test <uuid>    nur ermitteln (ohne Update), Ergebnis als JSON

    BSD 2-Clause License
"""
import fcntl
import ipaddress
import json
import os
import re
import subprocess
import sys
import syslog
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse

CONFIG_XML = os.environ.get('CFDDNS_CONFIG', '/conf/config.xml')
STATE_DIR = os.environ.get('CFDDNS_STATE_DIR', '/var/db/cfddns')
STATE_FILE = os.path.join(STATE_DIR, 'state.json')
LOCK_FILE = os.environ.get('CFDDNS_LOCK', '/var/run/cfddns.lock')
CURL = os.environ.get('CFDDNS_CURL', '/usr/local/bin/curl')
IFCONFIG = os.environ.get('CFDDNS_IFCONFIG', '/sbin/ifconfig')
CF_API = 'https://api.cloudflare.com/client/v4'
COMMENT_TAG = 'opnsense-cfddns:'
USER_AGENT = 'opnsense-cfddns/1.0'

FAMILIES = {'v4': 'IPv4', 'v6': 'IPv6'}
RECORD_TYPE = {'v4': 'A', 'v6': 'AAAA'}

CHECK_SERVICES = {
    'v4': {
        'cloudflare': 'https://1.1.1.1/cdn-cgi/trace',
        'ipify': 'https://api.ipify.org',
        'icanhazip': 'https://ipv4.icanhazip.com',
        'identme': 'https://v4.ident.me',
    },
    'v6': {
        'cloudflare': 'https://[2606:4700:4700::1111]/cdn-cgi/trace',
        'ipify': 'https://api6.ipify.org',
        'icanhazip': 'https://ipv6.icanhazip.com',
        'identme': 'https://v6.ident.me',
    },
}


class DetectError(Exception):
    pass


class CloudflareError(Exception):
    pass


def log(prio, msg):
    syslog.syslog(prio, msg)


# --------------------------------------------------------------------------
# Konfiguration / Status
# --------------------------------------------------------------------------

def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_config():
    root = ET.parse(CONFIG_XML).getroot()

    interfaces = {}
    ifnode = root.find('interfaces')
    if ifnode is not None:
        for child in ifnode:
            device = (child.findtext('if') or '').strip()
            if device:
                interfaces[child.tag] = {
                    'device': device,
                    'descr': (child.findtext('descr') or child.tag.upper()).strip(),
                }

    node = root.find('OPNsense/CloudflareDDNS')
    general = node.find('general') if node is not None else None

    def gen(name, default):
        if general is None:
            return default
        value = general.findtext(name)
        return default if value is None or value == '' else value

    cfg = {
        'enabled': gen('enabled', '0') == '1',
        'duplicate_guard': gen('duplicate_guard', '1') == '1',
        'timeout': max(2, _int(gen('timeout', '10'), 10)),
        'resync_hours': max(1, _int(gen('resync_hours', '6'), 6)),
        'interfaces': interfaces,
        'accounts': [],
    }

    if node is not None:
        for acc in node.findall('accounts/account'):
            def txt(name, default=''):
                value = acc.findtext(name)
                return default if value is None else value.strip()
            cfg['accounts'].append({
                'uuid': acc.get('uuid'),
                'enabled': txt('enabled', '0') == '1',
                'description': txt('description'),
                'interface': txt('interface'),
                'ipversion': txt('ipversion', 'v4') or 'v4',
                'checkip': txt('checkip', 'auto') or 'auto',
                'service': txt('service', 'cloudflare') or 'cloudflare',
                'custom_url4': txt('custom_url4'),
                'custom_url6': txt('custom_url6'),
                'zone': txt('zone').rstrip('.').lower(),
                'hostnames': [h.strip() for h in txt('hostnames').split(',') if h.strip()],
                'token': txt('token'),
                'proxied': txt('proxied', '0') == '1',
                'ttl': max(1, _int(txt('ttl', '1'), 1)),
                'interval': max(1, _int(txt('interval', '5'), 5)),
            })
    return cfg


def families(account):
    return {'v4': ['v4'], 'v6': ['v6'], 'both': ['v4', 'v6']}.get(account['ipversion'], ['v4'])


def load_state():
    try:
        with open(STATE_FILE) as fh:
            state = json.load(fh)
            if isinstance(state, dict) and isinstance(state.get('accounts'), dict):
                return state
    except (OSError, ValueError):
        pass
    return {'accounts': {}}


def save_state(state):
    os.makedirs(STATE_DIR, mode=0o750, exist_ok=True)
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
    os.chmod(tmp, 0o640)
    os.replace(tmp, STATE_FILE)


# --------------------------------------------------------------------------
# IP-Ermittlung
# --------------------------------------------------------------------------

def interface_addresses(device):
    """ Adressen eines Interfaces aus ifconfig lesen.
        IPv4: primaere Adressen (ohne CARP-VIPs), IPv6: globale bevorzugt, ohne temporary/deprecated
    """
    proc = subprocess.run([IFCONFIG, device], capture_output=True, text=True)
    if proc.returncode != 0:
        raise DetectError('Interface %s existiert nicht oder ist nicht aktiv' % device)
    v4, v6 = [], []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or 'vhid' in parts:
            continue
        if parts[0] == 'inet':
            try:
                v4.append(ipaddress.IPv4Address(parts[1]))
            except ValueError:
                continue
        elif parts[0] == 'inet6':
            if any(flag in parts for flag in ('deprecated', 'tentative', 'detached', 'duplicated')):
                continue
            try:
                addr = ipaddress.IPv6Address(parts[1].split('%')[0])
            except ValueError:
                continue
            if addr.is_link_local:
                continue
            v6.append((not addr.is_global, 'temporary' in parts, addr))
    v6.sort(key=lambda item: (item[0], item[1]))
    return {'v4': v4, 'v6': [item[2] for item in v6]}


def service_url(account, fam):
    if account['service'] == 'custom':
        url = account['custom_url4'] if fam == 'v4' else account['custom_url6']
        if not url:
            raise DetectError('Keine eigene %s-URL konfiguriert' % FAMILIES[fam])
        return url
    try:
        return CHECK_SERVICES[fam][account['service']]
    except KeyError:
        return CHECK_SERVICES[fam]['cloudflare']


def parse_address(body, fam, url):
    """ Adresse der gewuenschten Familie aus der Antwort eines Check-Dienstes lesen """
    wanted = ipaddress.IPv4Address if fam == 'v4' else ipaddress.IPv6Address
    host = (urlparse(url).hostname or '').strip('[]')
    candidates = []
    # Cloudflare /cdn-cgi/trace liefert "ip=..." (aber auch "h=1.1.1.1")
    for line in body.splitlines():
        if line.startswith('ip='):
            candidates.append(line[3:].strip())
    candidates.append(body.strip())
    pattern = r'(?:\d{1,3}\.){3}\d{1,3}' if fam == 'v4' else r'[0-9a-fA-F:]*:[0-9a-fA-F:.]+'
    candidates.extend(re.findall(pattern, body))
    for candidate in candidates:
        if candidate == host:
            continue
        try:
            addr = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if isinstance(addr, wanted):
            return addr
    raise DetectError('Keine %s-Adresse in der Antwort von %s gefunden' % (FAMILIES[fam], url))


def web_check(url, source, fam, timeout):
    cmd = [
        CURL, '-sS', '--fail',
        '-4' if fam == 'v4' else '-6',
        '--interface', str(source),
        '--connect-timeout', str(min(timeout, 5)),
        '--max-time', str(timeout),
        '-A', USER_AGENT,
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        raise DetectError('Zeitueberschreitung bei %s' % url)
    if proc.returncode != 0:
        reason = proc.stderr.strip() or 'curl exit %d' % proc.returncode
        raise DetectError('Abfrage von %s ueber %s fehlgeschlagen: %s' % (url, source, reason))
    return parse_address(proc.stdout, fam, url)


def detect(account, fam, cfg):
    """ Oeffentliche Adresse eines Eintrags fuer eine Adressfamilie ermitteln """
    ifinfo = cfg['interfaces'].get(account['interface'])
    info = {
        'family': fam,
        'interface': account['interface'],
        'interface_descr': ifinfo['descr'] if ifinfo else account['interface'],
        'device': ifinfo['device'] if ifinfo else None,
        'local': None,
        'method': None,
        'url': None,
        'ip': None,
    }
    try:
        if ifinfo is None:
            raise DetectError('Interface "%s" ist nicht (mehr) zugewiesen' % account['interface'])
        addrs = interface_addresses(ifinfo['device'])[fam]
        if not addrs:
            raise DetectError('%s (%s) hat keine %s-Adresse' % (info['interface_descr'], info['device'], FAMILIES[fam]))
        local = addrs[0]
        info['local'] = str(local)
        method = account['checkip']
        if method == 'interface' or (method == 'auto' and local.is_global):
            if not local.is_global:
                raise DetectError(
                    'Interface-Adresse %s ist nicht oeffentlich (privat/CGNAT) - Methode "Webdienst" verwenden' % local
                )
            info['method'] = 'interface'
            info['ip'] = str(local)
            return info
        if fam == 'v6' and not local.is_global:
            raise DetectError('%s hat keine globale IPv6-Adresse fuer die Abfrage' % info['interface_descr'])
        info['method'] = 'web'
        info['url'] = service_url(account, fam)
        addr = web_check(info['url'], local, fam, cfg['timeout'])
        if not addr.is_global:
            raise DetectError('Dienst lieferte keine oeffentliche Adresse (%s)' % addr)
        info['ip'] = str(addr)
        return info
    except DetectError as exc:
        info['error'] = str(exc)
        return info


# --------------------------------------------------------------------------
# Cloudflare
# --------------------------------------------------------------------------

def cf_request(token, method, path, payload=None, timeout=30):
    # Token per stdin (-K -), damit er nicht in der Prozessliste auftaucht
    escaped = token.replace('\\', '\\\\').replace('"', '\\"')
    curl_cfg = 'header = "Authorization: Bearer %s"\n' % escaped
    cmd = [CURL, '-sS', '--max-time', str(timeout), '-X', method,
           '-H', 'Content-Type: application/json', '-A', USER_AGENT, '-K', '-']
    if payload is not None:
        cmd += ['--data-binary', json.dumps(payload)]
    cmd.append(CF_API + path)
    try:
        proc = subprocess.run(cmd, input=curl_cfg, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        raise CloudflareError('Zeitueberschreitung bei der Cloudflare-API')
    if proc.returncode != 0:
        raise CloudflareError('Cloudflare-API nicht erreichbar: %s' % (proc.stderr.strip() or proc.returncode))
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise CloudflareError('Ungueltige Antwort der Cloudflare-API: %s' % proc.stdout[:200])
    if not data.get('success'):
        errors = '; '.join(
            '%s: %s' % (err.get('code'), err.get('message')) for err in (data.get('errors') or [])
        ) or 'unbekannter Fehler'
        raise CloudflareError('Cloudflare-API: %s' % errors)
    return data


def resolve_zone(account, entry):
    cached = entry.get('zone') or {}
    if cached.get('key') == account['zone'] and cached.get('id') and cached.get('name'):
        return cached['id'], cached['name']
    if re.fullmatch(r'[0-9a-f]{32}', account['zone']):
        result = cf_request(account['token'], 'GET', '/zones/%s' % account['zone'])['result']
    else:
        found = cf_request(account['token'], 'GET', '/zones?name=%s' % quote(account['zone']))['result']
        if not found:
            raise CloudflareError('Zone "%s" nicht gefunden (Token-Berechtigung Zone:Read pruefen)' % account['zone'])
        result = found[0]
    entry['zone'] = {'key': account['zone'], 'id': result['id'], 'name': result['name'].lower()}
    return result['id'], result['name'].lower()


def fqdn(host, zone_name):
    host = host.strip().rstrip('.').lower()
    if host in ('', '@'):
        return zone_name
    if host == zone_name or host.endswith('.' + zone_name):
        return host
    return '%s.%s' % (host, zone_name)


def sync_record(account, zone_id, name, fam, ip):
    """ Einen Record angleichen. Eigene Records werden ueber den Kommentar erkannt,
        so koennen mehrere Interfaces denselben Namen (Round-Robin) pflegen.
    """
    rtype = RECORD_TYPE[fam]
    tag = COMMENT_TAG + account['uuid']
    ttl = 1 if account['proxied'] else account['ttl']
    token = account['token']
    records = cf_request(
        token, 'GET', '/zones/%s/dns_records?type=%s&name=%s&per_page=100' % (zone_id, rtype, quote(name))
    )['result']
    mine = [rec for rec in records if (rec.get('comment') or '') == tag]
    target = None
    if mine:
        target = mine[0]
    elif len(records) == 1 and not (records[0].get('comment') or '').startswith(COMMENT_TAG):
        # einzelner, bisher nicht verwalteter Record -> uebernehmen
        target = records[0]

    if target is not None:
        if (target.get('content') == ip and bool(target.get('proxied')) == account['proxied']
                and int(target.get('ttl', 1)) == ttl and (target.get('comment') or '') == tag):
            return 'unveraendert'
        cf_request(token, 'PATCH', '/zones/%s/dns_records/%s' % (zone_id, target['id']), {
            'content': ip, 'ttl': ttl, 'proxied': account['proxied'], 'comment': tag
        })
        return 'aktualisiert'
    cf_request(token, 'POST', '/zones/%s/dns_records' % zone_id, {
        'type': rtype, 'name': name, 'content': ip, 'ttl': ttl, 'proxied': account['proxied'], 'comment': tag
    })
    return 'angelegt'


def sync_account(account, entry, fam, ip):
    if not account['token']:
        raise CloudflareError('Kein API-Token konfiguriert')
    zone_id, zone_name = resolve_zone(account, entry)
    results = {}
    for host in account['hostnames']:
        name = fqdn(host, zone_name)
        results[name] = sync_record(account, zone_id, name, fam, ip)
    return results


# --------------------------------------------------------------------------
# Ablauf
# --------------------------------------------------------------------------

def label(account):
    return account['description'] or ', '.join(account['hostnames']) or account['uuid']


def flag_duplicates(detections, cfg, state, now):
    """ Wenn eine per Webdienst ermittelte Adresse auch einem anderen Interface zugeordnet ist,
        lief die Abfrage mit hoher Wahrscheinlichkeit ueber das falsche Gateway.
    """
    owners = {}
    # zuletzt bekannte Adressen anderer Eintraege (letzte 24h, ohne Fehler)
    by_uuid = {acc['uuid']: acc for acc in cfg['accounts'] if acc['enabled']}
    for uuid, st in state['accounts'].items():
        acc = by_uuid.get(uuid)
        if acc is None:
            continue
        for fam in families(acc):
            entry = st.get(fam) or {}
            if entry.get('ip') and not entry.get('error') and now - entry.get('checked', 0) < 86400:
                owners.setdefault((fam, entry['ip']), set()).add(acc['interface'])
    for acc, info in detections:
        if info.get('ip'):
            owners.setdefault((info['family'], info['ip']), set()).add(acc['interface'])
    for acc, info in detections:
        if info.get('ip') and info['method'] == 'web':
            others = owners.get((info['family'], info['ip']), set()) - {acc['interface']}
            if others:
                names = sorted(cfg['interfaces'].get(name, {}).get('descr', name) for name in others)
                info['error'] = (
                    '%s ist auch Interface %s zugeordnet - die Abfrage lief vermutlich ueber das falsche '
                    'Gateway (Policy-Routing pruefen). Kein Update.' % (info['ip'], ', '.join(names))
                )
                info['conflict'] = True


def run(mode):
    cfg = load_config()
    if not cfg['enabled']:
        return {'status': 'disabled'}
    state = load_state()
    now = int(time.time())
    known = set()
    detections = []

    for account in cfg['accounts']:
        known.add(account['uuid'])
        if not account['enabled']:
            continue
        st = state['accounts'].setdefault(account['uuid'], {})
        fams = families(account)
        if mode == 'cron':
            last = min((st.get(fam, {}).get('checked', 0) for fam in fams), default=0)
            if now - last < account['interval'] * 60 - 15:
                continue
        for fam in fams:
            info = detect(account, fam, cfg)
            detections.append((account, info))

    if cfg['duplicate_guard']:
        flag_duplicates(detections, cfg, state, now)

    summary = []
    for account, info in detections:
        fam = info['family']
        st = state['accounts'][account['uuid']]
        entry = st.setdefault(fam, {})
        entry['checked'] = now
        for key in ('local', 'method', 'url', 'device'):
            entry[key] = info.get(key)
        if info.get('error'):
            entry['error'] = info['error']
            log(syslog.LOG_WARNING, '%s [%s %s]: %s' % (label(account), info['interface_descr'], FAMILIES[fam], info['error']))
            summary.append({'uuid': account['uuid'], 'family': fam, 'error': info['error']})
            continue

        changed = entry.get('ip') != info['ip']
        resync = now - entry.get('synced', 0) >= cfg['resync_hours'] * 3600
        retry = bool(entry.get('error'))
        if changed:
            log(syslog.LOG_NOTICE, '%s [%s %s]: neue Adresse %s (vorher %s, Quelle %s)' % (
                label(account), info['interface_descr'], FAMILIES[fam], info['ip'], entry.get('ip') or '-',
                info['url'] or 'Interface'))
        entry['ip'] = info['ip']
        entry['error'] = None
        if not (mode == 'force' or changed or resync or retry):
            continue
        try:
            results = sync_account(account, st, fam, info['ip'])
            entry['synced'] = now
            entry['records'] = results
            touched = [name for name, res in results.items() if res != 'unveraendert']
            if touched:
                entry['updated'] = now
                log(syslog.LOG_NOTICE, '%s: %s -> %s (%s)' % (
                    label(account), ', '.join(touched), info['ip'], ', '.join(results[n] for n in touched)))
            summary.append({'uuid': account['uuid'], 'family': fam, 'ip': info['ip'], 'records': results})
        except CloudflareError as exc:
            entry['error'] = str(exc)
            log(syslog.LOG_ERR, '%s [%s]: %s' % (label(account), FAMILIES[fam], exc))
            summary.append({'uuid': account['uuid'], 'family': fam, 'error': str(exc)})

    # Status geloeschter Eintraege entfernen
    for uuid in list(state['accounts']):
        if uuid not in known:
            del state['accounts'][uuid]
    save_state(state)
    return {'status': 'ok', 'results': summary}


def status():
    cfg = load_config()
    state = load_state()
    rows = []
    for account in cfg['accounts']:
        st = state['accounts'].get(account['uuid'], {})
        ifinfo = cfg['interfaces'].get(account['interface'], {})
        for fam in families(account):
            entry = st.get(fam, {})
            rows.append({
                'uuid': account['uuid'],
                'enabled': account['enabled'],
                'description': account['description'],
                'hostnames': ', '.join(account['hostnames']),
                'interface': ifinfo.get('descr', account['interface']),
                'device': ifinfo.get('device', ''),
                'family': FAMILIES[fam],
                'local': entry.get('local'),
                'ip': entry.get('ip'),
                'method': entry.get('method'),
                'url': entry.get('url'),
                'checked': entry.get('checked'),
                'updated': entry.get('updated'),
                'synced': entry.get('synced'),
                'records': entry.get('records', {}),
                'error': entry.get('error'),
            })
    return {'enabled': cfg['enabled'], 'rows': rows}


def test(uuid):
    cfg = load_config()
    for account in cfg['accounts']:
        if account['uuid'] == uuid:
            detections = [(account, detect(account, fam, cfg)) for fam in families(account)]
            if cfg['duplicate_guard']:
                flag_duplicates(detections, cfg, load_state(), int(time.time()))
            results = []
            for _, info in detections:
                info['family'] = FAMILIES[info['family']]
                results.append(info)
            return {'uuid': uuid, 'description': label(account), 'results': results}
    return {'error': 'Eintrag nicht gefunden'}


def main(argv):
    syslog.openlog('cfddns', syslog.LOG_PID, syslog.LOG_DAEMON)
    if len(argv) < 2 or argv[1] not in ('cron', 'check', 'force', 'status', 'test'):
        print(__doc__)
        return 1
    action = argv[1]
    if action == 'status':
        print(json.dumps(status()))
        return 0
    if action == 'test':
        uuid = argv[2] if len(argv) > 2 else ''
        print(json.dumps(test(uuid)))
        return 0

    with open(LOCK_FILE, 'a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | (fcntl.LOCK_NB if action == 'cron' else 0))
        except BlockingIOError:
            return 0
        try:
            print(json.dumps(run(action)))
        except Exception as exc:
            log(syslog.LOG_ERR, 'unerwarteter Fehler: %s' % exc)
            print(json.dumps({'status': 'error', 'message': str(exc)}))
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

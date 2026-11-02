"""
    Multihome DynDNS - Ermittlung der öffentlichen Adresse pro Interface

    Die Liste der Prüfdienste entspricht der des os-ddclient-Plugins
    (dns/ddclient/.../lib/address.py, Copyright (c) 2022-2025 Ad Schellevis).
    Anders als dort wird jede Abfrage mit der Adresse des gewählten Interfaces
    als Quelle gesendet und per route-to-Regel über dessen Gateway geroutet.

    BSD 2-Clause License
"""
import ipaddress
import os
import re
import subprocess
from urllib.parse import urlparse

from .log import shorten

CURL = os.environ.get('MHDDNS_CURL', '/usr/local/bin/curl')
IFCONFIG = os.environ.get('MHDDNS_IFCONFIG', '/sbin/ifconfig')
PFCTL = os.environ.get('MHDDNS_PFCTL', '/sbin/pfctl')
USER_AGENT = 'OPNsense-multihome-ddns/2.0'

FAMILIES = {'v4': 'IPv4', 'v6': 'IPv6'}

# identisch zu os-ddclient (Schlüssel mit "_" statt "-"/".")
CHECKIP_WEB = {
    'akamai': '%s://whatismyip.akamai.com',
    'akamai_ipv4': '%s://ipv4.whatismyip.akamai.com',
    'akamai_ipv6': '%s://ipv6.whatismyip.akamai.com',
    'cloudflare': '%s://one.one.one.one/cdn-cgi/trace',
    'cloudflare_ipv4': '%s://1.1.1.1/cdn-cgi/trace',
    'cloudflare_ipv6': '%s://[2606:4700:4700::1111]/cdn-cgi/trace',
    'dynu_ipv4': '%s://ipcheck.dynu.com/',
    'dynu_ipv6': '%s://ipcheckv6.dynu.com/',
    'freedns': '%s://freedns.afraid.org/dynamic/check.php',
    'he': '%s://checkip.dns.he.net/',
    'icanhazip': '%s://icanhazip.com/',
    'ipify_ipv4': '%s://api.ipify.org/',
    'ipify_ipv6': '%s://api6.ipify.org/',
    'loopia': '%s://dns.loopia.se/checkip/checkip.php',
    'myonlineportal': '%s://myonlineportal.net/checkip',
    'noip_ipv4': '%s://ip1.dynupdate.no-ip.com/',
    'noip_ipv6': '%s://ip1.dynupdate6.no-ip.com/',
    'nsupdate_info_ipv4': '%s://ipv4.nsupdate.info/myip',
    'nsupdate_info_ipv6': '%s://ipv6.nsupdate.info/myip',
    'zoneedit': '%s://dynamic.zoneedit.com/checkip.html',
}

CHECKIP_DNS = {
    'cloudflare_dns': {
        'nameservers': {'v4': ['1.1.1.1', '1.0.0.1'], 'v6': ['2606:4700:4700::1111', '2606:4700:4700::1001']},
        'qname': 'whoami.cloudflare',
        'rdtype': 'TXT',
        'rdclass': 'CH',
    },
}

# Adressklassen
CGNAT = ipaddress.ip_network('100.64.0.0/10')                      # RFC 6598
RFC1918 = [ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
ULA = ipaddress.ip_network('fc00::/7')                             # RFC 4193
CLASS_LABEL = {
    'public': 'öffentlich',
    'private': 'privat (RFC 1918 / RFC 4193)',
    'cgnat': 'CGNAT (RFC 6598)',
    'reserved': 'reserviert (RFC 6890)',
}


class DetectError(Exception):
    pass


def classify(addr):
    """ public | private | cgnat | reserved """
    addr = ipaddress.ip_address(addr)
    if addr.version == 4:
        if addr in CGNAT:
            return 'cgnat'
        if any(addr in net for net in RFC1918):
            return 'private'
    elif addr in ULA:
        return 'private'
    return 'public' if addr.is_global else 'reserved'


def interface_addresses(device):
    """ IPv4: primäre Adressen ohne CARP-VIPs; IPv6: global vor ULA, ohne temporary/deprecated/link-local """
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
            if addr.is_link_local or addr.is_loopback:
                continue
            v6.append((not addr.is_global, 'temporary' in parts, addr))
    v6.sort(key=lambda item: (item[0], item[1]))
    return {'v4': v4, 'v6': [item[2] for item in v6], 'raw': proc.stdout}


def transform_ip(addr, ipv6host):
    """ IPv6: Interface-Identifier durch den konfigurierten Host-Teil ersetzen (wie os-ddclient) """
    addr = ipaddress.ip_address(addr)
    if ipv6host and addr.version == 6:
        return ipaddress.ip_address(
            ipaddress.ip_network('%s/64' % addr, strict=False).network_address.exploded[0:19] +
            ipaddress.ip_address(ipv6host).exploded[19:]
        )
    return addr


def parse_address(body, fam, url):
    wanted = 4 if fam == 'v4' else 6
    host = (urlparse(url).hostname or '').strip('[]')
    candidates = [line[3:].strip() for line in body.splitlines() if line.startswith('ip=')]
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
        if addr.version == wanted:
            return addr
    raise DetectError('Keine %s-Adresse in der Antwort von %s: "%s"' % (FAMILIES[fam], url, shorten(body, 120)))


def web_check(url, source, fam, timeout, log):
    cmd = [
        CURL, '-sS', '--fail', '-4' if fam == 'v4' else '-6',
        '--interface', str(source),
        '--connect-timeout', str(min(timeout, 5)), '--max-time', str(timeout),
        '-A', USER_AGENT, url,
    ]
    log.debug('Abfrage: %s' % ' '.join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        raise DetectError('Zeitüberschreitung bei %s (Quelle %s)' % (url, source))
    log.debug('Antwort (exit %d): %s %s' % (proc.returncode, shorten(proc.stdout), shorten(proc.stderr)))
    if proc.returncode != 0:
        reason = proc.stderr.strip() or 'curl exit %d' % proc.returncode
        raise DetectError('Abfrage von %s über %s fehlgeschlagen: %s' % (url, source, reason))
    return parse_address(proc.stdout, fam, url)


def dns_check(service, source, fam, timeout, log):
    try:
        import dns.message
        import dns.query
        import dns.rdataclass
        import dns.rdatatype
    except ImportError:
        raise DetectError('dnspython ist nicht installiert')
    spec = CHECKIP_DNS[service]
    query = dns.message.make_query(
        spec['qname'], dns.rdatatype.from_text(spec['rdtype']), dns.rdataclass.from_text(spec['rdclass'])
    )
    errors = []
    for server in spec['nameservers'][fam]:
        log.debug('DNS-Abfrage: %s %s %s an %s, Quelle %s' % (spec['qname'], spec['rdclass'], spec['rdtype'], server, source))
        try:
            response = dns.query.udp(query, server, timeout=timeout, source=str(source))
        except Exception as exc:
            errors.append('%s: %s' % (server, exc))
            continue
        for rrset in response.answer:
            for rdata in rrset:
                text = b''.join(rdata.strings).decode(errors='replace')
                log.debug('DNS-Antwort von %s: %s' % (server, text))
                try:
                    addr = ipaddress.ip_address(text.strip())
                    if (addr.version == 4) == (fam == 'v4'):
                        return addr
                except ValueError:
                    continue
        errors.append('%s: keine passende Antwort' % server)
    raise DetectError('DNS-Abfrage fehlgeschlagen (%s)' % '; '.join(errors))


def service_url(account):
    if account['checkip_service'] == 'custom':
        if not account['custom_url']:
            raise DetectError('Keine eigene URL für den IP-Check konfiguriert')
        return account['custom_url']
    template = CHECKIP_WEB.get(account['checkip_service'], CHECKIP_WEB['cloudflare'])
    return template % ('https' if account['force_ssl'] else 'http')


_pf_rules = None


def policy_rule(device, fam, proto='tcp'):
    """ aktive route-to-Regel für Verkehr mit der Quelladresse dieses Interfaces (oder None)
        proto: tcp für Web-Prüfdienste, udp für die DNS-Abfrage
    """
    global _pf_rules
    if _pf_rules is None:
        try:
            _pf_rules = subprocess.run([PFCTL, '-sr'], capture_output=True, text=True, timeout=15).stdout
        except (OSError, subprocess.TimeoutExpired):
            _pf_rules = ''
    inet = 'inet6' if fam == 'v6' else 'inet'
    for line in _pf_rules.splitlines():
        if ('route-to' in line and 'from (%s)' % device in line and ' %s ' % inet in line
                and ' proto %s ' % proto in line and 'pass' in line.split('route-to')[0]):
            return ' '.join(line.split())
    return None


def detect(account, cfg, log):
    """ Adresse für einen Eintrag ermitteln. Liefert immer ein dict, Fehler in info['error'] """
    fam = account['ipversion']
    ifinfo = cfg['interfaces'].get(account['interface'])
    info = {
        'family': fam,
        'interface': account['interface'],
        'interface_descr': ifinfo['descr'] if ifinfo else account['interface'],
        'device': ifinfo['device'] if ifinfo else None,
        'local': None, 'local_class': None,
        'method': None, 'url': None,
        'ip': None, 'ip_class': None,
        'cgnat': False, 'behind_nat': False,
        'blocked': False, 'error': None,
    }
    tag = '%s [%s %s]' % (account['description'] or account['hostnames'], info['interface_descr'], FAMILIES[fam])
    try:
        if ifinfo is None:
            raise DetectError('Interface "%s" ist nicht (mehr) zugewiesen' % account['interface'])
        addrs = interface_addresses(ifinfo['device'])
        log.debug('%s: Adressen von %s: IPv4 %s, IPv6 %s' % (
            tag, ifinfo['device'], [str(a) for a in addrs['v4']] or '-', [str(a) for a in addrs['v6']] or '-'))
        if not addrs[fam]:
            raise DetectError('%s (%s) hat keine %s-Adresse' % (info['interface_descr'], ifinfo['device'], FAMILIES[fam]))
        local = addrs[fam][0]
        info['local'] = str(local)
        info['local_class'] = classify(local)
        info['cgnat'] = info['local_class'] == 'cgnat'
        info['behind_nat'] = info['local_class'] == 'private'
        if info['cgnat']:
            log.warning('%s: Interface-Adresse %s liegt im CGNAT-Bereich (RFC 6598) - der Anschluss ist von '
                        'aussen über IPv4 nicht erreichbar' % (tag, local))
        elif info['behind_nat']:
            log.debug('%s: Interface-Adresse %s ist privat - Router/NAT davor, öffentliche IP per Dienst' % (tag, local))

        method = account['checkip']
        if method == 'interface' or (method == 'auto' and info['local_class'] == 'public'):
            info['method'] = 'interface'
            addr = transform_ip(local, account['dynipv6host'])
        else:
            if fam == 'v6' and info['local_class'] != 'public':
                raise DetectError('%s hat keine globale IPv6-Adresse für die Abfrage' % info['interface_descr'])
            if account['checkip_service'] in CHECKIP_DNS:
                info['method'] = 'dns'
                info['url'] = 'dns://%s/%s' % (CHECKIP_DNS[account['checkip_service']]['nameservers'][fam][0],
                                               CHECKIP_DNS[account['checkip_service']]['qname'])
                addr = dns_check(account['checkip_service'], local, fam, cfg['timeout'], log)
            else:
                info['method'] = 'web'
                info['url'] = service_url(account)
                addr = web_check(info['url'], local, fam, cfg['timeout'], log)
            addr = transform_ip(addr, account['dynipv6host'])

        info['ip'] = str(addr)
        info['ip_class'] = classify(addr)
        if info['ip_class'] != 'public':
            info['blocked'] = True
            raise DetectError('Ermittelte Adresse %s ist %s und wird nicht geschrieben' % (
                addr, CLASS_LABEL[info['ip_class']]))
        if info['cgnat'] and cfg['block_cgnat']:
            info['blocked'] = True
            raise DetectError('Anschluss hinter CGNAT (Interface %s) - %s ist eine geteilte Adresse des Providers '
                              'und wird nicht geschrieben' % (local, addr))
        return info
    except DetectError as exc:
        info['error'] = str(exc)
        return info

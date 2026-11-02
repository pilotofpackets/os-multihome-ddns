"""
    Multihome DynDNS - Konfiguration aus /conf/config.xml lesen

    BSD 2-Clause License
"""
import os
import xml.etree.ElementTree as ET

CONFIG_XML = os.environ.get('MHDDNS_CONFIG', '/conf/config.xml')
MOUNT = 'OPNsense/MultihomeDDNS'


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

    node = root.find(MOUNT)
    general = node.find('general') if node is not None else None

    def gen(name, default):
        value = general.findtext(name) if general is not None else None
        return default if value is None or value.strip() == '' else value.strip()

    cfg = {
        'enabled': gen('enabled', '0') == '1',
        'loglevel': gen('loglevel', 'info'),
        'policy_routing': gen('policy_routing', '1') == '1',
        'duplicate_guard': gen('duplicate_guard', '1') == '1',
        'block_cgnat': gen('block_cgnat', '1') == '1',
        'timeout': min(60, max(2, _int(gen('timeout', '10'), 10))),
        'resync_hours': max(0, _int(gen('resync_hours', '24'), 24)),
        'force_gw_disabled': root.find('system/pf_disable_force_gw') is not None,
        'interfaces': interfaces,
        'accounts': [],
        'failovers': [],
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
                'ipversion': 'v6' if txt('ipversion') == 'v6' else 'v4',
                'checkip': txt('checkip', 'auto') or 'auto',
                'checkip_service': txt('checkip_service', 'cloudflare') or 'cloudflare',
                'custom_url': txt('custom_url'),
                'force_ssl': txt('force_ssl', '1') == '1',
                'dynipv6host': txt('dynipv6host'),
                'gateway': txt('gateway'),
                'interval': max(1, _int(txt('interval', '5'), 5)),
                **provider_fields(txt),
            })
    if node is not None:
        for fo in node.findall('failovers/failover'):
            def ftxt(name, default=''):
                value = fo.findtext(name)
                return default if value is None else value.strip()
            cfg['failovers'].append({
                'uuid': fo.get('uuid'),
                'enabled': ftxt('enabled', '0') == '1',
                'description': ftxt('description'),
                'ipversion': 'v6' if ftxt('ipversion') == 'v6' else 'v4',
                'members': [m for m in ftxt('members').split(',') if m],
                'strategy': ftxt('strategy', 'order') or 'order',
                'treat_loss': ftxt('treat_loss', '1') == '1',
                'treat_delay': ftxt('treat_delay', '0') == '1',
                'loss_threshold': max(0, _int(ftxt('loss_threshold', '0'), 0)),
                'delay_threshold': max(0, _int(ftxt('delay_threshold', '0'), 0)),
                'failback': ftxt('failback', 'delayed') or 'delayed',
                'failback_minutes': max(0, _int(ftxt('failback_minutes', '5'), 5)),
                'force_ssl': True,
                **provider_fields(ftxt),
            })
    return cfg


def provider_fields(txt):
    """ Anbieter-Felder (Feldnamen wie os-ddclient) """
    return {
        'service': txt('service'),
        'protocol': txt('protocol'),
        'server': txt('server'),
        'resourceId': txt('resourceId'),
        'username': txt('username'),
        'password': txt('password'),
        'hostnames': ','.join(h.strip() for h in txt('hostnames').split(',') if h.strip()),
        'wildcard': txt('wildcard', '0') == '1',
        'zone': txt('zone'),
        'ttl': txt('ttl', '300') or '300',
        'proxied': txt('proxied', '0') == '1',
    }


def label(account):
    return account['description'] or account['hostnames'] or account['uuid']

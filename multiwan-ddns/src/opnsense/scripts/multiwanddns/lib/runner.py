"""
    Multi-WAN DynDNS - Ablauf: pruefen, absichern, beim Anbieter aktualisieren

    BSD 2-Clause License
"""
import json
import os
import time

from .account import AccountFactory
from .config import load_config, label
from .detect import detect, policy_rule, FAMILIES, CLASS_LABEL
from .failover import choose, gateway_status
from .log import Logger

STATE_DIR = os.environ.get('MWDDNS_STATE_DIR', '/var/db/multiwanddns')
STATE_FILE = os.path.join(STATE_DIR, 'state.json')


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


def provider_settings(account, cfg, log, force=False):
    """ Eintrag in das von den os-ddclient-Modulen erwartete Format bringen """
    return {
        'id': account['uuid'],
        'description': account['description'],
        'service': account['service'],
        'protocol': account['protocol'],
        'server': account['server'],
        'resourceId': account['resourceId'],
        'username': account['username'],
        'password': account['password'],
        'hostnames': account['hostnames'],
        'wildcard': account['wildcard'],
        'zone': account['zone'],
        'ttl': account['ttl'],
        'proxied': account['proxied'],
        'force_ssl': account['force_ssl'],
        'verbose': log.enabled('debug'),
        '_force': force,
        '_resync': cfg['resync_hours'] * 3600,
    }


def push(factory, settings, pstate, address, tag, log):
    """ Adresse beim Anbieter eintragen, wenn noetig. Liefert (ergebnis, provider_state, fehler)
        ergebnis: unchanged | updated | error
    """
    settings['_address'] = address
    provider = factory.get(settings)
    if provider is None:
        module_err = factory.unavailable.get(settings['service'].replace('-', '_'), '')
        return 'error', pstate, 'Anbieter "%s" nicht verfuegbar%s' % (
            settings['service'], (': %s' % module_err) if module_err else '')
    provider.state = pstate or {}
    provider._current_address = address
    reason = provider.needs_update()
    if reason is None:
        return 'unchanged', provider.state, None
    log.info('%s: Update bei %s mit %s (%s)' % (tag, settings['service'], address, reason))
    before = provider.mtime
    try:
        provider.execute()
    except Exception as exc:
        return 'error', provider.state, 'Update bei %s fehlgeschlagen: %s' % (settings['service'], exc)
    pstate = provider.state
    if pstate.get('ip') == address and pstate.get('mtime', 0) > before:
        details = pstate.get('records') or pstate.get('status') or 'ok'
        log.notice('%s: %s bei %s eingetragen (%s) [%s]' % (tag, address, settings['service'], settings['hostnames'], details))
        return 'updated', pstate, None
    return 'error', pstate, 'Update bei %s fehlgeschlagen - Details im Log' % settings['service']


def check_policy_routing(detections, cfg, log):
    """ Hinweis, wenn fuer ein per Dienst abgefragtes Interface keine route-to-Regel aktiv ist """
    seen = set()
    for _, info in detections:
        if info.get('method') in ('web', 'dns') and info.get('device'):
            key = (info['device'], info['family'])
            if key in seen:
                continue
            seen.add(key)
            rule = policy_rule(info['device'], info['family'])
            info['policy_rule'] = rule
            if rule:
                log.debug('Policy-Routing aktiv fuer %s %s: %s' % (info['device'], FAMILIES[info['family']], rule))
            elif cfg['policy_routing']:
                log.warning('Keine route-to-Regel fuer %s (%s) aktiv - kein Gateway auf dem Interface gefunden '
                            'oder Einstellungen nicht angewendet. Die Abfrage folgt der Routing-Tabelle.'
                            % (info['interface_descr'], FAMILIES[info['family']]))
            else:
                log.debug('Policy-Routing ist deaktiviert, Abfrage ueber %s folgt der Routing-Tabelle%s' % (
                    info['device'], ' (force gw ist aus!)' if cfg['force_gw_disabled'] else ''))


def flag_duplicates(detections, cfg, state, now, log):
    """ Gleiche per Dienst ermittelte Adresse auf mehreren Interfaces = falsches Routing """
    owners = {}
    by_uuid = {acc['uuid']: acc for acc in cfg['accounts'] if acc['enabled']}
    for uuid, entry in state['accounts'].items():
        acc = by_uuid.get(uuid)
        if acc and entry.get('ip') and not entry.get('error') and now - entry.get('checked', 0) < 86400:
            owners.setdefault((acc['ipversion'], entry['ip']), set()).add(acc['interface'])
    for acc, info in detections:
        if info.get('ip') and not info.get('blocked'):
            owners.setdefault((info['family'], info['ip']), set()).add(acc['interface'])
    for acc, info in detections:
        if info.get('ip') and not info.get('error') and info['method'] in ('web', 'dns'):
            others = owners.get((info['family'], info['ip']), set()) - {acc['interface']}
            if others:
                names = sorted(cfg['interfaces'].get(n, {}).get('descr', n) for n in others)
                info['conflict'] = True
                info['blocked'] = True
                info['error'] = ('%s ist auch Interface %s zugeordnet - die Abfrage lief vermutlich ueber das '
                                 'falsche Gateway (Policy-Routing pruefen). Kein Update.' % (info['ip'], ', '.join(names)))


def _describe(info):
    if info['method'] == 'interface':
        return 'Interface-Adresse'
    return '%s ueber %s' % (info['url'], info['local'])


def run(mode, uuids=None):
    """ mode: cron (faellige), check (alle jetzt), force (Update erzwingen), failover (nur Failover bewerten) """
    started = time.time()
    cfg = load_config()
    log = Logger(cfg['loglevel'])
    if not cfg['enabled']:
        log.debug('Dienst deaktiviert, %s uebersprungen' % mode)
        return {'status': 'disabled'}
    selected = set(uuids or [])
    log.info('Lauf gestartet: %s%s' % (mode, (' fuer %s' % ', '.join(sorted(selected))) if selected else ''))
    if cfg['force_gw_disabled']:
        log.debug('Hinweis: "Disable force gateway" ist gesetzt - das Plugin verwendet eigene route-to-Regeln')

    state = load_state()
    now = int(time.time())
    known = {acc['uuid'] for acc in cfg['accounts']}
    detections = []
    for account in cfg['accounts']:
        if mode == 'failover' or (selected and account['uuid'] not in selected):
            continue
        if not account['enabled']:
            if selected:
                log.info('%s: deaktiviert, uebersprungen' % label(account))
            continue
        entry = state['accounts'].setdefault(account['uuid'], {})
        if mode == 'cron':
            wait = account['interval'] * 60 - 15 - (now - entry.get('checked', 0))
            if wait > 0:
                log.debug('%s: noch nicht faellig (naechste Pruefung in %ds)' % (label(account), wait))
                continue
        detections.append((account, detect(account, cfg, log)))

    check_policy_routing(detections, cfg, log)
    if cfg['duplicate_guard']:
        flag_duplicates(detections, cfg, state, now, log)

    factory = AccountFactory()
    if factory.unavailable:
        log.debug('Nicht verfuegbare Anbieter-Module: %s' % factory.unavailable)

    counts = {'checked': 0, 'updated': 0, 'unchanged': 0, 'blocked': 0, 'error': 0, 'switched': 0}
    for account, info in detections:
        counts['checked'] += 1
        entry = state['accounts'][account['uuid']]
        tag = '%s [%s %s]' % (label(account), info['interface_descr'], FAMILIES[info['family']])
        entry['checked'] = now
        for key in ('device', 'local', 'local_class', 'method', 'url', 'ip_class', 'cgnat', 'behind_nat', 'blocked'):
            entry[key] = info.get(key)
        entry['detected'] = info.get('ip')

        if info.get('error'):
            entry['error'] = info['error']
            entry['status'] = 'blocked' if info.get('blocked') else 'error'
            counts['blocked' if info.get('blocked') else 'error'] += 1
            (log.warning if info.get('blocked') else log.error)('%s: %s' % (tag, info['error']))
            continue

        if entry.get('ip') and entry['ip'] != info['ip']:
            log.notice('%s: neue Adresse %s (vorher %s) via %s' % (tag, info['ip'], entry['ip'], _describe(info)))
        entry['ip'] = info['ip']

        result, pstate, err = push(factory, provider_settings(account, cfg, log, force=(mode == 'force')),
                                   entry.get('provider'), info['ip'], tag, log)
        entry['provider'] = pstate
        entry['error'] = err
        entry['status'] = 'error' if err else 'ok'
        if result == 'updated':
            entry['updated'] = now
            entry['written'] = info['ip']
        elif result == 'unchanged':
            entry['written'] = pstate.get('ip')
            log.info('%s: %s via %s - unveraendert' % (tag, info['ip'], _describe(info)))
        else:
            log.error('%s: %s' % (tag, err))
        counts[{'updated': 'updated', 'unchanged': 'unchanged'}.get(result, 'error')] += 1

    # Failover-Eintraege bei jedem Lauf bewerten (Gateway-Status aendert sich unabhaengig vom Intervall)
    run_failovers(cfg, state, now, log, factory, mode, selected, counts)

    for uuid in list(state['accounts']):
        if uuid not in known:
            del state['accounts'][uuid]
            log.debug('Status des geloeschten Eintrags %s entfernt' % uuid)
    known_fo = {fo['uuid'] for fo in cfg['failovers']}
    for uuid in list(state.get('failovers', {})):
        if uuid not in known_fo:
            del state['failovers'][uuid]
    save_state(state)
    log.info('Lauf beendet (%s): %d geprueft, %d aktualisiert, %d unveraendert, %d blockiert, %d Fehler, '
             '%d Failover-Wechsel, %.1fs' % (mode, counts['checked'], counts['updated'], counts['unchanged'],
                                            counts['blocked'], counts['error'], counts['switched'], time.time() - started))
    return {'status': 'ok', 'counts': counts}


def failover_settings(failover, log, force=False):
    settings = {key: failover[key] for key in ('service', 'protocol', 'server', 'resourceId', 'username', 'password',
                                               'hostnames', 'wildcard', 'zone', 'ttl', 'proxied', 'force_ssl')}
    settings.update({'id': failover['uuid'], 'description': failover['description'],
                     'verbose': log.enabled('debug'), '_force': force, '_resync': 0})
    return settings


def run_failovers(cfg, state, now, log, factory, mode, selected, counts):
    active = [fo for fo in cfg['failovers'] if fo['enabled'] and (not selected or fo['uuid'] in selected
                                                                   or mode in ('cron', 'check', 'failover'))]
    if not active:
        return
    gateways = gateway_status(log)
    for failover in active:
        name = failover['description'] or failover['hostnames']
        before = state.get('failovers', {}).get(failover['uuid'], {}).get('active')
        fstate, member = choose(failover, cfg, state, gateways, now, log)
        if member is None:
            counts['error'] += 1
            continue
        if before and before != member['uuid']:
            counts['switched'] += 1
        force = mode == 'force' and (not selected or failover['uuid'] in selected)
        tag = 'Failover %s' % name
        result, pstate, err = push(factory, failover_settings(failover, log, force), fstate.get('provider'),
                                   member['ip'], tag, log)
        fstate['provider'] = pstate
        fstate['active_ip'] = member['ip']
        if result == 'updated':
            fstate['updated'] = now
            fstate['written'] = member['ip']
            counts['updated'] += 1
        elif result == 'unchanged':
            fstate['written'] = pstate.get('ip')
            log.info('%s: zeigt auf %s (%s) - unveraendert' % (tag, member['name'], member['ip']))
        if err:
            fstate['status'] = 'error'
            fstate['error'] = err
            counts['error'] += 1
            log.error('%s: %s' % (tag, err))


def reset_failover(uuid):
    """ aktives Mitglied verwerfen, damit beim naechsten Lauf neu (bevorzugt) gewaehlt wird """
    cfg = load_config()
    log = Logger(cfg['loglevel'])
    state = load_state()
    fstate = state.setdefault('failovers', {}).get(uuid)
    if fstate is not None:
        fstate.pop('active', None)
        fstate['healthy_since'] = {}
        save_state(state)
        log.notice('Failover %s: manuell zurueckgesetzt, wird neu bewertet' % uuid)
    return run('failover')


def status():
    cfg = load_config()
    state = load_state()
    now = int(time.time())
    rows = []
    for account in cfg['accounts']:
        entry = state['accounts'].get(account['uuid'], {})
        ifinfo = cfg['interfaces'].get(account['interface'], {})
        checked = entry.get('checked')
        rows.append({
            'uuid': account['uuid'],
            'enabled': account['enabled'],
            'description': account['description'],
            'service': account['service'],
            'hostnames': account['hostnames'],
            'interface': ifinfo.get('descr', account['interface']),
            'device': ifinfo.get('device', ''),
            'family': FAMILIES[account['ipversion']],
            'local': entry.get('local'),
            'local_class': entry.get('local_class'),
            'detected': entry.get('detected'),
            'ip_class': entry.get('ip_class'),
            'written': entry.get('written'),
            'cgnat': bool(entry.get('cgnat')),
            'behind_nat': bool(entry.get('behind_nat')),
            'method': entry.get('method'),
            'url': entry.get('url'),
            'checked': checked,
            'next': (checked + account['interval'] * 60) if checked and account['enabled'] and cfg['enabled'] else None,
            'updated': entry.get('updated'),
            'records': (entry.get('provider') or {}).get('records') or {},
            'status': entry.get('status') or ('disabled' if not account['enabled'] else 'pending'),
            'error': entry.get('error'),
        })
    return {
        'enabled': cfg['enabled'],
        'force_gw_disabled': cfg['force_gw_disabled'],
        'policy_routing': cfg['policy_routing'],
        'now': now,
        'class_labels': CLASS_LABEL,
        'rows': rows,
        'failovers': failover_rows(cfg, state),
    }


def failover_rows(cfg, state):
    rows = []
    for failover in cfg['failovers']:
        fstate = state.get('failovers', {}).get(failover['uuid'], {})
        rows.append({
            'uuid': failover['uuid'],
            'enabled': failover['enabled'],
            'description': failover['description'],
            'hostnames': failover['hostnames'],
            'service': failover['service'],
            'family': FAMILIES[failover['ipversion']],
            'strategy': failover['strategy'],
            'failback': failover['failback'],
            'active': fstate.get('active_name'),
            'active_ip': fstate.get('active_ip'),
            'written': fstate.get('written'),
            'updated': fstate.get('updated'),
            'switched': fstate.get('switched'),
            'members': fstate.get('members', []),
            'history': fstate.get('history', []),
            'status': fstate.get('status') or ('disabled' if not failover['enabled'] else 'pending'),
            'error': fstate.get('error'),
        })
    return rows


def test(uuid):
    cfg = load_config()
    log = Logger(cfg['loglevel'])
    for account in cfg['accounts']:
        if account['uuid'] == uuid:
            log.info('Test fuer %s gestartet (ohne Update)' % label(account))
            detections = [(account, detect(account, cfg, log))]
            check_policy_routing(detections, cfg, log)
            if cfg['duplicate_guard']:
                flag_duplicates(detections, cfg, load_state(), int(time.time()), log)
            info = detections[0][1]
            info['family'] = FAMILIES[info['family']]
            info['policy_routing_enabled'] = cfg['policy_routing']
            info['force_gw_disabled'] = cfg['force_gw_disabled']
            log.info('Test fuer %s: %s' % (label(account), info.get('error') or '%s via %s' % (info['ip'], _describe(info))))
            return {'uuid': uuid, 'description': label(account), 'service': account['service'], 'result': info}
    return {'error': 'Eintrag nicht gefunden'}


def services():
    factory = AccountFactory()
    return {'services': factory.known_services(), 'unavailable': factory.unavailable}

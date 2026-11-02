"""
    Multi-WAN DynDNS - Failover-DNS

    Ein Failover-Eintrag (z.B. www.example.com) zeigt auf die Adresse eines
    verfuegbaren Mitglieds. Mitglieder sind normale Interface-Eintraege; deren
    eigene Namen (dsl1..., dsl2...) bleiben unveraendert (Forward/Reverse-DNS).

    Ein Mitglied ist verfuegbar, wenn
      - seine IP-Ermittlung aktuell, fehlerfrei und nicht blockiert ist und
      - das Gateway seines Interfaces laut dpinger nicht offline ist
        (optional auch nicht bei Paketverlust/Latenz bzw. eigenen Schwellwerten).

    Strategien:
      order     Reihenfolge der Mitglieder
      priority  Gateway-Prioritaet aus System > Gateways (bei Gleichstand Reihenfolge)
      latency   geringste Latenz laut dpinger

    Zurueckschalten auf ein besseres Mitglied:
      immediate sofort
      delayed   wenn es seit failback_minutes durchgehend verfuegbar ist
      manual    nur per "Neu bewerten" in der GUI

    BSD 2-Clause License
"""
import json
import os
import re
import subprocess

from .detect import FAMILIES

GATEWAYS_PHP = os.environ.get('MWDDNS_GATEWAYS', '/usr/local/opnsense/scripts/multiwanddns/gateways.php')
HISTORY = 25


def gateway_status(log):
    try:
        proc = subprocess.run([GATEWAYS_PHP], capture_output=True, text=True, timeout=30)
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            log.debug('Gateway-Status: %s' % ', '.join(
                '%s=%s (loss %s, delay %s)' % (n, g.get('status'), g.get('loss'), g.get('delay')) for n, g in data.items()))
            return data
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        log.error('Gateway-Status nicht lesbar: %s' % exc)
    return {}


def number(value):
    match = re.search(r'[-+]?\d+(?:\.\d+)?', str(value or ''))
    return float(match.group()) if match else None


def member_gateway(account, gateways):
    proto = 'inet6' if account['ipversion'] == 'v6' else 'inet'
    found = [gw for gw in gateways.values()
             if gw.get('interface') == account['interface'] and gw.get('ipprotocol') == proto and not gw.get('disabled')]
    found.sort(key=lambda gw: (not gw.get('upstream'), gw.get('priority', 255), gw.get('name')))
    return found[0] if found else None


def member_health(failover, account, entry, gateways, now):
    result = {
        'uuid': account['uuid'], 'name': account['description'] or account['hostnames'],
        'interface': account['interface'], 'ip': entry.get('ip'), 'ok': False, 'reason': None,
        'gateway': None, 'gw_status': None, 'loss': None, 'delay': None, 'priority': 255,
    }
    if not account['enabled']:
        result['reason'] = 'Eintrag deaktiviert'
        return result
    if account['ipversion'] != failover['ipversion']:
        result['reason'] = 'falsche IP-Version (%s)' % FAMILIES[account['ipversion']]
        return result
    gw = member_gateway(account, gateways)
    if gw:
        result.update(gateway=gw['name'], gw_status=gw.get('status'), priority=gw.get('priority', 255),
                      loss=number(gw.get('loss')), delay=number(gw.get('delay')))
    if not entry.get('ip') or entry.get('error') or entry.get('blocked'):
        result['reason'] = entry.get('error') or 'keine gueltige Adresse ermittelt'
        return result
    if now - entry.get('checked', 0) > max(3 * account['interval'] * 60, 300):
        result['reason'] = 'IP-Ermittlung veraltet'
        return result
    if gw:
        status = gw.get('status') or 'none'
        if 'down' in status:
            result['reason'] = 'Gateway %s offline' % gw['name']
            return result
        if failover['treat_loss'] and 'loss' in status:
            result['reason'] = 'Gateway %s meldet Paketverlust (%s)' % (gw['name'], gw.get('loss'))
            return result
        if failover['treat_delay'] and 'delay' in status:
            result['reason'] = 'Gateway %s meldet hohe Latenz (%s)' % (gw['name'], gw.get('delay'))
            return result
        if failover['loss_threshold'] and result['loss'] is not None and result['loss'] >= failover['loss_threshold']:
            result['reason'] = 'Paketverlust %.1f %% >= %d %%' % (result['loss'], failover['loss_threshold'])
            return result
        if failover['delay_threshold'] and result['delay'] is not None and result['delay'] >= failover['delay_threshold']:
            result['reason'] = 'Latenz %.1f ms >= %d ms' % (result['delay'], failover['delay_threshold'])
            return result
    result['ok'] = True
    result['reason'] = 'verfuegbar' if gw else 'verfuegbar (kein Gateway gefunden, nur IP-Pruefung)'
    return result


def choose(failover, cfg, state, gateways, now, log):
    """ aktives Mitglied bestimmen; liefert (fstate, Mitglied-Health oder None) """
    fstate = state.setdefault('failovers', {}).setdefault(failover['uuid'], {})
    accounts = {acc['uuid']: acc for acc in cfg['accounts']}
    name = failover['description'] or failover['hostnames']

    members = []
    for idx, uuid in enumerate(failover['members']):
        if uuid in accounts:
            health = member_health(failover, accounts[uuid], state['accounts'].get(uuid, {}), gateways, now)
            health['order'] = idx
            members.append(health)
    fstate['members'] = members

    since = fstate.setdefault('healthy_since', {})
    for m in members:
        if m['ok']:
            since.setdefault(m['uuid'], now)
        else:
            since.pop(m['uuid'], None)
        log.debug('Failover %s: Mitglied %s - %s' % (name, m['name'], m['reason']))

    if failover['strategy'] == 'priority':
        ranked = sorted(members, key=lambda m: (m['priority'], m['order']))
    elif failover['strategy'] == 'latency':
        ranked = sorted(members, key=lambda m: (m['delay'] if m['delay'] is not None else 1e9, m['order']))
    else:
        ranked = sorted(members, key=lambda m: m['order'])
    candidates = [m for m in ranked if m['ok']]
    by_uuid = {m['uuid']: m for m in members}
    current = by_uuid.get(fstate.get('active'))

    if not candidates:
        fstate['status'] = 'error'
        fstate['error'] = 'Kein Mitglied verfuegbar - Eintrag bleibt auf dem letzten Stand'
        log.error('Failover %s: %s' % (name, fstate['error']))
        return fstate, None

    best = candidates[0]
    target, reason = current, None
    if current is None:
        target, reason = best, 'erste Auswahl' if not fstate.get('active') else 'bisheriges Mitglied entfernt'
    elif not current['ok']:
        target, reason = best, 'Ausfall: %s' % current['reason']
    elif best['uuid'] != current['uuid']:
        if failover['strategy'] == 'latency' and current['delay'] is not None and best['delay'] is not None \
                and current['delay'] - best['delay'] < max(5.0, current['delay'] * 0.2):
            log.debug('Failover %s: %s nur geringfuegig schneller, bleibe bei %s' % (name, best['name'], current['name']))
        elif failover['failback'] == 'immediate':
            target, reason = best, 'zurueckschalten auf bevorzugtes Mitglied'
        elif failover['failback'] == 'delayed':
            stable = now - since.get(best['uuid'], now)
            if stable >= failover['failback_minutes'] * 60:
                target, reason = best, 'zurueckschalten, %s seit %d min stabil' % (best['name'], stable // 60)
            else:
                log.info('Failover %s: %s wieder verfuegbar, zurueckschalten in %ds' % (
                    name, best['name'], failover['failback_minutes'] * 60 - stable))
        else:
            log.info('Failover %s: %s wieder verfuegbar, Zurueckschalten nur manuell' % (name, best['name']))

    if reason:
        previous = current['name'] if current else (fstate.get('active_name') or '-')
        (log.warning if reason.startswith('Ausfall') else log.notice)(
            'Failover %s: %s -> %s (%s)' % (name, previous, target['name'], reason))
        history = fstate.setdefault('history', [])
        history.insert(0, {'time': now, 'from': previous, 'to': target['name'], 'ip': target['ip'], 'reason': reason})
        del history[HISTORY:]
        fstate['switched'] = now
    fstate['active'] = target['uuid']
    fstate['active_name'] = target['name']
    fstate['status'] = 'ok'
    fstate['error'] = None
    return fstate, target

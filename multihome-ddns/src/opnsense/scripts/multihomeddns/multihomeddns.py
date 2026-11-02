#!/usr/local/bin/python3
"""
    Multihome DynDNS für OPNsense

    Aufruf:
        multihomeddns.py cron                 fällige Einträge prüfen + Failover bewerten (minütlich per Cron)
        multihomeddns.py check [uuid,...]     sofort prüfen, bei Aenderung aktualisieren
        multihomeddns.py force [uuid,...]     sofort prüfen und Update beim Anbieter erzwingen
        multihomeddns.py failover             nur Failover-Einträge bewerten (Gateway-Alarm)
        multihomeddns.py reset <uuid>         Failover neu bewerten (z.B. manuelles Zurückschalten)
        multihomeddns.py status               Status als JSON
        multihomeddns.py test <uuid>          IP-Ermittlung testen, ohne zu schreiben
        multihomeddns.py services             verfügbare Anbieter
        multihomeddns.py applied              Hinweis "Einstellungen angewendet" ins Log, danach check

    BSD 2-Clause License
"""
import fcntl
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import runner  # noqa: E402
from lib.config import load_config  # noqa: E402
from lib.log import Logger  # noqa: E402

LOCK_FILE = os.environ.get('MHDDNS_LOCK', '/var/run/multihomeddns.lock')
ACTIONS = ('cron', 'check', 'force', 'failover', 'reset', 'status', 'test', 'services', 'applied')
UUID = re.compile(r'^[0-9a-fA-F-]{36}$')


def uuids(argv):
    if len(argv) < 3 or not argv[2].strip():
        return None
    items = [item.strip() for item in argv[2].split(',') if item.strip()]
    return [item for item in items if UUID.match(item)]


def locked(fn, blocking=True):
    with open(LOCK_FILE, 'a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            return {'status': 'busy'}
        return fn()


def main(argv):
    if len(argv) < 2 or argv[1] not in ACTIONS:
        print(__doc__)
        return 1
    action = argv[1]
    try:
        if action == 'status':
            result = runner.status()
        elif action == 'services':
            result = runner.services()
        elif action == 'test':
            ids = uuids(argv) or ['']
            result = runner.test(ids[0])
        elif action == 'reset':
            ids = uuids(argv) or ['']
            result = locked(lambda: runner.reset_failover(ids[0]))
        elif action == 'applied':
            Logger(load_config()['loglevel']).notice('Einstellungen angewendet (Firewall-Regeln und Cron neu geladen)')
            result = locked(lambda: runner.run('check'))
        elif action == 'cron':
            result = locked(lambda: runner.run('cron'), blocking=False)
        else:
            result = locked(lambda: runner.run(action, uuids(argv)))
    except Exception as exc:
        try:
            Logger('error').error('unerwarteter Fehler bei "%s": %s' % (action, exc))
        finally:
            print(json.dumps({'status': 'error', 'message': str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

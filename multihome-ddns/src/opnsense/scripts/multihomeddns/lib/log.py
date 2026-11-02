"""
    Multihome DynDNS - logging

    Stufen (general.loglevel):
        error    nur Fehler
        warning  Fehler und Warnungen (z.B. CGNAT, private Adressen, Routing-Hinweise)
        notice   zusätzlich Aenderungen und Updates beim Anbieter
        info     zusätzlich jede einzelne Prüfung mit Ergebnis (Standard)
        debug    zusätzlich Details: Adressen, Abfragen, Antworten, Entscheidungen, API-Aufrufe

    Alles landet per syslog (Programmname "multihomeddns") in
    /var/log/multihomeddns/ und ist in der GUI unter Log File sichtbar.

    BSD 2-Clause License
"""
import syslog

IDENT = 'multihomeddns'
LEVELS = {'error': 0, 'warning': 1, 'notice': 2, 'info': 3, 'debug': 4}
PRIORITY = {
    'error': syslog.LOG_ERR,
    'warning': syslog.LOG_WARNING,
    'notice': syslog.LOG_NOTICE,
    'info': syslog.LOG_INFO,
    # debug bewusst als INFO, damit es nicht von einem globalen Filter verschluckt wird
    'debug': syslog.LOG_INFO,
}


class Logger:
    _opened = False

    def __init__(self, level='info'):
        self.level = LEVELS.get(level, LEVELS['info'])
        if not Logger._opened:
            syslog.openlog(IDENT, syslog.LOG_PID, syslog.LOG_DAEMON)
            Logger._opened = True

    def enabled(self, name):
        return LEVELS[name] <= self.level

    def _emit(self, name, msg):
        if self.enabled(name):
            prefix = '[debug] ' if name == 'debug' else ''
            for line in str(msg).splitlines() or ['']:
                syslog.syslog(PRIORITY[name], prefix + line)

    def error(self, msg):
        self._emit('error', msg)

    def warning(self, msg):
        self._emit('warning', msg)

    def notice(self, msg):
        self._emit('notice', msg)

    def info(self, msg):
        self._emit('info', msg)

    def debug(self, msg):
        self._emit('debug', msg)


def shorten(text, limit=300):
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit] + '...'

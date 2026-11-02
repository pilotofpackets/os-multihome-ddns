"""
    Copyright (c) 2022 Ad Schellevis <ad@opnsense.org>
    All rights reserved.

    Angepasst fuer Multi-WAN DynDNS: die Adresse wird nicht mehr hier per checkip
    ermittelt, sondern vom Runner pro Interface bestimmt und als "_address"
    uebergeben. Die Anbieter-Module aus os-ddclient laufen dadurch unveraendert.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.

    THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
    INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
    AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
    AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
    OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.
"""
import glob
import hashlib
import importlib
import os
import sys
import time
import uuid

# Felder, die keine Neuuebertragung ausloesen sollen
_HASH_EXCLUDE = ('id', 'description', 'verbose', 'force_ssl')


class BaseAccount:
    _priority = 255

    def __init__(self, account: dict):
        self._account = account
        self._account['id'] = account.get('id', str(uuid.uuid4()))
        self._account['description'] = account.get('description', '')
        self._state = {}
        self._last_accessed = 0
        self._current_address = None

        hash_list = []
        for fieldname in sorted(account.keys()):
            if fieldname not in _HASH_EXCLUDE and not fieldname.startswith('_'):
                hash_list.append(str(account[fieldname]))
        self._account['md5'] = hashlib.md5("|".join(hash_list).encode()).hexdigest()

    def update_state(self, address, status='good'):
        if address is not None:
            self._state['ip'] = address
            self._state['status'] = status
            self._state['mtime'] = time.time()
            self._state['md5'] = self.md5
        self._last_accessed = time.time()

    @staticmethod
    def known_services():
        return {}

    @property
    def id(self):
        return self._account['id']

    @property
    def settings(self):
        return self._account

    @staticmethod
    def match(account):
        return False

    @property
    def description(self):
        return "%(id)s [%(service)s - %(description)s] " % self._account

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value: dict):
        self._state = dict(value or {})

    @property
    def mtime(self):
        return self._state.get('mtime', 0)

    @property
    def atime(self):
        return self._last_accessed

    @property
    def md5(self):
        return self._account.get('md5')

    @property
    def is_verbose(self):
        return self._account.get('verbose') is True

    @property
    def current_address(self):
        return self._current_address

    @property
    def is_forced(self):
        return self._account.get('_force') is True

    def needs_update(self):
        """ Grund fuer eine Uebertragung oder None """
        if self.is_forced:
            return 'erzwungen'
        if self._state.get('ip') is None:
            return 'noch nie uebertragen'
        if self._current_address != self._state.get('ip'):
            return 'Adresse geaendert (%s -> %s)' % (self._state.get('ip'), self._current_address)
        if self._state.get('md5') != self.md5:
            return 'Einstellungen geaendert'
        resync = self._account.get('_resync', 0)
        if resync and time.time() - self.mtime > resync:
            return 'periodischer Abgleich'
        return None

    def execute(self):
        """ True, wenn der Anbieter aktualisiert werden soll (Unterklassen fuehren das Update dann aus) """
        self._current_address = self._account.get('_address')
        if not self._current_address:
            return False
        return self.needs_update() is not None


class AccountFactory:
    """ Laedt alle Anbieter-Module; Module mit fehlenden Abhaengigkeiten (z.B. boto3) werden gemerkt """

    def __init__(self):
        self.unavailable = {}
        self._classes = []
        pkg = __name__
        for filename in sorted(glob.glob(os.path.join(os.path.dirname(__file__), '*.py'))):
            module = os.path.splitext(os.path.basename(filename))[0]
            if module == '__init__':
                continue
            try:
                importlib.import_module('.%s' % module, pkg)
            except Exception as exc:
                self.unavailable[module] = str(exc)
        for module_name in dir(sys.modules[pkg]):
            mod = getattr(sys.modules[pkg], module_name)
            for attr in dir(mod):
                cls = getattr(mod, attr)
                if isinstance(cls, type) and issubclass(cls, BaseAccount) and cls is not BaseAccount \
                        and cls not in self._classes:
                    self._classes.append(cls)
        self._classes.sort(key=lambda k: k._priority)

    def get(self, account):
        for handler in self._classes:
            if handler.match(account):
                return handler(account)
        return None

    def known_services(self):
        services = {}
        for handler in self._classes:
            data = handler.known_services()
            if isinstance(data, dict):
                services.update(data)
            else:
                for item in data:
                    services[item] = item
        return services

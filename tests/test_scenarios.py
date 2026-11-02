import json, os, sys, syslog, uuid as uuidlib, types
sys.path.insert(0, os.environ['SCRIPTDIR'])
T = os.environ['T']
LOG = []
syslog.syslog = lambda prio, msg=None: LOG.append(msg if msg is not None else prio)
syslog.openlog = lambda *a, **k: None

import requests
DB = {'records': [], 'dyndns': {}}
class Resp:
    def __init__(s, code, data=None, text=None):
        s.status_code = code; s._d = data; s.text = text if text is not None else json.dumps(data)
    def json(s):
        if s._d is None: raise ValueError
        return s._d
def fake_request(method, url, headers=None, json=None, timeout=None, **kw):
    assert headers['Authorization'] == 'Bearer tok123'
    path = url.split('/client/v4')[1]
    ok = lambda r: Resp(200, {'success': True, 'errors': [], 'result': r})
    if path.startswith('/zones?name='): return ok([{'id': 'z' * 32, 'name': 'example.com'}])
    if method == 'GET':
        q = dict(p.split('=') for p in path.split('?')[1].split('&'))
        return ok([r for r in DB['records'] if r['type'] == q['type'] and r['name'] == q['name']])
    if method == 'PATCH':
        rid = path.rsplit('/', 1)[1]
        for r in DB['records']:
            if r['id'] == rid: r.update(json)
        return ok({})
    if method == 'POST':
        rec = dict(json, id=uuidlib.uuid4().hex); DB['records'].append(rec); return ok(rec)
def fake_get(url=None, params=None, auth=None, headers=None, **kw):
    DB['dyndns'][params['hostname']] = params['myip']
    return Resp(200, text='good %s' % params['myip'])
requests.request = fake_request
requests.get = fake_get

import dns.query
class RD:
    def __init__(s, t): s.strings = [t.encode()]
def fake_udp(q, where, timeout=None, source=None):
    m = {'192.168.2.2': '79.200.1.2'}
    ip = '93.184.10.20' if os.environ.get('BROKEN') else m[source]
    return types.SimpleNamespace(answer=[[RD(ip)]])
dns.query.udp = fake_udp

from lib import runner, failover
def gw(**st):
    os.system('python3 %s/gw.py %s' % (T, ' '.join('%s=%s' % kv for kv in st.items())))
def records():
    return {(r['type'], r['name']): r['content'] for r in DB['records']}
def run(mode, ids=None, show=True):
    LOG.clear()
    res = runner.run(mode, ids)
    if show: print('  ->', res.get('counts'))
    return res
def age(seconds, checks=True):
    st = runner.load_state()
    for e in st['accounts'].values(): e['checked'] = e.get('checked', 0) - (seconds if checks else 0)
    for f in st.get('failovers', {}).values():
        f['healthy_since'] = {k: v - seconds for k, v in f.get('healthy_since', {}).items()}
    runner.save_state(st)
def ok(cond, msg):
    print(('  OK   ' if cond else '  FAIL ') + msg)
    if not cond:
        print('\n'.join('     | ' + l for l in LOG[-40:])); sys.exit(1)

print('== 1 Erster Lauf: alle Interfaces korrekt')
gw(); run('check')
r = records()
ok(r[('A', 'dsl1.example.com')] == '93.184.10.20', 'DSL1 per Interface-Adresse (PPPoE)')
ok(r[('A', 'dsl2.example.com')] == '87.150.20.30', 'DSL2 per ipify über 192.168.178.2 (nicht CARP-VIP)')
ok(DB['dyndns'].get('dsl3.dyndns.example') == '79.200.1.2', 'DSL3 per cloudflare-dns über os-ddclient-Modul dyndns2')
ok(('A', 'lte.example.com') not in r, 'LTE hinter CGNAT wird NICHT geschrieben')
ok(any('CGNAT' in l for l in LOG), 'CGNAT im Log gewarnt')
ok(r[('A', 'www.example.com')] == '93.184.10.20', 'Failover www zeigt auf DSL1 (erstes Mitglied)')
ok(sorted(x['content'] for x in DB['records'] if x['name'] == 'vpn.example.com') == ['87.150.20.30', '93.184.10.20'], 'Round-Robin vpn mit zwei Records')
st = runner.status()
lte = [x for x in st['rows'] if x['description'] == 'LTE'][0]
ok(lte['cgnat'] and lte['status'] == 'blocked' and lte['local_class'] == 'cgnat', 'Status: LTE als CGNAT/blockiert markiert')
dsl2 = [x for x in st['rows'] if x['description'] == 'DSL2'][0]
ok(dsl2['behind_nat'] and dsl2['local_class'] == 'private' and dsl2['ip_class'] == 'public', 'Status: DSL2 privat hinter Router, öffentliche IP')
ok(any('[debug]' in l and 'Abfrage:' in l for l in LOG), 'Debug-Log enthaelt Abfragen')
ok(not any('Keine route-to-Regel' in l and ('DSL2' in l or 'DSL3' in l) for l in LOG) and any('Keine route-to-Regel für LTE' in l for l in LOG), 'Regeln für DSL2/DSL3 erkannt, fehlende Regel für LTE gewarnt')

print('== 2 Zweiter Lauf: nichts zu tun')
before = json.dumps(DB, sort_keys=True); res = run('check')
ok(json.dumps(DB, sort_keys=True) == before and res['counts']['updated'] == 0, 'keine Schreibzugriffe')
ok(any('unverändert' in l for l in LOG), 'jede Prüfung im Log (Stufe info)')

print('== 3 cron sofort danach: nichts fällig, Failover trotzdem bewertet')
res = run('cron'); ok(res['counts']['checked'] == 0, 'keine Interface-Prüfung fällig')
ok(any('Failover Main' in l for l in LOG), 'Failover bewertet')

print('== 4 Routing kaputt (alles über DSL1)')
os.environ['BROKEN'] = '1'; age(120); res = run('cron')
ok(records()[('A', 'dsl2.example.com')] == '87.150.20.30', 'DSL2 nicht ueberschrieben')
ok(DB['dyndns']['dsl3.dyndns.example'] == '79.200.1.2', 'DSL3 nicht ueberschrieben')
ok(res['counts']['blocked'] >= 2, 'als blockiert gezaehlt')
del os.environ['BROKEN']; age(120); run('cron', show=False)

print('== 5 Gateway DSL1 Paketverlust -> Failover auf DSL2')
gw(WAN_PPPOE='loss'); run('failover')
ok(records()[('A', 'www.example.com')] == '87.150.20.30', 'www -> DSL2')
ok(any('Ausfall' in l for l in LOG), 'Wechsel im Log mit Grund')
print('== 6 DSL1 wieder gut -> verzoegertes Zurückschalten (5 min)')
gw(); run('failover')
ok(records()[('A', 'www.example.com')] == '87.150.20.30', 'bleibt zunaechst auf DSL2')
age(301, checks=False); run('failover')
ok(records()[('A', 'www.example.com')] == '93.184.10.20', 'nach 5 min zurueck auf DSL1')

print('== 7 PPPoE weg + Gateway down -> DSL2; DSL2 down -> DSL3 (dyndns2 Mitglied)')
open(T + '/pppoe_down', 'w').close(); gw(WAN_PPPOE='down'); age(120); run('cron')
ok(records()[('A', 'www.example.com')] == '87.150.20.30', 'www -> DSL2')
gw(WAN_PPPOE='down', DSL2_GW='down'); run('failover')
ok(records()[('A', 'www.example.com')] == '79.200.1.2', 'www -> DSL3')
print('== 8 alle Gateways down -> Eintrag bleibt stehen')
gw(WAN_PPPOE='down', DSL2_GW='down', DSL3_GW='down'); res = run('failover')
ok(records()[('A', 'www.example.com')] == '79.200.1.2' and any('Kein Mitglied' in l for l in LOG), 'bleibt auf letztem Stand, Fehler geloggt')
os.remove(T + '/pppoe_down')

print('== 9 manuelles Zurückschalten (reset) und Strategie latency')
gw(); age(120); run('cron', show=False)
runner.reset_failover('99999999-9999-9999-9999-999999999999')
ok(records()[('A', 'www.example.com')] == '93.184.10.20', 'reset -> sofort DSL1')
os.system("sed -i 's#<strategy>order</strategy>#<strategy>latency</strategy>#' %s/config.xml" % T)
runner.reset_failover('99999999-9999-9999-9999-999999999999')
ok(records()[('A', 'www.example.com')] == '87.150.20.30', 'latency -> DSL2 (9 ms)')

print('== 10 Force-Update einzelner Eintrag')
patches = []
orig = requests.request
def counting(method, url, **kw):
    if method == 'PATCH': patches.append(url)
    return orig(method, url, **kw)
requests.request = counting
run('force', ['22222222-2222-2222-2222-222222222222'])
ok(len(patches) == 2, 'DSL2: beide Records neu geschrieben (%d PATCH)' % len(patches))
requests.request = orig

print('== 11 Test-Aktion mit Policy-Rule-Info')
t = runner.test('22222222-2222-2222-2222-222222222222')['result']
ok(t['policy_rule'] and 'route-to (igb1' in t['policy_rule'] and t['force_gw_disabled'], 'route-to-Regel gefunden, force gw aus erkannt')
t = runner.test('11111111-1111-1111-1111-111111111111')['result']
ok(t['method'] == 'interface', 'DSL1 per Interface')

print('== 12 private Adresse wird nie geschrieben (Methode Interface auf DSL2)')
os.system("sed -i 's#<description>DSL2</description><interface>opt1</interface><ipversion>v4</ipversion><checkip>auto#<description>DSL2</description><interface>opt1</interface><ipversion>v4</ipversion><checkip>interface#' %s/config.xml" % T)
run('check', ['22222222-2222-2222-2222-222222222222'])
ok(records()[('A', 'dsl2.example.com')] == '87.150.20.30' and any('privat' in l for l in LOG), '192.168.178.2 blockiert')

print('== 13 services / status JSON')
s = runner.services()
ok('cloudflare' in s['services'] and 'netcup' in s['services'] and 'noip' in s['services'], '%d Anbieter, nicht ladbar: %s' % (len(s['services']), list(s['unavailable'])))
st = runner.status()
ok(st['failovers'][0]['history'] and st['failovers'][0]['members'], 'Failover-Status mit Mitgliedern und Historie')
print('== 14 Records mit Kennzeichen der Vorgaengerversion werden übernommen, nicht dupliziert')
uid = '11111111-1111-1111-1111-111111111111'
for rec in DB['records']:
    if rec.get('comment') == 'multihome-ddns:' + uid:
        rec['comment'] = 'multiwan-ddns:' + uid
count = len(DB['records'])
run('force', [uid])
ok(len(DB['records']) == count, 'keine zusaetzlichen Records angelegt')
ok(not any((r.get('comment') or '').startswith('multiwan-ddns:') for r in DB['records']), 'Kennzeichen auf multihome-ddns umgeschrieben')
print('ALLE TESTS OK')

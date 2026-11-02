"""
Serve the rendered preview pages, mock the plugin API with realistic sample data and
take screenshots with Chrome (desktop + mobile width, grid, dialogs, details).
usage: shoot.py <site_dir> <model_xml> <out_dir>
"""
import functools
import http.server
import json
import sys
import threading
import time
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright

SITE, MODEL, OUT = sys.argv[1:4]
NOW = int(time.time())

ACC = [
    dict(uuid='11111111-1111-1111-1111-111111111111', enabled='1', description='DSL1 Telekom', interface='DSL1', ipversion='IPv4',
         checkip='Automatisch', service='Cloudflare', hostnames='dsl1,vpn', interval='1',
         rt_local='198.51.100.20', rt_local_class='public', rt_detected='198.51.100.20', rt_ip_class='public', rt_written='198.51.100.20',
         rt_cgnat=False, rt_behind_nat=False, rt_method='interface', rt_url=None, rt_checked=NOW - 35, rt_updated=NOW - 3 * 3600,
         rt_status='ok', rt_error=None, rt_device='pppoe0'),
    dict(uuid='22222222-2222-2222-2222-222222222222', enabled='1', description='DSL2 Vodafone', interface='DSL2', ipversion='IPv4',
         checkip='Automatisch', service='Cloudflare', hostnames='dsl2,vpn', interval='1',
         rt_local='192.168.178.2', rt_local_class='private', rt_detected='203.0.113.30', rt_ip_class='public', rt_written='203.0.113.30',
         rt_cgnat=False, rt_behind_nat=True, rt_method='web', rt_url='https://api.ipify.org/', rt_checked=NOW - 35,
         rt_updated=NOW - 26 * 3600, rt_status='ok', rt_error=None, rt_device='igb1'),
    dict(uuid='33333333-3333-3333-3333-333333333333', enabled='1', description='DSL1 Telekom v6', interface='DSL1', ipversion='IPv6',
         checkip='Automatisch', service='Cloudflare', hostnames='dsl1', interval='5',
         rt_local='2001:db8:f70b:6400::5', rt_local_class='public', rt_detected='2001:db8:f70b:6400::5', rt_ip_class='public',
         rt_written='2001:db8:f70b:6400::5', rt_cgnat=False, rt_behind_nat=False, rt_method='interface', rt_url=None,
         rt_checked=NOW - 140, rt_updated=NOW - 9 * 86400, rt_status='ok', rt_error=None, rt_device='pppoe0'),
    dict(uuid='44444444-4444-4444-4444-444444444444', enabled='1', description='LTE Backup', interface='LTE', ipversion='IPv4',
         checkip='Automatisch', service='STRATO', hostnames='lte.example.de', interval='5',
         rt_local='100.70.1.9', rt_local_class='cgnat', rt_detected='192.0.2.55', rt_ip_class='public', rt_written=None,
         rt_cgnat=True, rt_behind_nat=False, rt_method='web', rt_url='https://api.ipify.org/', rt_checked=NOW - 200,
         rt_updated=None, rt_status='blocked',
         rt_error='Anschluss hinter CGNAT (Interface 100.70.1.9) - 192.0.2.55 ist eine geteilte Adresse des Providers und wird nicht geschrieben',
         rt_device='igb3'),
    dict(uuid='55555555-5555-5555-5555-555555555555', enabled='0', description='Kabel (Reserve)', interface='KABEL', ipversion='IPv4',
         checkip='Prüfdienst über dieses Interface', service='DynDNS.com', hostnames='kabel.dyndns.example', interval='5',
         rt_local=None, rt_local_class=None, rt_detected=None, rt_ip_class=None, rt_written=None, rt_cgnat=False,
         rt_behind_nat=False, rt_method=None, rt_url=None, rt_checked=None, rt_updated=None, rt_status='disabled',
         rt_error=None, rt_device='igb4'),
]
MEMBERS = [
    dict(uuid=ACC[0]['uuid'], name='DSL1 Telekom', gateway='WAN_PPPOE', gw_status='none', loss=0.0, delay=14.8, priority=1,
         ip='198.51.100.20', ok=True, reason='verfügbar'),
    dict(uuid=ACC[1]['uuid'], name='DSL2 Vodafone', gateway='DSL2_GW', gw_status='none', loss=0.0, delay=9.1, priority=2,
         ip='203.0.113.30', ok=True, reason='verfügbar'),
    dict(uuid=ACC[3]['uuid'], name='LTE Backup', gateway='LTE_GW', gw_status='loss', loss=22.0, delay=61.0, priority=5,
         ip='192.0.2.55', ok=False, reason='Gateway LTE_GW meldet Paketverlust (22.0 %)'),
]
FO = [dict(uuid='99999999-9999-9999-9999-999999999999', enabled='1', description='Webserver', ipversion='IPv4',
           members='DSL1 Telekom,DSL2 Vodafone,LTE Backup', strategy='order', failback='delayed', service='Cloudflare',
           hostnames='www,@', rt_active='DSL1 Telekom', rt_active_ip='198.51.100.20', rt_written='198.51.100.20',
           rt_updated=NOW - 2 * 3600, rt_switched=NOW - 2 * 3600, rt_members=MEMBERS, rt_status='ok', rt_error=None,
           rt_history=[dict(time=NOW - 2 * 3600, **{'from': 'DSL2 Vodafone'}, to='DSL1 Telekom', ip='198.51.100.20',
                            reason='zurückschalten, DSL1 Telekom seit 5 min stabil'),
                       dict(time=NOW - 3 * 3600, **{'from': 'DSL1 Telekom'}, to='DSL2 Vodafone', ip='203.0.113.30',
                            reason='Ausfall: Gateway WAN_PPPOE offline')])]

model = ET.parse(MODEL).getroot().find('items')
INTERFACES = {'wan': 'DSL1', 'opt1': 'DSL2', 'opt3': 'LTE', 'opt4': 'KABEL', 'lan': 'LAN'}


def node_values(node, values):
    out = {}
    for fld in node:
        t = fld.get('type', '')
        default = values.get(fld.tag, fld.findtext('Default') or '')
        if t == 'OptionField':
            out[fld.tag] = {k.tag: {'value': k.text, 'selected': 1 if k.tag == default else 0} for k in fld.find('OptionValues')}
        elif t == 'InterfaceField':
            out[fld.tag] = {k: {'value': v, 'selected': 1 if k == default else 0} for k, v in INTERFACES.items()}
        elif t == 'ModelRelationField':
            sel = default.split(',')
            out[fld.tag] = {a['uuid']: {'value': a['description'], 'selected': 1 if a['uuid'] in sel else 0} for a in ACC}
        elif t == 'UpdateOnlyTextField':
            out[fld.tag] = ''
        else:
            out[fld.tag] = default
    return out


def api(path):
    p = path.split('?')[0]
    if p.endswith('/settings/searchAccount'):
        return {'rows': ACC, 'rowCount': len(ACC), 'total': len(ACC), 'current': 1}
    if p.endswith('/settings/searchFailover'):
        return {'rows': FO, 'rowCount': 1, 'total': 1, 'current': 1}
    if '/settings/getAccount' in p:
        return {'account': node_values(model.find('accounts/account'), dict(
            enabled='1', description='DSL2 Vodafone', interface='opt1', service='cloudflare', zone='example.com',
            hostnames='dsl2,vpn', checkip_service='ipify_ipv4', ttl='1', interval='1'))}
    if '/settings/getFailover' in p:
        return {'failover': node_values(model.find('failovers/failover'), dict(
            description='Webserver', members=','.join(m['uuid'] for m in MEMBERS), service='cloudflare', zone='example.com',
            hostnames='www,@', ttl='60'))}
    if p.endswith('/settings/get'):
        return {'multihomeddns': {'general': node_values(model.find('general'), dict(enabled='1'))}}
    if p.endswith('/service/status'):
        return {'enabled': True, 'force_gw_disabled': True, 'policy_routing': True, 'now': NOW, 'rows': [], 'failovers': []}
    if '/service/test/' in p:
        return {'uuid': ACC[1]['uuid'], 'description': 'DSL2 Vodafone', 'service': 'cloudflare', 'result': dict(
            family='IPv4', interface='opt1', interface_descr='DSL2', device='igb1', local='192.168.178.2', local_class='private',
            method='web', url='https://api.ipify.org/', ip='203.0.113.30', ip_class='public', cgnat=False, behind_nat=True,
            blocked=False, error=None, policy_routing_enabled=True, force_gw_disabled=False, gateway_mode='automatisch', gateway_chosen='DSL2_GW',
            gateways=[dict(name='DSL2_GW', address='192.168.178.1', status='none', upstream=True, priority=2, disabled=False)],
            policy_rule='pass out quick route-to (igb1 192.168.178.1) inet proto tcp from (igb1) to ! (igb1:network) port = https keep state allow-opts')}
    return {'status': 'ok'}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), functools.partial(Quiet, directory=SITE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    shots = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        for width, tag in ((1440, 'desktop'), (1100, 'sidebar'), (820, 'tablet')):
            page = browser.new_page(viewport={'width': width, 'height': 900}, device_scale_factor=1)
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.route('**/api/**', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(api(route.request.url.split('8765')[1]))))
            for name in ('index', 'failover', 'general'):
                page.goto('http://127.0.0.1:8765/ui/multihomeddns/%s.html' % name)
                page.wait_for_timeout(1500)
                f = '%s/%s_%s.png' % (OUT, name, tag)
                page.screenshot(path=f, full_page=True)
                shots.append(f)
                if tag == 'desktop' and name == 'index':
                    page.locator('#grid-accounts .command-edit').nth(1).click()
                    page.wait_for_timeout(1200)
                    page.screenshot(path='%s/index_dialog.png' % OUT, full_page=False)
                    page.evaluate("$('#DialogAccount').modal('hide')")
                    page.wait_for_timeout(600)
                    page.locator('#grid-accounts .command-test_entry').nth(1).click()
                    page.wait_for_timeout(1200)
                    page.screenshot(path='%s/index_test.png' % OUT, full_page=False)
                    shots += ['%s/index_dialog.png' % OUT, '%s/index_test.png' % OUT]
                if tag == 'desktop' and name == 'failover':
                    page.locator('#grid-failovers .command-details').first.click()
                    page.wait_for_timeout(1200)
                    page.screenshot(path='%s/failover_details.png' % OUT, full_page=False)
                    shots.append('%s/failover_details.png' % OUT)
            if errors:
                print('JS errors (%s):' % tag, errors[:5])
            page.close()
        browser.close()
    srv.shutdown()
    print('\n'.join(shots))


main()

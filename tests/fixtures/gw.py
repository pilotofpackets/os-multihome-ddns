import json, sys
st = dict(a.split('=') for a in sys.argv[1:])
gws = {'WAN_PPPOE': ('wan', 1), 'DSL2_GW': ('opt1', 2), 'DSL3_GW': ('opt2', 3), 'LTE_GW': ('opt3', 4)}
out = {n: {'name': n, 'interface': i, 'ipprotocol': 'inet', 'priority': p, 'upstream': True, 'disabled': False,
           'monitored': True, 'status': st.get(n, 'none'), 'loss': '25.0 %' if 'loss' in st.get(n, '') else '0.0 %',
           'delay': {'WAN_PPPOE': '15.0 ms', 'DSL2_GW': '9.0 ms', 'DSL3_GW': '30.0 ms'}.get(n, '50 ms')} for n, (i, p) in gws.items()}
json.dump(out, open(sys.argv[0].replace('gw.py', 'gw.json'), 'w'))

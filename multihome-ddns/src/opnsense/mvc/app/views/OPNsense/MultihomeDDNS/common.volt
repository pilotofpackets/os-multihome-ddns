{# Multihome DynDNS - gemeinsame Helfer (Badges, Anbieter-Felder, Zeit) #}
<style>
    .mhddns-badge { display: inline-block; margin: 1px 2px 1px 0; font-size: 85%; }
    .mhddns-ip { font-family: monospace; }
    .mhddns-legend .label { margin-right: 4px; }
    .mhddns-cgnat-row { background-color: rgba(240, 173, 78, 0.15) !important; }
</style>
<script>
    const MHDDNS_CLASS = {
        'public':   ['label-success', "{{ lang._('öffentlich') }}", "{{ lang._('Öffentliche Adresse') }}"],
        'private':  ['label-danger',  "{{ lang._('privat') }}", "{{ lang._('Privater Bereich (RFC 1918 / RFC 4193) – wird nie geschrieben') }}"],
        'cgnat':    ['label-warning', "{{ lang._('CGNAT') }}", "{{ lang._('Carrier-Grade NAT (RFC 6598, 100.64.0.0/10) – Anschluss von außen nicht erreichbar, wird nicht geschrieben') }}"],
        'reserved': ['label-danger',  "{{ lang._('reserviert') }}", "{{ lang._('Reservierter Bereich (RFC 6890) – wird nie geschrieben') }}"]
    };
    const MHDDNS_STATUS = {
        'ok':       ['label-success', "{{ lang._('OK') }}"],
        'blocked':  ['label-warning', "{{ lang._('blockiert') }}"],
        'error':    ['label-danger',  "{{ lang._('Fehler') }}"],
        'pending':  ['label-default', "{{ lang._('ausstehend') }}"],
        'disabled': ['label-default', "{{ lang._('deaktiviert') }}"]
    };

    function mwEsc(value) {
        return $('<div/>').text(value === null || value === undefined ? '' : String(value)).html();
    }
    function mwBadge(cls, text, title) {
        return '<span class="label ' + cls + ' mhddns-badge"' + (title ? ' title="' + mwEsc(title) + '"' : '') + '>' + mwEsc(text) + '</span>';
    }
    function mwClassBadge(addrClass) {
        const c = MHDDNS_CLASS[addrClass];
        return c ? mwBadge(c[0], c[1], c[2]) : '';
    }
    function mwStatusBadge(status, error) {
        const s = MHDDNS_STATUS[status] || MHDDNS_STATUS['pending'];
        return mwBadge(s[0], s[1], error || '');
    }
    function mwAgo(ts) {
        if (!ts) {
            return '-';
        }
        const diff = Math.round(Date.now() / 1000 - ts);
        let text;
        if (diff < 90) {
            text = diff + ' s';
        } else if (diff < 5400) {
            text = Math.round(diff / 60) + ' min';
        } else if (diff < 172800) {
            text = Math.round(diff / 3600) + ' h';
        } else {
            text = Math.round(diff / 86400) + ' d';
        }
        return '<span title="' + new Date(ts * 1000).toLocaleString() + '">' + "{{ lang._('vor') }} " + text + '</span>';
    }
    function mwTime(ts) {
        return ts ? new Date(ts * 1000).toLocaleString() : '-';
    }

    /* show only the provider fields the selected service uses (prefix: account | failover) */
    const MHDDNS_DYNDNS2 = ['dyndns2', 'desec-v4', 'desec-v6', 'dns-o-matic', 'dynu', 'he-net', 'he-net-tunnel', 'inwx',
        'loopia', 'nsupdatev4', 'nsupdatev6', 'ovh', 'spdyn', 'strato', 'noip', 'custom'];
    const MHDDNS_FIELDS = {
        'protocol': ['custom'],
        'server': ['custom', 'powerdns'],
        'resourceId': ['azure'],
        'zone': ['allinkl', 'aws', 'cloudflare', 'dnspodcn', 'digitalocean', 'gandi', 'hetzner', 'hetzner-legacy', 'hostinger'],
        'ttl': ['aws', 'cloudflare', 'hetzner', 'hetzner-legacy', 'hostinger', 'netcup', 'powerdns'],
        'proxied': ['cloudflare'],
        'wildcard': MHDDNS_DYNDNS2,
        'username': '!duckdns,gandi,hostinger,digitalocean,powerdns'
    };
    function mwProviderFields(prefix) {
        const service = $('#' + prefix + '\\.service').val();
        $.each(MHDDNS_FIELDS, function (field, services) {
            let show;
            if (typeof services === 'string') {
                show = services.substring(1).split(',').indexOf(service) === -1;
            } else {
                show = services.indexOf(service) !== -1;
            }
            $('#' + prefix + '\\.' + field).closest('tr').toggle(show);
        });
    }
</script>

{# Multihome DynDNS - gemeinsame Helfer (Styles, Badges, Anbieter-Felder, Zeit) #}
<style>
    /* Statusleiste ueber der Tabelle */
    .mhddns-summary {
        display: flex;
        flex-wrap: wrap;
        align-items: stretch;
        gap: 12px;
        padding: 15px;
        border-bottom: 1px solid #e5e5e5;
    }
    .mhddns-stat {
        min-width: 110px;
        padding: 6px 14px;
        border: 1px solid #e5e5e5;
        border-radius: 3px;
        background: #fafafa;
    }
    .mhddns-stat-num {
        display: block;
        font-size: 22px;
        font-weight: 600;
        line-height: 1.2;
    }
    .mhddns-stat-label {
        font-size: 12px;
        color: #777;
        white-space: nowrap;
    }
    .mhddns-stat-label .fa { font-size: 9px; vertical-align: middle; margin-right: 3px; }
    .mhddns-summary-info {
        flex: 1 1 320px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 4px;
        font-size: 12px;
        color: #555;
        text-align: right;
    }
    .mhddns-help {
        display: none;
        padding: 12px 15px;
        border-bottom: 1px solid #e5e5e5;
        background: #fcfcfc;
        font-size: 13px;
    }
    .mhddns-help ul { margin: 6px 0 0 0; padding-left: 18px; }

    /* Tabellenzellen: mehrzeilig statt abgeschnitten */
    .mhddns-cell {
        white-space: normal;
        line-height: 1.45;
        overflow-wrap: break-word;
    }
    .mhddns-sub {
        display: block;
        font-size: 12px;
        color: #888;
    }
    .mhddns-ip {
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .mhddns-ip6 {
        font-variant-numeric: tabular-nums;
        white-space: normal;
        overflow-wrap: normal;
    }
    .mhddns-cell .label {
        display: inline-block;
        margin: 1px 4px 1px 0;
        padding: .2em .5em .25em;
        font-size: 11px;
        vertical-align: 1px;
    }
    .mhddns-msg {
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        margin-top: 3px;
        font-size: 12px;
        line-height: 1.35;
        cursor: help;
    }
    .mhddns-msg.warn { color: #9a5b00; }
    .mhddns-msg.err { color: #b52b27; }
    .mhddns-flags { font-size: 12px; color: #555; }
    .mhddns-testtable { table-layout: fixed; width: 100%; }
    .mhddns-testtable td:first-child { color: #666; }
    .mhddns-rule {
        display: block;
        margin-top: 4px;
        padding: 4px 6px;
        white-space: normal;
        word-break: break-all;
        font-size: 11px;
        color: #444;
        background: #f5f5f5;
    }
    .mhddns-flags span { white-space: nowrap; margin-left: 12px; }
    .mhddns-flags span:first-child { margin-left: 0; }
    .mhddns-legend { font-size: 12px; color: #555; white-space: nowrap; }
    .mhddns-legend .label { font-size: 11px; padding: .2em .5em .25em; }
    .mhddns-member {
        display: block;
        white-space: nowrap;
    }
    .mhddns-member .fa-star { color: #d94f00; margin-left: 4px; font-size: 11px; }
    .mhddns-member .fa-circle { font-size: 9px; vertical-align: 1px; margin-right: 4px; }

    /* Aktionsleiste unter der Tabelle */
    .mhddns-actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        padding: 15px;
    }
    .mhddns-actions .mhddns-spacer { flex: 1 1 auto; }
    .mhddns-actions .alert { flex: 1 1 100%; margin: 0; }

    @media (max-width: 767px) {
        .mhddns-summary-info { text-align: left; }
        .mhddns-actions .mhddns-spacer { display: none; }
    }
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
    function mwCell(html) {
        return '<div class="mhddns-cell">' + html + '</div>';
    }
    function mwSub(html) {
        return '<span class="mhddns-sub">' + html + '</span>';
    }
    function mwIp(ip, strong) {
        if (!ip) {
            return '<span class="text-muted">–</span>';
        }
        const v6 = String(ip).indexOf(':') !== -1;
        const text = v6 ? mwEsc(ip).split(':').join(':<wbr>') : mwEsc(ip);
        const tag = strong ? 'strong' : 'span';
        return '<' + tag + ' class="' + (v6 ? 'mhddns-ip6' : 'mhddns-ip') + '">' + text + '</' + tag + '>';
    }
    function mwMsg(text, kind) {
        return '<span class="mhddns-msg ' + (kind === 'warn' ? 'warn' : 'err') + '" title="' + mwEsc(text) + '">' + mwEsc(text) + '</span>';
    }
    function mwBadge(cls, text, title) {
        return '<span class="label ' + cls + '"' + (title ? ' title="' + mwEsc(title) + '"' : '') + '>' + mwEsc(text) + '</span>';
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
            return '–';
        }
        const diff = Math.max(0, Math.round(Date.now() / 1000 - ts));
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
    const MHDDNS_GW = {
        'none': ['text-success', "{{ lang._('Online') }}"],
        'down': ['text-danger', "{{ lang._('Offline') }}"],
        'force_down': ['text-danger', "{{ lang._('Offline (erzwungen)') }}"],
        'loss': ['text-warning', "{{ lang._('Paketverlust') }}"],
        'delay': ['text-warning', "{{ lang._('Latenz') }}"],
        'delay+loss': ['text-warning', "{{ lang._('Latenz, Paketverlust') }}"]
    };
    function mwGwStatus(status) {
        if (!status) {
            return '<span class="text-muted">–</span>';
        }
        const s = MHDDNS_GW[status] || ['text-muted', status];
        return '<i class="fa fa-circle ' + s[0] + '" style="font-size:9px"></i> ' + mwEsc(s[1]);
    }
    function mwTime(ts) {
        return ts ? new Date(ts * 1000).toLocaleString() : '–';
    }
    function mwLegend() {
        return '<span class="mhddns-legend" title="' + "{{ lang._('Nur öffentliche Adressen werden geschrieben') }}" + '">' +
            "{{ lang._('Adressen:') }} " + ['public', 'private', 'cgnat', 'reserved'].map(function (c) {
                return mwClassBadge(c);
            }).join(' ') + '</span>';
    }
    function mwStat(id, num, label, colorClass) {
        $('#' + id).html('<span class="mhddns-stat-num">' + mwEsc(num) + '</span><span class="mhddns-stat-label">' +
            (colorClass ? '<i class="fa fa-circle ' + colorClass + '"></i>' : '') + mwEsc(label) + '</span>');
    }
    function mwRoutingInfo(target) {
        ajaxGet('/api/multihomeddns/service/status', {}, function (data) {
            if (!data) {
                return;
            }
            const item = function (ok, okText, badText, title) {
                return '<span' + (title ? ' title="' + mwEsc(title) + '"' : '') + '><i class="fa fa-fw ' +
                    (ok ? 'fa-check-circle text-success' : 'fa-exclamation-circle text-warning') + '"></i> ' +
                    mwEsc(ok ? okText : badText) + '</span>';
            };
            let html = item(data.enabled, "{{ lang._('Dienst aktiv') }}", "{{ lang._('Dienst deaktiviert (Einstellungen)') }}");
            html += item(data.policy_routing, "{{ lang._('Policy-Routing an') }}", "{{ lang._('Policy-Routing aus') }}");
            if (data.force_gw_disabled) {
                html += '<span title="' + mwEsc("{{ lang._('„Disable force gateway“ ist gesetzt. Die Prüfabfragen laufen über die eigenen route-to-Regeln des Plugins.') }}") +
                    '"><i class="fa fa-fw fa-info-circle text-info"></i> ' + "{{ lang._('„Disable force gateway“ gesetzt – abgedeckt') }}" + '</span>';
            }
            $(target).html('<div class="mhddns-flags">' + html + '</div>');
        });
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

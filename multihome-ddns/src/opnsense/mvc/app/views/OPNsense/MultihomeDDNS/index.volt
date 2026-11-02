{#
 # Multihome DynDNS - Interface-Eintraege
 # BSD 2-Clause License
 #}
{{ partial('OPNsense/MultihomeDDNS/common') }}

<script>
    $(document).ready(function () {
        function runAction(endpoint, $icon) {
            if ($icon && $icon.hasClass('fa-spin')) {
                return;
            }
            if ($icon) {
                $icon.addClass('fa-spin');
            }
            ajaxCall(endpoint, {}, function () {
                if ($icon) {
                    $icon.removeClass('fa-spin');
                }
                $('#grid-accounts').bootgrid('reload');
            });
        }

        function showTest(uuid, $icon) {
            $icon.removeClass('fa-flask').addClass('fa-spinner fa-pulse');
            ajaxCall('/api/multihomeddns/service/test/' + uuid, {}, function (data) {
                $icon.removeClass('fa-spinner fa-pulse').addClass('fa-flask');
                const r = (data && data.result) ? data.result : null;
                let html;
                if (!r) {
                    html = mwEsc((data && (data.error || data.message)) || "{{ lang._('Keine Antwort') }}");
                } else {
                    const rows = [
                        ["{{ lang._('Interface') }}", mwEsc(r.interface_descr) + ' (' + mwEsc(r.device) + '), ' + mwEsc(r.family)],
                        ["{{ lang._('Interface-Adresse') }}", r.local ? mwIp(r.local) + ' ' + mwClassBadge(r.local_class) : '–'],
                        ["{{ lang._('Methode') }}", mwEsc(r.method || '-') + (r.url ? ' – ' + mwEsc(r.url) : '')],
                        ["{{ lang._('Ermittelte Adresse') }}", r.ip ? mwIp(r.ip, true) + ' ' + mwClassBadge(r.ip_class) : '–'],
                        ["{{ lang._('Policy-Routing') }}", r.method === 'interface' ? "{{ lang._('nicht nötig (Interface-Adresse)') }}" :
                            (r.policy_rule ? mwBadge('label-success', "{{ lang._('aktiv') }}") + '<br/><code class="mhddns-rule">' + mwEsc(r.policy_rule) + '</code>'
                                : mwBadge('label-danger', "{{ lang._('keine Regel aktiv') }}") + ' <small>' + (r.policy_routing_enabled
                                    ? "{{ lang._('kein Gateway auf dem Interface gefunden oder Einstellungen nicht angewendet') }}"
                                    : "{{ lang._('in den Einstellungen deaktiviert') }}") + '</small>')],
                        ["{{ lang._('Gateway') }}", (r.gateway_chosen ? '<strong>' + mwEsc(r.gateway_chosen) + '</strong> <small class="text-muted">(' +
                            mwEsc(r.gateway_mode) + ')</small>' : '<span class="text-danger">' + "{{ lang._('kein Gateway auf diesem Interface – unter System › Gateways anlegen oder im Eintrag wählen') }}" + '</span>') +
                            ((r.gateways || []).length ? '<br/><small class="text-muted">' + "{{ lang._('Gateways auf dem Interface:') }}" + ' ' +
                                r.gateways.map(function (g) {
                                    return mwEsc(g.name) + (g.address ? ' ' + mwEsc(g.address) : '') + ' – ' + $('<div/>').html(mwGwStatus(g.status)).text().trim() +
                                        (g.disabled ? ' (' + "{{ lang._('deaktiviert') }}" + ')' : '');
                                }).join(', ') + '</small>' : '')],
                        ["{{ lang._('Disable force gateway') }}", r.force_gw_disabled ? "{{ lang._('gesetzt – wird durch die eigenen Regeln abgedeckt') }}" : "{{ lang._('nicht gesetzt') }}"]
                    ];
                    if (r.cgnat) {
                        rows.push(["{{ lang._('Hinweis') }}", mwBadge('label-warning', 'CGNAT') + ' ' + "{{ lang._('Anschluss hinter Carrier-Grade NAT – von außen über IPv4 nicht erreichbar.') }}"]);
                    } else if (r.behind_nat) {
                        rows.push(["{{ lang._('Hinweis') }}", "{{ lang._('Router/NAT vor der Firewall – ob dieser selbst hinter CGNAT hängt, ist von hier nicht erkennbar.') }}"]);
                    }
                    if (r.error) {
                        rows.push(["{{ lang._('Ergebnis') }}", '<span class="text-danger">' + mwEsc(r.error) + '</span>']);
                    } else {
                        rows.push(["{{ lang._('Ergebnis') }}", '<span class="text-success">' + "{{ lang._('würde geschrieben') }}" + '</span>']);
                    }
                    html = '<p><strong>' + mwEsc(data.description) + '</strong> → ' + mwEsc(data.service) + '</p><table class="table table-condensed mhddns-testtable">' +
                        '<colgroup><col style="width: 28%"/><col/></colgroup>' +
                        rows.map(function (row) { return '<tr><td>' + row[0] + '</td><td>' + row[1] + '</td></tr>'; }).join('') +
                        '</table><small class="text-muted">' + "{{ lang._('Test ohne Schreiben – Ergebnis steht auch im Log.') }}" + '</small>';
                }
                BootstrapDialog.show({
                    type: (r && !r.error) ? BootstrapDialog.TYPE_SUCCESS : BootstrapDialog.TYPE_WARNING,
                    size: BootstrapDialog.SIZE_WIDE,
                    title: "{{ lang._('Test der IP-Ermittlung') }}",
                    message: html,
                    buttons: [{label: "{{ lang._('Schließen') }}", action: function (d) { d.close(); }}]
                });
            });
        }

        $("#grid-accounts").UIBootgrid({
            search: '/api/multihomeddns/settings/searchAccount',
            get: '/api/multihomeddns/settings/getAccount/',
            set: '/api/multihomeddns/settings/setAccount/',
            add: '/api/multihomeddns/settings/addAccount/',
            del: '/api/multihomeddns/settings/delAccount/',
            toggle: '/api/multihomeddns/settings/toggleAccount/',
            options: {
                responseHandler: function (response) {
                    const count = {ok: 0, blocked: 0, error: 0, disabled: 0, cgnat: 0};
                    (response.rows || []).forEach(function (row) {
                        if (row.enabled !== '1') {
                            count.disabled++;
                        } else if (count[row.rt_status] !== undefined) {
                            count[row.rt_status]++;
                        }
                        if (row.enabled === '1' && row.rt_cgnat) {
                            count.cgnat++;
                        }
                    });
                    mwStat('stat_ok', count.ok, "{{ lang._('aktuell') }}", 'text-success');
                    mwStat('stat_blocked', count.blocked, "{{ lang._('blockiert') }}", 'text-warning');
                    mwStat('stat_error', count.error, "{{ lang._('Fehler') }}", 'text-danger');
                    mwStat('stat_cgnat', count.cgnat, "{{ lang._('hinter CGNAT') }}", 'text-warning');
                    mwStat('stat_disabled', count.disabled, "{{ lang._('deaktiviert') }}", 'text-muted');
                    return response;
                },
                formatters: {
                    entry: function (column, row) {
                        const sub = mwEsc(row.interface) + (row.rt_device ? ' (' + mwEsc(row.rt_device) + ')' : '') +
                            ' · ' + mwEsc(row.ipversion);
                        let html = '<strong>' + mwEsc(row.description) + '</strong>' + mwSub(sub);
                        if (row.rt_local) {
                            html += mwSub("{{ lang._('Interface:') }} " + mwIp(row.rt_local) + ' ' + mwClassBadge(row.rt_local_class));
                        }
                        return mwCell(html);
                    },
                    dns: function (column, row) {
                        return mwCell(mwEsc(row.service) + mwSub(mwEsc((row.hostnames || '').split(',').join(', '))));
                    },
                    publicip: function (column, row) {
                        if (!row.rt_detected) {
                            return mwCell('<span class="text-muted">–</span>');
                        }
                        const via = row.rt_method === 'interface' ? "{{ lang._('vom Interface') }}"
                            : (row.rt_url || '').replace(/^https?:\/\//, '').replace(/\/$/, '');
                        let sub = mwClassBadge(row.rt_ip_class) + mwEsc(via);
                        if (row.rt_written && row.rt_written !== row.rt_detected) {
                            sub += '<br/>' + "{{ lang._('im DNS:') }}" + ' ' + mwEsc(row.rt_written);
                        }
                        return mwCell(mwIp(row.rt_detected, true) + mwSub(sub));
                    },
                    state: function (column, row) {
                        let html = mwStatusBadge(row.enabled === '1' ? row.rt_status : 'disabled', row.rt_error);
                        if (row.enabled === '1' && row.rt_cgnat) {
                            html += mwBadge('label-warning', 'CGNAT', MHDDNS_CLASS['cgnat'][2]);
                        } else if (row.enabled === '1' && row.rt_behind_nat) {
                            html += mwBadge('label-default', "{{ lang._('hinter Router') }}",
                                "{{ lang._('Private Interface-Adresse: öffentliche IP wird über den Prüfdienst ermittelt') }}");
                        }
                        if (row.enabled === '1' && row.rt_error) {
                            html += mwMsg(row.rt_error, row.rt_status === 'blocked' ? 'warn' : 'err');
                        }
                        return mwCell(html);
                    },
                    checked: function (column, row) {
                        if (row.enabled !== '1') {
                            return mwCell('<span class="text-muted">' + "{{ lang._('alle') }} " + mwEsc(row.interval) + ' min</span>');
                        }
                        return mwCell(mwAgo(row.rt_checked) + ' <span class="text-muted">· ' + "{{ lang._('alle') }} " +
                            mwEsc(row.interval) + ' min</span>' + (row.rt_updated ? mwSub("{{ lang._('geschrieben') }} " +
                            mwAgo(row.rt_updated)) : mwSub("{{ lang._('noch nicht geschrieben') }}")));
                    }
                }
            },
            commands: {
                test_entry: {
                    method: function () {
                        showTest($(this).data('row-id'), $(this).find('span'));
                    },
                    classname: 'fa fa-fw fa-flask',
                    title: "{{ lang._('IP-Ermittlung testen (ohne Schreiben)') }}",
                    sequence: 40
                },
                force_entry: {
                    method: function () {
                        runAction('/api/multihomeddns/service/force/' + $(this).data('row-id'), $(this).find('span'));
                    },
                    filter: function (cell) {
                        return cell.getData().enabled === '1';
                    },
                    classname: 'fa fa-fw fa-refresh',
                    title: "{{ lang._('Force-Update: jetzt prüfen und beim Anbieter neu schreiben') }}",
                    sequence: 50
                },
                force_selected: {
                    method: function () {
                        const ids = $("#grid-accounts").bootgrid('getSelectedRows');
                        if (ids.length) {
                            runAction('/api/multihomeddns/service/force/' + ids.join(','), $(this).find('span'));
                        }
                    },
                    classname: 'fa fa-fw fa-refresh',
                    title: "{{ lang._('Force-Update für ausgewählte Einträge') }}",
                    footer: true,
                    sequence: 350
                }
            }
        });

        $("#mhddnsLegend").html(mwLegend());
        mwRoutingInfo('#mhddnsRouting');

        $("#account\\.checkip, #account\\.checkip_service").change(function () {
            const checkip = $("#account\\.checkip").val();
            const svc = $("#account\\.checkip_service").val();
            $("#account\\.checkip_service").closest('tr').toggle(checkip !== 'interface');
            $("#account\\.custom_url").closest('tr').toggle(checkip !== 'interface' && svc === 'custom');
            $("#account\\.force_ssl").closest('tr').toggle(checkip !== 'interface' && svc !== 'cloudflare_dns' && svc !== 'custom');
        });
        $("#account\\.service").change(function () {
            mwProviderFields('account');
        });
        $('#DialogAccount').on('shown.bs.modal', function () {
            $("#account\\.checkip").change();
            mwProviderFields('account');
        });

        $("#checkAll").click(function () {
            runAction('/api/multihomeddns/service/check', $(this).find('.fa'));
        });
        $("#forceAll").click(function () {
            runAction('/api/multihomeddns/service/force', $(this).find('.fa'));
        });

        $("#reconfigureAct").SimpleActionButton({
            onAction: function () {
                $("#mhddnsChangeMessage").hide();
                setTimeout(function () {
                    $('#grid-accounts').bootgrid('reload');
                    mwRoutingInfo('#mhddnsRouting');
                }, 4000);
            }
        });

        /* live status */
        setInterval(function () {
            if (!$('.modal.in').length) {
                $('#grid-accounts').bootgrid('reload');
            }
        }, 30000);
    });
</script>

<div class="content-box">
    <div class="mhddns-summary">
        <div class="mhddns-stat" id="stat_ok"></div>
        <div class="mhddns-stat" id="stat_blocked"></div>
        <div class="mhddns-stat" id="stat_error"></div>
        <div class="mhddns-stat" id="stat_cgnat"></div>
        <div class="mhddns-stat" id="stat_disabled"></div>
        <div class="mhddns-summary-info">
            <div id="mhddnsRouting"></div>
            <div id="mhddnsLegend"></div>
        </div>
    </div>
    <table id="grid-accounts" class="table table-condensed table-hover table-striped table-responsive"
           data-editDialog="DialogAccount" data-editAlert="mhddnsChangeMessage">
        <thead>
        <tr>
            <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">ID</th>
            <th data-column-id="enabled" data-width="6em" data-type="string" data-formatter="rowtoggle">{{ lang._('Aktiv') }}</th>
            <th data-column-id="description" data-type="string" data-formatter="entry">{{ lang._('Anschluss') }}</th>
            <th data-column-id="interface" data-type="string" data-visible="false">{{ lang._('Interface') }}</th>
            <th data-column-id="ipversion" data-type="string" data-visible="false">{{ lang._('IP-Version') }}</th>
            <th data-column-id="service" data-type="string" data-formatter="dns">{{ lang._('DNS') }}</th>
            <th data-column-id="hostnames" data-type="string" data-visible="false">{{ lang._('Hostnamen') }}</th>
            <th data-column-id="rt_detected" data-formatter="publicip" data-sortable="false">{{ lang._('Öffentliche IP') }}</th>
            <th data-column-id="rt_status" data-formatter="state" data-sortable="false">{{ lang._('Status') }}</th>
            <th data-column-id="rt_checked" data-formatter="checked" data-sortable="false" data-width="11em">{{ lang._('Geprüft') }}</th>
            <th data-column-id="commands" data-width="10.5em" data-formatter="commands" data-sortable="false">{{ lang._('Aktionen') }}</th>
        </tr>
        </thead>
        <tbody></tbody>
        <tfoot>
        <tr>
            <td></td>
            <td>
                <button data-action="add" type="button" class="btn btn-xs btn-primary"><span class="fa fa-fw fa-plus"></span></button>
                <button data-action="deleteSelected" type="button" class="btn btn-xs btn-default"><span class="fa fa-fw fa-trash-o"></span></button>
            </td>
        </tr>
        </tfoot>
    </table>
</div>

<div class="content-box" style="margin-top: 15px;">
    <div class="mhddns-actions">
        <div id="mhddnsChangeMessage" class="alert alert-info" style="display: none" role="alert">
            {{ lang._('Änderungen bitte mit „Anwenden“ übernehmen – lädt die Policy-Routing-Regeln und den Zeitplan neu.') }}
        </div>
        <button class="btn btn-primary" id="reconfigureAct"
                data-endpoint="/api/multihomeddns/service/reconfigure"
                data-label="{{ lang._('Anwenden') }}"
                data-error-title="{{ lang._('Fehler beim Anwenden') }}"
                type="button"></button>
        <span class="mhddns-spacer"></span>
        <button class="btn btn-default" id="checkAll" type="button" title="{{ lang._('Alle aktiven Einträge sofort prüfen, nur bei Änderung schreiben') }}">
            <i class="fa fa-search fa-fw"></i> {{ lang._('Alle jetzt prüfen') }}
        </button>
        <button class="btn btn-default" id="forceAll" type="button" title="{{ lang._('Alle aktiven Einträge prüfen und beim Anbieter neu schreiben') }}">
            <i class="fa fa-refresh fa-fw"></i> {{ lang._('Force-Update alle') }}
        </button>
    </div>
</div>

{{ partial("layout_partials/base_dialog",['fields':formDialogAccount,'id':'DialogAccount','label':lang._('Eintrag bearbeiten')]) }}

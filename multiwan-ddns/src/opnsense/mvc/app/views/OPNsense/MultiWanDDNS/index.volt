{#
 # Multi-WAN DynDNS - Interface-Eintraege
 # BSD 2-Clause License
 #}
{{ partial('OPNsense/MultiWanDDNS/common') }}

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
            ajaxCall('/api/multiwanddns/service/test/' + uuid, {}, function (data) {
                $icon.removeClass('fa-spinner fa-pulse').addClass('fa-flask');
                const r = (data && data.result) ? data.result : null;
                let html;
                if (!r) {
                    html = mwEsc((data && (data.error || data.message)) || "{{ lang._('Keine Antwort') }}");
                } else {
                    const rows = [
                        ["{{ lang._('Interface') }}", mwEsc(r.interface_descr) + ' (' + mwEsc(r.device) + '), ' + mwEsc(r.family)],
                        ["{{ lang._('Interface-Adresse') }}", r.local ? '<span class="mwddns-ip">' + mwEsc(r.local) + '</span> ' + mwClassBadge(r.local_class) : '-'],
                        ["{{ lang._('Methode') }}", mwEsc(r.method || '-') + (r.url ? ' – ' + mwEsc(r.url) : '')],
                        ["{{ lang._('Ermittelte Adresse') }}", r.ip ? '<strong class="mwddns-ip">' + mwEsc(r.ip) + '</strong> ' + mwClassBadge(r.ip_class) : '-'],
                        ["{{ lang._('Policy-Routing') }}", r.method === 'interface' ? "{{ lang._('nicht nötig (Interface-Adresse)') }}" :
                            (r.policy_rule ? mwBadge('label-success', "{{ lang._('aktiv') }}") + '<br/><small class="mwddns-ip">' + mwEsc(r.policy_rule) + '</small>'
                                : mwBadge('label-danger', "{{ lang._('keine Regel aktiv') }}") + ' <small>' + (r.policy_routing_enabled
                                    ? "{{ lang._('kein Gateway auf dem Interface gefunden oder Einstellungen nicht angewendet') }}"
                                    : "{{ lang._('in den Einstellungen deaktiviert') }}") + '</small>')],
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
                    html = '<p><strong>' + mwEsc(data.description) + '</strong> → ' + mwEsc(data.service) + '</p><table class="table table-condensed">' +
                        rows.map(function (row) { return '<tr><td style="width:30%">' + row[0] + '</td><td>' + row[1] + '</td></tr>'; }).join('') +
                        '</table><small class="text-muted">' + "{{ lang._('Test ohne Schreiben – Ergebnis steht auch im Log.') }}" + '</small>';
                }
                BootstrapDialog.show({
                    type: (r && !r.error) ? BootstrapDialog.TYPE_SUCCESS : BootstrapDialog.TYPE_WARNING,
                    title: "{{ lang._('Test der IP-Ermittlung') }}",
                    message: html,
                    buttons: [{label: "{{ lang._('Schließen') }}", action: function (d) { d.close(); }}]
                });
            });
        }

        $("#grid-accounts").UIBootgrid({
            search: '/api/multiwanddns/settings/searchAccount',
            get: '/api/multiwanddns/settings/getAccount/',
            set: '/api/multiwanddns/settings/setAccount/',
            add: '/api/multiwanddns/settings/addAccount/',
            del: '/api/multiwanddns/settings/delAccount/',
            toggle: '/api/multiwanddns/settings/toggleAccount/',
            options: {
                formatters: {
                    local: function (column, row) {
                        if (!row.rt_local) {
                            return '-';
                        }
                        return '<span class="mwddns-ip">' + mwEsc(row.rt_local) + '</span> ' + mwClassBadge(row.rt_local_class);
                    },
                    publicip: function (column, row) {
                        if (!row.rt_detected) {
                            return '-';
                        }
                        let html = '<span class="mwddns-ip"><strong>' + mwEsc(row.rt_detected) + '</strong></span> ' + mwClassBadge(row.rt_ip_class);
                        if (row.rt_cgnat) {
                            html += mwBadge('label-warning', 'CGNAT', MWDDNS_CLASS['cgnat'][2]);
                        }
                        if (row.rt_written && row.rt_written !== row.rt_detected) {
                            html += '<br/><small class="text-muted">' + "{{ lang._('im DNS:') }}" + ' ' + mwEsc(row.rt_written) + '</small>';
                        }
                        const via = row.rt_method === 'interface' ? "{{ lang._('Interface') }}" : (row.rt_url || '');
                        return html + (via ? '<br/><small class="text-muted">' + mwEsc(via) + '</small>' : '');
                    },
                    state: function (column, row) {
                        let html = mwStatusBadge(row.enabled === '1' ? row.rt_status : 'disabled', row.rt_error);
                        if (row.rt_cgnat) {
                            html += mwBadge('label-warning', "{{ lang._('CGNAT – nicht erreichbar') }}", MWDDNS_CLASS['cgnat'][2]);
                        }
                        if (row.rt_error) {
                            html += '<br/><small class="' + (row.rt_status === 'blocked' ? 'text-warning' : 'text-danger') + '">' + mwEsc(row.rt_error) + '</small>';
                        }
                        return html;
                    },
                    checked: function (column, row) {
                        return mwAgo(row.rt_checked) + (row.rt_updated ? '<br/><small class="text-muted">' +
                            "{{ lang._('geschrieben') }} " + mwAgo(row.rt_updated) + '</small>' : '');
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
                        runAction('/api/multiwanddns/service/force/' + $(this).data('row-id'), $(this).find('span'));
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
                            runAction('/api/multiwanddns/service/force/' + ids.join(','), $(this).find('span'));
                        }
                    },
                    classname: 'fa fa-fw fa-refresh',
                    title: "{{ lang._('Force-Update für ausgewählte Einträge') }}",
                    footer: true,
                    sequence: 350
                }
            }
        });

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
            runAction('/api/multiwanddns/service/check', $(this).find('.fa'));
        });
        $("#forceAll").click(function () {
            runAction('/api/multiwanddns/service/force', $(this).find('.fa'));
        });

        $("#reconfigureAct").SimpleActionButton({
            onAction: function () {
                $("#mwddnsChangeMessage").hide();
                setTimeout(function () { $('#grid-accounts').bootgrid('reload'); }, 4000);
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
    <table id="grid-accounts" class="table table-condensed table-hover table-striped table-responsive"
           data-editDialog="DialogAccount" data-editAlert="mwddnsChangeMessage">
        <thead>
        <tr>
            <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">ID</th>
            <th data-column-id="enabled" data-width="6em" data-type="string" data-formatter="rowtoggle">{{ lang._('Aktiv') }}</th>
            <th data-column-id="description" data-type="string">{{ lang._('Beschreibung') }}</th>
            <th data-column-id="interface" data-type="string">{{ lang._('Interface') }}</th>
            <th data-column-id="ipversion" data-type="string" data-width="5em">{{ lang._('IP') }}</th>
            <th data-column-id="service" data-type="string">{{ lang._('Anbieter') }}</th>
            <th data-column-id="hostnames" data-type="string">{{ lang._('Hostnamen') }}</th>
            <th data-column-id="rt_local" data-formatter="local" data-sortable="false">{{ lang._('Interface-Adresse') }}</th>
            <th data-column-id="rt_detected" data-formatter="publicip" data-sortable="false">{{ lang._('Öffentliche IP') }}</th>
            <th data-column-id="rt_status" data-formatter="state" data-sortable="false">{{ lang._('Status') }}</th>
            <th data-column-id="rt_checked" data-formatter="checked" data-sortable="false">{{ lang._('Geprüft') }}</th>
            <th data-column-id="commands" data-width="10em" data-formatter="commands" data-sortable="false">{{ lang._('Aktionen') }}</th>
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
    <div class="col-md-12 mwddns-legend">
        <small>
            <span class="label label-success">{{ lang._('öffentlich') }}</span>
            <span class="label label-danger">{{ lang._('privat') }}</span>{{ lang._('RFC 1918 / 4193') }} &nbsp;
            <span class="label label-warning">CGNAT</span>{{ lang._('RFC 6598') }} &nbsp;
            <span class="label label-danger">{{ lang._('reserviert') }}</span>{{ lang._('RFC 6890') }} &nbsp;–&nbsp;
            {{ lang._('Nur öffentliche Adressen werden geschrieben. Die Ansicht aktualisiert sich alle 30 Sekunden.') }}
        </small>
    </div>
</div>

<section class="page-content-main">
    <div class="content-box">
        <div class="col-md-12">
            <br/>
            <div id="mwddnsChangeMessage" class="alert alert-info" style="display: none" role="alert">
                {{ lang._('Änderungen bitte mit "Anwenden" übernehmen (lädt die Policy-Routing-Regeln und den Zeitplan neu).') }}
            </div>
            <button class="btn btn-primary" id="reconfigureAct"
                    data-endpoint="/api/multiwanddns/service/reconfigure"
                    data-label="{{ lang._('Anwenden') }}"
                    data-error-title="{{ lang._('Fehler beim Anwenden') }}"
                    type="button"></button>
            <button class="btn btn-default" id="checkAll" type="button"><i class="fa fa-search fa-fw"></i> {{ lang._('Alle jetzt prüfen') }}</button>
            <button class="btn btn-default" id="forceAll" type="button"><i class="fa fa-refresh fa-fw"></i> {{ lang._('Force-Update alle') }}</button>
            <br/><br/>
        </div>
    </div>
</section>

{{ partial("layout_partials/base_dialog",['fields':formDialogAccount,'id':'DialogAccount','label':lang._('Eintrag bearbeiten')]) }}

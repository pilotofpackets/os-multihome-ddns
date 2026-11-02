{#
 # Multihome DynDNS - Failover-DNS
 # BSD 2-Clause License
 #}
{{ partial('OPNsense/MultihomeDDNS/common') }}

<script>
    $(document).ready(function () {
        const STRATEGY = {
            'order': "{{ lang._('Reihenfolge') }}",
            'priority': "{{ lang._('Gateway-Priorität') }}",
            'latency': "{{ lang._('Latenz') }}"
        };
        let lastRows = {};

        function memberTable(members) {
            if (!members || !members.length) {
                return '<em>' + "{{ lang._('Noch nicht bewertet.') }}" + '</em>';
            }
            return '<table class="table table-condensed"><thead><tr><th>' + [
                "{{ lang._('Mitglied') }}", "{{ lang._('Gateway') }}", "{{ lang._('Status') }}", "{{ lang._('Verlust') }}",
                "{{ lang._('Latenz') }}", "{{ lang._('Prio') }}", "{{ lang._('Adresse') }}", "{{ lang._('Bewertung') }}"
            ].join('</th><th>') + '</th></tr></thead><tbody>' + members.map(function (m) {
                const nw = '<td style="white-space:nowrap">';
                return '<tr>' + nw + '<strong>' + mwEsc(m.name) + '</strong></td>' + nw + mwEsc(m.gateway || '–') + '</td>' + nw +
                    mwGwStatus(m.gw_status) + '</td>' + nw + (m.loss !== null ? m.loss + ' %' : '–') + '</td>' + nw +
                    (m.delay !== null ? m.delay + ' ms' : '–') + '</td><td>' + mwEsc(m.priority) + '</td>' + nw +
                    mwIp(m.ip) + '</td><td>' +
                    (m.ok ? mwBadge('label-success', "{{ lang._('verfügbar') }}")
                        : mwBadge('label-danger', "{{ lang._('nicht verfügbar') }}") + ' <small>' + mwEsc(m.reason) + '</small>') +
                    '</td></tr>';
            }).join('') + '</tbody></table>';
        }

        function historyTable(history) {
            if (!history || !history.length) {
                return '<em>' + "{{ lang._('Noch keine Umschaltung.') }}" + '</em>';
            }
            return '<table class="table table-condensed"><thead><tr><th>' + [
                "{{ lang._('Zeit') }}", "{{ lang._('Von') }}", "{{ lang._('Nach') }}", "{{ lang._('Adresse') }}", "{{ lang._('Grund') }}"
            ].join('</th><th>') + '</th></tr></thead><tbody>' + history.map(function (h) {
                return '<tr><td style="white-space:nowrap">' + mwTime(h.time) + '</td><td>' + mwEsc(h.from) + '</td><td><strong>' +
                    mwEsc(h.to) + '</strong></td><td>' + mwIp(h.ip) + '</td><td>' + mwEsc(h.reason) + '</td></tr>';
            }).join('') + '</tbody></table>';
        }

        function showDetails(uuid) {
            const row = lastRows[uuid] || {};
            BootstrapDialog.show({
                type: BootstrapDialog.TYPE_INFO,
                size: BootstrapDialog.SIZE_WIDE,
                title: "{{ lang._('Failover') }}: " + mwEsc(row.description || ''),
                message: '<p>' + "{{ lang._('Name') }}" + ': <strong>' + mwEsc((row.hostnames || '').split(',').join(', ')) + '</strong> → ' +
                    (row.rt_active ? mwEsc(row.rt_active) + ' (<span class="mhddns-ip">' + mwEsc(row.rt_active_ip) + '</span>)' : '-') +
                    (row.rt_error ? '<br/><span class="text-danger">' + mwEsc(row.rt_error) + '</span>' : '') + '</p>' +
                    '<h4>' + "{{ lang._('Mitglieder') }}" + '</h4>' + memberTable(row.rt_members) +
                    '<h4>' + "{{ lang._('Verlauf') }}" + '</h4>' + historyTable(row.rt_history),
                buttons: [{label: "{{ lang._('Schließen') }}", action: function (d) { d.close(); }}]
            });
        }

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
                $('#grid-failovers').bootgrid('reload');
            });
        }

        const FAILBACK = {
            'immediate': "{{ lang._('sofort zurück') }}",
            'delayed': "{{ lang._('verzögert zurück') }}",
            'manual': "{{ lang._('manuell zurück') }}"
        };

        $("#grid-failovers").UIBootgrid({
            search: '/api/multihomeddns/settings/searchFailover',
            get: '/api/multihomeddns/settings/getFailover/',
            set: '/api/multihomeddns/settings/setFailover/',
            add: '/api/multihomeddns/settings/addFailover/',
            del: '/api/multihomeddns/settings/delFailover/',
            toggle: '/api/multihomeddns/settings/toggleFailover/',
            options: {
                responseHandler: function (response) {
                    lastRows = {};
                    const count = {total: 0, ok: 0, degraded: 0, error: 0};
                    (response.rows || []).forEach(function (row) {
                        lastRows[row.uuid] = row;
                        if (row.enabled !== '1') {
                            return;
                        }
                        count.total++;
                        if (row.rt_status === 'error') {
                            count.error++;
                        } else if ((row.rt_members || []).some(function (m) { return !m.ok; })) {
                            count.degraded++;
                        } else if (row.rt_status === 'ok') {
                            count.ok++;
                        }
                    });
                    mwStat('stat_total', count.total, "{{ lang._('aktive Namen') }}", '');
                    mwStat('stat_ok', count.ok, "{{ lang._('alle Mitglieder da') }}", 'text-success');
                    mwStat('stat_degraded', count.degraded, "{{ lang._('Mitglied ausgefallen') }}", 'text-warning');
                    mwStat('stat_error', count.error, "{{ lang._('ohne Ziel') }}", 'text-danger');
                    return response;
                },
                formatters: {
                    failover: function (column, row) {
                        return mwCell('<strong>' + mwEsc(row.description) + '</strong>' +
                            mwSub(mwEsc((row.hostnames || '').split(',').join(', ')) + ' · ' + mwEsc(row.ipversion)));
                    },
                    dns: function (column, row) {
                        return mwCell(mwEsc(row.service) + mwSub(mwEsc(STRATEGY[row.strategy] || row.strategy) + ' · ' +
                            mwEsc(FAILBACK[row.failback] || row.failback)));
                    },
                    members: function (column, row) {
                        if (!row.rt_members || !row.rt_members.length) {
                            return mwCell(mwEsc((row.members || '').split(',').join(', ')) +
                                mwSub("{{ lang._('noch nicht bewertet') }}"));
                        }
                        return mwCell(row.rt_members.map(function (m, idx) {
                            const active = m.name === row.rt_active;
                            const dot = m.ok ? 'text-success' : 'text-danger';
                            return '<span class="mhddns-member" title="' + mwEsc(m.reason + (m.gateway ? ' – ' + m.gateway : '')) + '">' +
                                '<i class="fa fa-circle ' + dot + '"></i>' + (idx + 1) + '. ' +
                                (active ? '<strong>' + mwEsc(m.name) + '</strong><i class="fa fa-star" title="' +
                                    "{{ lang._('aktiv') }}" + '"></i>' : mwEsc(m.name)) + '</span>';
                        }).join(''));
                    },
                    active: function (column, row) {
                        if (!row.rt_active) {
                            return mwCell('<span class="text-muted">–</span>');
                        }
                        let sub = '';
                        if (row.rt_written && row.rt_written !== row.rt_active_ip) {
                            sub = mwSub('<span class="text-warning">' + "{{ lang._('im DNS:') }}" + ' ' + mwEsc(row.rt_written) + '</span>');
                        }
                        return mwCell(mwIp(row.rt_active_ip, true) + mwSub(mwEsc(row.rt_active)) + sub);
                    },
                    state: function (column, row) {
                        let html = mwStatusBadge(row.enabled === '1' ? row.rt_status : 'disabled', row.rt_error);
                        if (row.enabled === '1' && row.rt_error) {
                            html += mwMsg(row.rt_error, 'err');
                        }
                        return mwCell(html);
                    },
                    switched: function (column, row) {
                        const last = (row.rt_history || [])[0];
                        return mwCell(mwAgo(row.rt_switched) + (last ? mwSub(mwEsc(last.from) + ' → ' + mwEsc(last.to)) : ''));
                    }
                }
            },
            commands: {
                details: {
                    method: function () {
                        showDetails($(this).data('row-id'));
                    },
                    classname: 'fa fa-fw fa-info-circle',
                    title: "{{ lang._('Mitglieder und Verlauf') }}",
                    sequence: 30
                },
                reset: {
                    method: function () {
                        runAction('/api/multihomeddns/service/reset/' + $(this).data('row-id'), $(this).find('span'));
                    },
                    classname: 'fa fa-fw fa-undo',
                    title: "{{ lang._('Neu bewerten (z.B. manuell auf das bevorzugte Mitglied zurückschalten)') }}",
                    sequence: 40
                },
                force: {
                    method: function () {
                        runAction('/api/multihomeddns/service/force/' + $(this).data('row-id'), $(this).find('span'));
                    },
                    classname: 'fa fa-fw fa-refresh',
                    title: "{{ lang._('Force-Update: Adresse beim Anbieter neu schreiben') }}",
                    sequence: 50
                }
            }
        });

        mwRoutingInfo('#mhddnsRouting');
        $("#mhddnsHelpToggle").click(function (e) {
            e.preventDefault();
            $("#mhddnsHelp").slideToggle(150);
        });

        $("#failover\\.service").change(function () {
            mwProviderFields('failover');
        });
        $("#failover\\.failback").change(function () {
            $("#failover\\.failback_minutes").closest('tr').toggle($(this).val() === 'delayed');
        });
        $('#DialogFailover').on('shown.bs.modal', function () {
            mwProviderFields('failover');
            $("#failover\\.failback").change();
        });

        $("#reconfigureAct").SimpleActionButton({
            onAction: function () {
                $("#mhddnsChangeMessage").hide();
                setTimeout(function () { $('#grid-failovers').bootgrid('reload'); }, 4000);
            }
        });

        setInterval(function () {
            if (!$('.modal.in').length) {
                $('#grid-failovers').bootgrid('reload');
            }
        }, 30000);
    });
</script>

<div class="content-box">
    <div class="mhddns-summary">
        <div class="mhddns-stat" id="stat_total"></div>
        <div class="mhddns-stat" id="stat_ok"></div>
        <div class="mhddns-stat" id="stat_degraded"></div>
        <div class="mhddns-stat" id="stat_error"></div>
        <div class="mhddns-summary-info">
            <div id="mhddnsRouting"></div>
            <div><a href="#" id="mhddnsHelpToggle"><i class="fa fa-question-circle fa-fw"></i>{{ lang._('So funktioniert Failover-DNS') }}</a></div>
        </div>
    </div>
    <div class="mhddns-help" id="mhddnsHelp">
        {{ lang._('Ein Failover-Name (z.B. www.example.com) zeigt immer auf die Adresse eines verfügbaren Anschlusses. Die Namen der einzelnen Interface-Einträge bleiben fest und passen damit zu Reverse-DNS.') }}
        <ul>
            <li>{{ lang._('Ausfall: Gateway offline (dpinger), optional Paketverlust, Latenz oder eigene Schwellwerte – oder die IP-Ermittlung des Mitglieds schlägt fehl.') }}</li>
            <li>{{ lang._('Bewertung sofort bei Gateway-Alarmen und zusätzlich jede Minute.') }}</li>
            <li>{{ lang._('Zurückschalten sofort, verzögert nach stabiler Zeit oder nur manuell (Knopf „Neu bewerten“).') }}</li>
        </ul>
    </div>
    <table id="grid-failovers" class="table table-condensed table-hover table-striped table-responsive"
           data-editDialog="DialogFailover" data-editAlert="mhddnsChangeMessage">
        <thead>
        <tr>
            <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">ID</th>
            <th data-column-id="enabled" data-width="6em" data-type="string" data-formatter="rowtoggle">{{ lang._('Aktiv') }}</th>
            <th data-column-id="description" data-type="string" data-formatter="failover">{{ lang._('Name') }}</th>
            <th data-column-id="service" data-type="string" data-formatter="dns">{{ lang._('DNS') }}</th>
            <th data-column-id="members" data-formatter="members" data-sortable="false" data-width="15em">{{ lang._('Mitglieder') }}</th>
            <th data-column-id="rt_active" data-formatter="active" data-sortable="false">{{ lang._('Zeigt auf') }}</th>
            <th data-column-id="rt_status" data-formatter="state" data-sortable="false">{{ lang._('Status') }}</th>
            <th data-column-id="rt_switched" data-formatter="switched" data-sortable="false">{{ lang._('Wechsel') }}</th>
            <th data-column-id="commands" data-width="13em" data-formatter="commands" data-sortable="false">{{ lang._('Aktionen') }}</th>
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
            {{ lang._('Änderungen bitte mit „Anwenden“ übernehmen.') }}
        </div>
        <button class="btn btn-primary" id="reconfigureAct"
                data-endpoint="/api/multihomeddns/service/reconfigure"
                data-label="{{ lang._('Anwenden') }}"
                data-error-title="{{ lang._('Fehler beim Anwenden') }}"
                type="button"></button>
    </div>
</div>

{{ partial("layout_partials/base_dialog",['fields':formDialogFailover,'id':'DialogFailover','label':lang._('Failover bearbeiten')]) }}

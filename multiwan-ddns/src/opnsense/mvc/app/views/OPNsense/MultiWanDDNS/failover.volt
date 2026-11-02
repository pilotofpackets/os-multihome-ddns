{#
 # Multi-WAN DynDNS - Failover-DNS
 # BSD 2-Clause License
 #}
{{ partial('OPNsense/MultiWanDDNS/common') }}

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
                return '<tr><td>' + mwEsc(m.name) + '</td><td>' + mwEsc(m.gateway || '-') + '</td><td>' +
                    mwEsc(m.gw_status || '-') + '</td><td>' + (m.loss !== null ? m.loss + ' %' : '-') + '</td><td>' +
                    (m.delay !== null ? m.delay + ' ms' : '-') + '</td><td>' + mwEsc(m.priority) + '</td><td class="mwddns-ip">' +
                    mwEsc(m.ip || '-') + '</td><td>' +
                    (m.ok ? mwBadge('label-success', "{{ lang._('verfügbar') }}") : mwBadge('label-danger', "{{ lang._('nicht verfügbar') }}")) +
                    ' <small>' + mwEsc(m.reason) + '</small></td></tr>';
            }).join('') + '</tbody></table>';
        }

        function historyTable(history) {
            if (!history || !history.length) {
                return '<em>' + "{{ lang._('Noch keine Umschaltung.') }}" + '</em>';
            }
            return '<table class="table table-condensed"><thead><tr><th>' + [
                "{{ lang._('Zeit') }}", "{{ lang._('Von') }}", "{{ lang._('Nach') }}", "{{ lang._('Adresse') }}", "{{ lang._('Grund') }}"
            ].join('</th><th>') + '</th></tr></thead><tbody>' + history.map(function (h) {
                return '<tr><td>' + mwTime(h.time) + '</td><td>' + mwEsc(h.from) + '</td><td><strong>' + mwEsc(h.to) +
                    '</strong></td><td class="mwddns-ip">' + mwEsc(h.ip) + '</td><td>' + mwEsc(h.reason) + '</td></tr>';
            }).join('') + '</tbody></table>';
        }

        function showDetails(uuid) {
            const row = lastRows[uuid] || {};
            BootstrapDialog.show({
                type: BootstrapDialog.TYPE_INFO,
                size: BootstrapDialog.SIZE_WIDE,
                title: "{{ lang._('Failover') }}: " + mwEsc(row.description || ''),
                message: '<p>' + "{{ lang._('Name') }}" + ': <strong>' + mwEsc(row.hostnames) + '</strong> → ' +
                    (row.rt_active ? mwEsc(row.rt_active) + ' (<span class="mwddns-ip">' + mwEsc(row.rt_active_ip) + '</span>)' : '-') +
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

        $("#grid-failovers").UIBootgrid({
            search: '/api/multiwanddns/settings/searchFailover',
            get: '/api/multiwanddns/settings/getFailover/',
            set: '/api/multiwanddns/settings/setFailover/',
            add: '/api/multiwanddns/settings/addFailover/',
            del: '/api/multiwanddns/settings/delFailover/',
            toggle: '/api/multiwanddns/settings/toggleFailover/',
            options: {
                responseHandler: function (response) {
                    lastRows = {};
                    (response.rows || []).forEach(function (row) { lastRows[row.uuid] = row; });
                    return response;
                },
                formatters: {
                    strategy: function (column, row) {
                        return mwEsc(STRATEGY[row.strategy] || row.strategy);
                    },
                    active: function (column, row) {
                        if (!row.rt_active) {
                            return '-';
                        }
                        let html = '<strong>' + mwEsc(row.rt_active) + '</strong><br/><span class="mwddns-ip">' + mwEsc(row.rt_active_ip) + '</span>';
                        if (row.rt_written && row.rt_written !== row.rt_active_ip) {
                            html += '<br/><small class="text-warning">' + "{{ lang._('im DNS:') }}" + ' ' + mwEsc(row.rt_written) + '</small>';
                        }
                        return html;
                    },
                    members: function (column, row) {
                        if (!row.rt_members || !row.rt_members.length) {
                            return mwEsc(row.members);
                        }
                        return row.rt_members.map(function (m) {
                            const active = m.name === row.rt_active;
                            return mwBadge(m.ok ? (active ? 'label-primary' : 'label-success') : 'label-danger',
                                (active ? '★ ' : '') + m.name, m.reason + (m.gateway ? ' (' + m.gateway + ')' : ''));
                        }).join(' ');
                    },
                    state: function (column, row) {
                        let html = mwStatusBadge(row.enabled === '1' ? row.rt_status : 'disabled', row.rt_error);
                        if (row.rt_error) {
                            html += '<br/><small class="text-danger">' + mwEsc(row.rt_error) + '</small>';
                        }
                        return html;
                    },
                    switched: function (column, row) {
                        return mwAgo(row.rt_switched);
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
                        runAction('/api/multiwanddns/service/reset/' + $(this).data('row-id'), $(this).find('span'));
                    },
                    classname: 'fa fa-fw fa-undo',
                    title: "{{ lang._('Neu bewerten (z.B. manuell auf das bevorzugte Mitglied zurückschalten)') }}",
                    sequence: 40
                },
                force: {
                    method: function () {
                        runAction('/api/multiwanddns/service/force/' + $(this).data('row-id'), $(this).find('span'));
                    },
                    classname: 'fa fa-fw fa-refresh',
                    title: "{{ lang._('Force-Update: Adresse beim Anbieter neu schreiben') }}",
                    sequence: 50
                }
            }
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
                $("#mwddnsChangeMessage").hide();
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
    <div class="col-md-12">
        <p style="margin-top:10px">
            {{ lang._('Ein Failover-Name (z.B. www.example.com) zeigt immer auf die Adresse eines verfügbaren Anschlusses. Die Namen der einzelnen Interface-Einträge bleiben fest – passend zu Reverse-DNS. Ausfälle werden über den Gateway-Status (dpinger) erkannt und sofort bei Gateway-Alarmen sowie minütlich ausgewertet.') }}
        </p>
    </div>
    <table id="grid-failovers" class="table table-condensed table-hover table-striped table-responsive"
           data-editDialog="DialogFailover" data-editAlert="mwddnsChangeMessage">
        <thead>
        <tr>
            <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">ID</th>
            <th data-column-id="enabled" data-width="6em" data-type="string" data-formatter="rowtoggle">{{ lang._('Aktiv') }}</th>
            <th data-column-id="description" data-type="string">{{ lang._('Beschreibung') }}</th>
            <th data-column-id="hostnames" data-type="string">{{ lang._('Hostnamen') }}</th>
            <th data-column-id="service" data-type="string">{{ lang._('Anbieter') }}</th>
            <th data-column-id="strategy" data-formatter="strategy" data-type="string">{{ lang._('Auswahl') }}</th>
            <th data-column-id="members" data-formatter="members" data-sortable="false">{{ lang._('Mitglieder') }}</th>
            <th data-column-id="rt_active" data-formatter="active" data-sortable="false">{{ lang._('Aktiv auf') }}</th>
            <th data-column-id="rt_status" data-formatter="state" data-sortable="false">{{ lang._('Status') }}</th>
            <th data-column-id="rt_switched" data-formatter="switched" data-sortable="false">{{ lang._('Letzter Wechsel') }}</th>
            <th data-column-id="commands" data-width="11em" data-formatter="commands" data-sortable="false">{{ lang._('Aktionen') }}</th>
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
            <span class="label label-primary">★</span>{{ lang._('aktiv') }} &nbsp;
            <span class="label label-success">&nbsp;</span>{{ lang._('verfügbar') }} &nbsp;
            <span class="label label-danger">&nbsp;</span>{{ lang._('nicht verfügbar (Maus über den Namen zeigt den Grund)') }}
        </small>
    </div>
</div>

<section class="page-content-main">
    <div class="content-box">
        <div class="col-md-12">
            <br/>
            <div id="mwddnsChangeMessage" class="alert alert-info" style="display: none" role="alert">
                {{ lang._('Änderungen bitte mit "Anwenden" übernehmen.') }}
            </div>
            <button class="btn btn-primary" id="reconfigureAct"
                    data-endpoint="/api/multiwanddns/service/reconfigure"
                    data-label="{{ lang._('Anwenden') }}"
                    data-error-title="{{ lang._('Fehler beim Anwenden') }}"
                    type="button"></button>
            <br/><br/>
        </div>
    </div>
</section>

{{ partial("layout_partials/base_dialog",['fields':formDialogFailover,'id':'DialogFailover','label':lang._('Failover bearbeiten')]) }}

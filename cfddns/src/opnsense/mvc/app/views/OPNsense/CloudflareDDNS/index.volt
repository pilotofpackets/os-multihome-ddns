{#
 # Cloudflare DDNS (per interface) for OPNsense
 # BSD 2-Clause License
 #}

<script>
    $(document).ready(function () {
        function esc(value) {
            return $('<div/>').text(value === null || value === undefined ? '' : String(value)).html();
        }
        function fmtTime(ts) {
            return ts ? new Date(ts * 1000).toLocaleString() : '-';
        }

        /* accounts grid */
        $("#grid-accounts").UIBootgrid({
            search: '/api/cloudflareddns/settings/searchAccount',
            get: '/api/cloudflareddns/settings/getAccount/',
            set: '/api/cloudflareddns/settings/setAccount/',
            add: '/api/cloudflareddns/settings/addAccount/',
            del: '/api/cloudflareddns/settings/delAccount/',
            toggle: '/api/cloudflareddns/settings/toggleAccount/'
        });

        /* show only the fields that matter for the selected check method / service / ip version */
        function updateDialogFields() {
            const checkip = $("#account\\.checkip").val();
            const service = $("#account\\.service").val();
            const ipversion = $("#account\\.ipversion").val();
            const web = checkip !== 'interface';
            $("#account\\.service").closest("tr").toggle(web);
            $("#account\\.custom_url4").closest("tr").toggle(web && service === 'custom' && ipversion !== 'v6');
            $("#account\\.custom_url6").closest("tr").toggle(web && service === 'custom' && ipversion !== 'v4');
            $("#account\\.ttl").closest("tr").toggle(!$("#account\\.proxied").is(':checked'));
        }
        $("#account\\.checkip, #account\\.service, #account\\.ipversion, #account\\.proxied").change(updateDialogFields);
        $('#DialogAccount').on('shown.bs.modal', updateDialogFields);

        /* general settings */
        mapDataToFormUI({'frm_general': "/api/cloudflareddns/settings/get"}).done(function () {
            formatTokenizersUI();
            $('.selectpicker').selectpicker('refresh');
        });

        /* status */
        function loadStatus() {
            ajaxGet('/api/cloudflareddns/service/status', {}, function (data) {
                const $body = $("#grid-status > tbody").empty();
                const rows = (data && data.rows) ? data.rows : [];
                if (data && data.enabled === false) {
                    $("#status-disabled").show();
                } else {
                    $("#status-disabled").hide();
                }
                if (rows.length === 0) {
                    $body.append('<tr><td colspan="9">{{ lang._("Noch keine Einträge.") }}</td></tr>');
                }
                rows.forEach(function (row) {
                    let state;
                    if (!row.enabled) {
                        state = '<span class="text-muted">{{ lang._("deaktiviert") }}</span>';
                    } else if (row.error) {
                        state = '<span class="text-danger"><i class="fa fa-exclamation-triangle"></i> ' + esc(row.error) + '</span>';
                    } else if (row.ip) {
                        const recs = Object.keys(row.records || {}).map(function (name) {
                            return esc(name) + ' (' + esc(row.records[name]) + ')';
                        });
                        state = '<span class="text-success"><i class="fa fa-check"></i> OK</span>' +
                            (recs.length ? '<br/><small>' + recs.join('<br/>') + '</small>' : '');
                    } else {
                        state = '<span class="text-muted">{{ lang._("noch nicht geprüft") }}</span>';
                    }
                    const source = row.method === 'interface' ? '{{ lang._("Interface") }}'
                        : (row.url ? esc(row.url) : '-');
                    $body.append(
                        '<tr>' +
                        '<td>' + esc(row.description || row.hostnames) + '</td>' +
                        '<td>' + esc(row.interface) + ' <small class="text-muted">(' + esc(row.device) + ')</small></td>' +
                        '<td>' + esc(row.family) + '</td>' +
                        '<td>' + esc(row.local || '-') + '</td>' +
                        '<td><strong>' + esc(row.ip || '-') + '</strong><br/><small class="text-muted">' + source + '</small></td>' +
                        '<td>' + fmtTime(row.checked) + '</td>' +
                        '<td>' + fmtTime(row.updated) + '</td>' +
                        '<td>' + state + '</td>' +
                        '<td><button type="button" class="btn btn-xs btn-default test-entry" data-uuid="' + esc(row.uuid) +
                        '" title="{{ lang._("IP-Ermittlung testen (ohne Update)") }}"><span class="fa fa-fw fa-flask"></span></button></td>' +
                        '</tr>'
                    );
                });
            });
        }

        $(document).on('click', '.test-entry', function () {
            const $btn = $(this);
            const $icon = $btn.find('span').removeClass('fa-flask').addClass('fa-spinner fa-pulse');
            ajaxCall('/api/cloudflareddns/service/test/' + $btn.data('uuid'), {}, function (data) {
                $icon.removeClass('fa-spinner fa-pulse').addClass('fa-flask');
                let html = '';
                if (data && data.results) {
                    html += '<p><strong>' + esc(data.description) + '</strong></p>';
                    html += '<table class="table table-condensed">';
                    data.results.forEach(function (r) {
                        html += '<tr><th colspan="2">' + esc(r.family) + '</th></tr>' +
                            '<tr><td>{{ lang._("Interface") }}</td><td>' + esc(r.interface_descr) + ' (' + esc(r.device) + ')</td></tr>' +
                            '<tr><td>{{ lang._("Quelladresse") }}</td><td>' + esc(r.local || '-') + '</td></tr>' +
                            '<tr><td>{{ lang._("Methode") }}</td><td>' + esc(r.method || '-') + (r.url ? ' – ' + esc(r.url) : '') + '</td></tr>' +
                            '<tr><td>{{ lang._("Ermittelte IP") }}</td><td><strong>' + esc(r.ip || '-') + '</strong></td></tr>' +
                            (r.error ? '<tr><td>{{ lang._("Fehler") }}</td><td class="text-danger">' + esc(r.error) + '</td></tr>' : '');
                    });
                    html += '</table>';
                } else {
                    html = esc((data && (data.error || data.message)) || '{{ lang._("Keine Antwort") }}');
                }
                BootstrapDialog.show({
                    type: BootstrapDialog.TYPE_INFO,
                    title: "{{ lang._('Test der IP-Ermittlung') }}",
                    message: html,
                    buttons: [{label: "{{ lang._('Schließen') }}", action: function (d) { d.close(); }}]
                });
            });
        });

        function runAction(endpoint, $btn) {
            const $icon = $btn.find('.fa-spinner').show();
            ajaxCall(endpoint, {}, function () {
                $icon.hide();
                loadStatus();
            });
        }
        $("#checkAct").click(function () { runAction('/api/cloudflareddns/service/check', $(this)); });
        $("#forceAct").click(function () { runAction('/api/cloudflareddns/service/force', $(this)); });
        $("#refreshStatus").click(loadStatus);
        $('a[href="#tab_status"]').on('shown.bs.tab', loadStatus);

        /* apply: save general settings, reload firewall rules + cron, run a check */
        $("#reconfigureAct").SimpleActionButton({
            onPreAction: function () {
                const dfObj = new $.Deferred();
                saveFormToEndpoint("/api/cloudflareddns/settings/set", 'frm_general', function () {
                    dfObj.resolve();
                });
                return dfObj;
            },
            onAction: function () {
                $("#cfddnsChangeMessage").hide();
                setTimeout(loadStatus, 3000);
            }
        });

        loadStatus();
    });
</script>

<ul class="nav nav-tabs" data-tabs="tabs" id="maintabs">
    <li class="active"><a data-toggle="tab" href="#tab_accounts">{{ lang._('Einträge') }}</a></li>
    <li><a data-toggle="tab" href="#tab_status">{{ lang._('Status') }}</a></li>
    <li><a data-toggle="tab" href="#tab_general">{{ lang._('Allgemein') }}</a></li>
</ul>
<div class="tab-content content-box">
    <div id="tab_accounts" class="tab-pane fade in active">
        <table id="grid-accounts" class="table table-condensed table-hover table-striped table-responsive"
               data-editDialog="DialogAccount" data-editAlert="cfddnsChangeMessage">
            <thead>
            <tr>
                <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">ID</th>
                <th data-column-id="enabled" data-width="6em" data-type="string" data-formatter="rowtoggle">{{ lang._('Aktiv') }}</th>
                <th data-column-id="description" data-type="string">{{ lang._('Beschreibung') }}</th>
                <th data-column-id="interface" data-type="string">{{ lang._('Interface') }}</th>
                <th data-column-id="ipversion" data-type="string">{{ lang._('IP-Version') }}</th>
                <th data-column-id="checkip" data-type="string">{{ lang._('Ermittlung') }}</th>
                <th data-column-id="zone" data-type="string">{{ lang._('Zone') }}</th>
                <th data-column-id="hostnames" data-type="string">{{ lang._('Hostnamen') }}</th>
                <th data-column-id="commands" data-width="7em" data-formatter="commands" data-sortable="false">{{ lang._('Aktionen') }}</th>
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
    <div id="tab_status" class="tab-pane fade in">
        <div class="col-md-12">
            <div id="status-disabled" class="alert alert-warning" style="display:none; margin-top:10px">
                {{ lang._('Der Dienst ist deaktiviert (Reiter "Allgemein").') }}
            </div>
            <table id="grid-status" class="table table-condensed table-striped">
                <thead>
                <tr>
                    <th>{{ lang._('Eintrag') }}</th>
                    <th>{{ lang._('Interface') }}</th>
                    <th>{{ lang._('Familie') }}</th>
                    <th>{{ lang._('Interface-Adresse') }}</th>
                    <th>{{ lang._('Öffentliche IP') }}</th>
                    <th>{{ lang._('Geprüft') }}</th>
                    <th>{{ lang._('Aktualisiert') }}</th>
                    <th>{{ lang._('Status') }}</th>
                    <th></th>
                </tr>
                </thead>
                <tbody></tbody>
            </table>
            <button class="btn btn-default" id="refreshStatus" type="button"><span class="fa fa-refresh"></span> {{ lang._('Aktualisieren') }}</button>
            <button class="btn btn-primary" id="checkAct" type="button">{{ lang._('Jetzt prüfen') }} <i class="fa fa-spinner fa-pulse" style="display:none"></i></button>
            <button class="btn btn-default" id="forceAct" type="button">{{ lang._('Abgleich erzwingen') }} <i class="fa fa-spinner fa-pulse" style="display:none"></i></button>
            <br/><br/>
        </div>
    </div>
    <div id="tab_general" class="tab-pane fade in">
        {{ partial("layout_partials/base_form",['fields':formGeneral,'id':'frm_general']) }}
    </div>
</div>

<section class="page-content-main">
    <div class="content-box">
        <div class="col-md-12">
            <br/>
            <div id="cfddnsChangeMessage" class="alert alert-info" style="display: none" role="alert">
                {{ lang._('Änderungen bitte mit "Anwenden" übernehmen (lädt die Firewall-Regeln für das Policy-Routing neu).') }}
            </div>
            <button class="btn btn-primary" id="reconfigureAct"
                    data-endpoint="/api/cloudflareddns/service/reconfigure"
                    data-label="{{ lang._('Anwenden') }}"
                    data-error-title="{{ lang._('Fehler beim Anwenden') }}"
                    type="button"></button>
            <br/><br/>
        </div>
    </div>
</section>

{{ partial("layout_partials/base_dialog",['fields':formDialogAccount,'id':'DialogAccount','label':lang._('Eintrag bearbeiten')]) }}

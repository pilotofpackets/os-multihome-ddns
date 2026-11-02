{#
 # Multi-WAN DynDNS - Einstellungen
 # BSD 2-Clause License
 #}
<script>
    $(document).ready(function () {
        mapDataToFormUI({'frm_general': "/api/multiwanddns/settings/get"}).done(function () {
            formatTokenizersUI();
            $('.selectpicker').selectpicker('refresh');
        });
        ajaxGet('/api/multiwanddns/service/status', {}, function (data) {
            if (data && data.force_gw_disabled) {
                $("#forceGwInfo").show();
            }
        });
        $("#reconfigureAct").SimpleActionButton({
            onPreAction: function () {
                const dfObj = new $.Deferred();
                saveFormToEndpoint("/api/multiwanddns/settings/set", 'frm_general', function () {
                    dfObj.resolve();
                });
                return dfObj;
            }
        });
    });
</script>

<div class="content-box">
    <div id="forceGwInfo" class="alert alert-info" style="display:none; margin: 10px">
        {{ lang._('"Disable force gateway" ist gesetzt. Das ist in Ordnung: die Prüfabfragen dieses Plugins werden über eigene route-to-Regeln pro Interface geroutet (Option "Policy-Routing für Prüfabfragen").') }}
    </div>
    {{ partial("layout_partials/base_form",['fields':formGeneral,'id':'frm_general']) }}
</div>

<section class="page-content-main">
    <div class="content-box">
        <div class="col-md-12">
            <br/>
            <button class="btn btn-primary" id="reconfigureAct"
                    data-endpoint="/api/multiwanddns/service/reconfigure"
                    data-label="{{ lang._('Speichern und anwenden') }}"
                    data-error-title="{{ lang._('Fehler beim Anwenden') }}"
                    type="button"></button>
            <br/><br/>
        </div>
    </div>
</section>

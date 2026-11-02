{#
 # Multihome DynDNS - Einstellungen
 # BSD 2-Clause License
 #}
{{ partial('OPNsense/MultihomeDDNS/common') }}

<script>
    $(document).ready(function () {
        mapDataToFormUI({'frm_general': "/api/multihomeddns/settings/get"}).done(function () {
            formatTokenizersUI();
            $('.selectpicker').selectpicker('refresh');
        });
        mwRoutingInfo('#mhddnsRouting');
        $("#reconfigureAct").SimpleActionButton({
            onPreAction: function () {
                const dfObj = new $.Deferred();
                saveFormToEndpoint("/api/multihomeddns/settings/set", 'frm_general', function () {
                    dfObj.resolve();
                });
                return dfObj;
            },
            onAction: function () {
                setTimeout(function () { mwRoutingInfo('#mhddnsRouting'); }, 2000);
            }
        });
    });
</script>

<div class="content-box">
    <div class="mhddns-summary">
        <div class="mhddns-summary-info" style="text-align: left;">
            <div id="mhddnsRouting"></div>
        </div>
    </div>
    {{ partial("layout_partials/base_form",['fields':formGeneral,'id':'frm_general']) }}
</div>

<div class="content-box" style="margin-top: 15px;">
    <div class="mhddns-actions">
        <button class="btn btn-primary" id="reconfigureAct"
                data-endpoint="/api/multihomeddns/service/reconfigure"
                data-label="{{ lang._('Speichern und anwenden') }}"
                data-error-title="{{ lang._('Fehler beim Anwenden') }}"
                type="button"></button>
    </div>
</div>

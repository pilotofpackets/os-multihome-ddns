<?php
/*
 * Renders the plugin's firewall + NAT rules with the REAL rule classes of OPNsense core
 * (Plugin, Rule, FilterRule, SNatRule, Util) and checks the generated pf syntax.
 * usage: CORE=/path/to/opnsense-core CFG=tests/fixtures/hook_config.xml INC=.../multihomeddns.inc php tests/test_real_rules.php
 */
namespace OPNsense\Core {
    class Config {
        private static $i;
        public static function getInstance() { return self::$i ??= new self(); }
        public function object() { return simplexml_load_string(file_get_contents(getenv('CFG'))); }
    }
}
namespace OPNsense\Base\FieldTypes {
    class PortField { public static function getWellKnown($v) { return ['http' => [80], 'https' => [443], 'domain' => [53]][$v] ?? []; } }
}
namespace OPNsense\Firewall {
    class AliasItems { public function iterateItems() { return []; } }
    class Alias {
        public $aliases;
        public function __construct($a = false) { $this->aliases = new \stdClass(); $this->aliases->alias = new AliasItems(); }
        public function __call($n, $a) { return null; }
        public static function __callStatic($n, $a) { return null; }
    }
}
namespace OPNsense\Routing {
    class Gateways {
        public function getInterfaceGateway($if, $inet, $only, $prop) { return ['wan' => ['inet' => 'WAN_PPPOE'], 'opt1' => ['inet' => 'DSL2_GW']][$if][$inet] ?? null; }
        public function gatewaysIndexedByName($a = false, $b = false, $c = false) {
            return ['DSL3_GW' => ['interface' => 'opt2', 'ipprotocol' => 'inet', 'priority' => 10],
                    'DSL2_ALT' => ['interface' => 'opt1', 'ipprotocol' => 'inet', 'priority' => 5]];
        }
    }
}
namespace {
    $lib = getenv('CORE') . '/src/opnsense/mvc/app/library/OPNsense/Firewall/';
    foreach (['Util', 'Rule', 'FilterRule', 'SNatRule', 'Plugin'] as $cls) {
        require_once $lib . $cls . '.php';
    }
    function mwexec($c) {}
    require getenv('INC');

    $fw = new \OPNsense\Firewall\Plugin();
    $map = [
        'wan' => ['if' => 'pppoe0', 'descr' => 'DSL1', 'gateway' => 'WAN_PPPOE'],
        'opt1' => ['if' => 'igb1', 'descr' => 'DSL2'],
        'opt2' => ['if' => 'igc2', 'descr' => 'ETH3_TelekomPriv'],
        'opt3' => ['if' => 'igc3', 'descr' => 'Mobilfunk_Backup', 'gateway' => 'LTE_GW'],
    ];
    $fw->setInterfaceMapping($map);
    // gateway mapping as Plugin::setGateways() builds it (route-to logic per gateway)
    $ref = new \ReflectionProperty($fw, 'gatewayMapping');
    $ref->setAccessible(true);
    $ref->setValue($fw, [
        'WAN_PPPOE' => ['interface' => 'pppoe0', 'proto' => 'inet', 'type' => 'gateway', 'logic' => 'route-to ( pppoe0 62.155.1.1 )'],
        'DSL2_ALT' => ['interface' => 'igb1', 'proto' => 'inet', 'type' => 'gateway', 'logic' => 'route-to ( igb1 192.168.178.2 )'],
        'DSL3_GW' => ['interface' => 'igc2', 'proto' => 'inet', 'type' => 'gateway', 'logic' => 'route-to ( igc2 192.168.10.250 )'],
    ]);
    $gw = new \ReflectionProperty($fw, 'gateways');
    $gw->setAccessible(true);
    $gw->setValue($fw, new \OPNsense\Routing\Gateways());

    multihomeddns_firewall($fw);
    $filter = $fw->outputFilterRules();
    $nat = $fw->outputNatRules();
    echo $filter, $nat;

    $fail = 0;
    $need = [
        'pass out quick route-to ( igc2 192.168.10.250 ) inet proto tcp from {(igc2)} to {!(igc2:network)} port {443} keep state',
        'pass out quick route-to ( igc2 192.168.10.250 ) inet proto tcp from {(igc2)} to {!(igc2:network)} port {80} keep state',
        'pass out quick route-to ( igc2 192.168.10.250 ) inet proto udp from {(igc2)} to {!(igc2:network)} port {53} keep state',
        'pass out quick route-to ( igb1 192.168.178.2 ) inet proto tcp from {(igb1)}',
        'no nat on igc3 inet proto tcp from (igc2) to any port 443',
        'no nat on igc3 inet proto udp from (igc2) to any port 53',
        'no nat on pppoe0 inet proto tcp from (igc2) to any port 80',
    ];
    $flat = preg_replace('/\s+/', ' ', $filter . "\n" . $nat);
    foreach ($need as $line) {
        if (strpos($flat, preg_replace('/\s+/', ' ', $line)) === false) {
            fwrite(STDERR, "FAIL real rules: missing: $line\n");
            $fail = 1;
        }
    }
    if (preg_match('/^#.*Multihome/m', $filter) || strpos($filter, 'Unable to map port') !== false) {
        fwrite(STDERR, "FAIL real rules: disabled/commented rule found\n");
        $fail = 1;
    }
    if (preg_match('/no nat on igc2 .*from \\(igc2\\)/', $nat)) {
        fwrite(STDERR, "FAIL real rules: NAT exemption on own interface\n");
        $fail = 1;
    }
    echo $fail ? "" : "real rules OK\n";
    exit($fail);
}

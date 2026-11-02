#!/usr/local/bin/php
<?php

/*
 * Multi-WAN DynDNS - Gateways inkl. dpinger-Status als JSON
 * (Interface, Protokoll, Prioritaet, Status, Paketverlust, Latenz)
 *
 * BSD 2-Clause License
 */

require_once 'config.inc';
require_once 'util.inc';
require_once 'interfaces.inc';
require_once 'plugins.inc.d/dpinger.inc';

$status = dpinger_status();
$result = [];

foreach ((new \OPNsense\Routing\Gateways())->gatewaysIndexedByName(true, false, true) as $name => $gw) {
    $st = !empty($status[$name]) ? $status[$name] : null;
    $result[$name] = [
        'name' => $name,
        'interface' => $gw['interface'] ?? '',
        'if' => $gw['if'] ?? '',
        'ipprotocol' => $gw['ipprotocol'] ?? 'inet',
        'gateway' => $gw['gateway'] ?? '',
        'priority' => (int)($gw['priority'] ?? 255),
        'upstream' => !empty($gw['defaultgw']),
        'disabled' => !empty($gw['disabled']),
        'defunct' => !empty($gw['defunct']),
        'monitored' => $st !== null,
        'status' => $st !== null ? strtolower($st['status']) : 'none',
        'loss' => $st['loss'] ?? null,
        'delay' => $st['delay'] ?? null,
    ];
}

echo json_encode($result) . PHP_EOL;

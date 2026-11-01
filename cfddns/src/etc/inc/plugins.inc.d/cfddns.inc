<?php

/*
 * Cloudflare DDNS (per interface) for OPNsense
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
 * INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
 * AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
 */

/**
 * plugin settings (config object) or null when not configured
 */
function cfddns_settings()
{
    $cnf = \OPNsense\Core\Config::getInstance()->object();
    if (!isset($cnf->OPNsense) || !isset($cnf->OPNsense->CloudflareDDNS)) {
        return null;
    }
    return $cnf->OPNsense->CloudflareDDNS;
}

function cfddns_enabled()
{
    $mdl = cfddns_settings();
    return $mdl !== null && isset($mdl->general) && (string)$mdl->general->enabled == '1';
}

/**
 * Periodic check, the script itself decides per entry if it is due (interval).
 */
function cfddns_cron()
{
    $jobs = [];
    if (cfddns_enabled()) {
        $jobs[]['autocron'] = ['/usr/local/sbin/configctl -d cfddns cron', '*'];
    }
    return $jobs;
}

/**
 * Re-check immediately when an interface address changes (PPPoE reconnect, DHCP renew).
 */
function cfddns_configure()
{
    return [
        'newwanip' => ['cfddns_configure_do'],
    ];
}

function cfddns_configure_do($verbose = false)
{
    if (!cfddns_enabled()) {
        return;
    }
    // give routes and the filter reload some time to settle
    mwexec('(/bin/sleep 15; /usr/local/sbin/configctl cfddns check) > /dev/null 2>&1 &');
}

/**
 * Policy routing for the IP check: traffic originating from the firewall with the
 * address of interface X (tcp/443, i.e. our check requests) always leaves through
 * the gateway of interface X. Without this, locally originated traffic follows the
 * default route and every check service reports the IP of the default WAN.
 */
function cfddns_firewall(\OPNsense\Firewall\Plugin $fw)
{
    $mdl = cfddns_settings();
    if ($mdl === null || !cfddns_enabled() || (string)$mdl->general->policy_routing == '0') {
        return;
    }

    $wanted = [];
    if (isset($mdl->accounts) && isset($mdl->accounts->account)) {
        foreach ($mdl->accounts->account as $account) {
            if ((string)$account->enabled != '1' || (string)$account->checkip == 'interface') {
                continue;
            }
            $ifname = (string)$account->interface;
            $ipversion = (string)$account->ipversion;
            if ($ipversion != 'v6') {
                $wanted[$ifname]['inet'] = true;
            }
            if ($ipversion == 'v6' || $ipversion == 'both') {
                $wanted[$ifname]['inet6'] = true;
            }
        }
    }
    if (empty($wanted)) {
        return;
    }

    $ifmap = iterator_to_array($fw->getInterfaceMapping());
    $gateways = $fw->getGateways();
    if ($gateways === null) {
        return;
    }

    foreach ($wanted as $ifname => $protos) {
        if (empty($ifmap[$ifname]['if'])) {
            continue;
        }
        $device = $ifmap[$ifname]['if'];
        $descr = !empty($ifmap[$ifname]['descr']) ? $ifmap[$ifname]['descr'] : strtoupper($ifname);
        foreach (array_keys($protos) as $inet) {
            // any usable gateway on this interface, also when not set as "upstream"/interface gateway
            $gwname = $gateways->getInterfaceGateway($ifname, $inet, false, 'name');
            if (empty($gwname)) {
                continue;
            }
            try {
                $mapping = @$fw->getGateway($gwname);
            } catch (\Throwable $e) {
                $mapping = null;
            }
            if (empty($mapping['logic'])) {
                // without route-to this rule would only bypass the default force-gw rules
                continue;
            }
            $fw->registerFilterRule(
                1,
                [
                    'type' => 'pass',
                    'direction' => 'out',
                    'quick' => true,
                    'ipprotocol' => $inet,
                    'protocol' => 'tcp',
                    'from' => "({$device})",
                    'destination' => ['network' => $ifname, 'not' => true, 'port' => '443'],
                    'gateway' => $gwname,
                    'statetype' => 'keep',
                    'allowopts' => true,
                    'log' => false,
                    '#ref' => 'ui/cloudflareddns/',
                    'descr' => "Cloudflare DDNS: IP-Check via {$descr}",
                ]
            );
        }
    }
}

function cfddns_syslog()
{
    return [
        'cfddns' => ['facility' => ['cfddns']],
    ];
}

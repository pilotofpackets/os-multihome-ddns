<?php

/*
 * Multihome DynDNS for OPNsense
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

function multihomeddns_settings()
{
    $cnf = \OPNsense\Core\Config::getInstance()->object();
    if (!isset($cnf->OPNsense) || !isset($cnf->OPNsense->MultihomeDDNS)) {
        return null;
    }
    return $cnf->OPNsense->MultihomeDDNS;
}

function multihomeddns_enabled()
{
    $mdl = multihomeddns_settings();
    return $mdl !== null && isset($mdl->general) && (string)$mdl->general->enabled == '1';
}

/**
 * every minute; the script decides per entry whether it is due (interval >= 1 minute)
 * and evaluates failover entries on every run
 */
function multihomeddns_cron()
{
    $jobs = [];
    if (multihomeddns_enabled()) {
        $jobs[]['autocron'] = ['/usr/local/sbin/configctl -d multihomeddns cron', '*'];
    }
    return $jobs;
}

function multihomeddns_configure()
{
    return [
        // interface address changed (PPPoE reconnect, DHCP renew)
        'newwanip' => ['multihomeddns_configure_newwanip'],
        // gateway alarm from dpinger (down, loss, delay, recovered)
        'monitor' => ['multihomeddns_configure_monitor'],
    ];
}

function multihomeddns_configure_newwanip($verbose = false)
{
    if (multihomeddns_enabled()) {
        // give routes and the filter reload some time to settle
        mwexec('(/bin/sleep 15; /usr/local/sbin/configctl multihomeddns check) > /dev/null 2>&1 &');
    }
}

function multihomeddns_configure_monitor($verbose = false)
{
    if (multihomeddns_enabled()) {
        mwexec('(/bin/sleep 5; /usr/local/sbin/configctl multihomeddns failover) > /dev/null 2>&1 &');
    }
}

/**
 * Policy routing for the IP check.
 *
 * Traffic originating from the firewall with the address of interface X (our check
 * requests: tcp 80/443, udp 53 for the DNS based check) always leaves through the
 * gateway of interface X.
 *
 * These rules are generated independently of "Disable force gateway"
 * (system/pf_disable_force_gw) on purpose: with that option set, OPNsense no longer
 * generates its own "force gw" rules and all locally originated traffic would follow
 * the default route - every check service would then report the IP of the default WAN.
 */
function multihomeddns_firewall(\OPNsense\Firewall\Plugin $fw)
{
    $mdl = multihomeddns_settings();
    if ($mdl === null || !multihomeddns_enabled() || (string)$mdl->general->policy_routing == '0') {
        return;
    }

    $wanted = [];
    if (isset($mdl->accounts) && isset($mdl->accounts->account)) {
        foreach ($mdl->accounts->account as $account) {
            if ((string)$account->enabled != '1' || (string)$account->checkip == 'interface') {
                continue;
            }
            $inet = (string)$account->ipversion == 'v6' ? 'inet6' : 'inet';
            $wanted[(string)$account->interface][$inet] = true;
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
            // any usable gateway on this interface, also when not marked as upstream / interface gateway
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
                // without route-to this rule would only bypass the default rules
                continue;
            }
            foreach ([['tcp', '80,443'], ['udp', '53']] as $proto) {
                $fw->registerFilterRule(
                    1,
                    [
                        'type' => 'pass',
                        'direction' => 'out',
                        'quick' => true,
                        'ipprotocol' => $inet,
                        'protocol' => $proto[0],
                        'from' => "({$device})",
                        'destination' => ['network' => $ifname, 'not' => true, 'port' => $proto[1]],
                        'gateway' => $gwname,
                        'statetype' => 'keep',
                        'allowopts' => true,
                        'log' => false,
                        '#ref' => 'ui/multihomeddns/',
                        'descr' => "Multihome DynDNS: IP-Check via {$descr}",
                    ]
                );
            }
        }
    }
}

function multihomeddns_syslog()
{
    return [
        'multihomeddns' => ['facility' => ['multihomeddns']],
    ];
}

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

namespace OPNsense\MultihomeDDNS\FieldTypes;

use OPNsense\Base\FieldTypes\BaseListField;

/**
 * Auswahl eines Gateways (inkl. dynamischer DHCP/PPPoE-Gateways), leer = automatisch
 */
class GatewayField extends BaseListField
{
    private static $cache = null;

    protected function actionPostLoadingEvent()
    {
        if (self::$cache === null) {
            self::$cache = [];
            try {
                $intf = [];
                $cfg = \OPNsense\Core\Config::getInstance()->object();
                if (isset($cfg->interfaces)) {
                    foreach ($cfg->interfaces->children() as $key => $node) {
                        $intf[$key] = !empty((string)$node->descr) ? (string)$node->descr : strtoupper($key);
                    }
                }
                foreach ((new \OPNsense\Routing\Gateways())->gatewaysIndexedByName(false, false, true) as $name => $gw) {
                    $ifname = $gw['interface'] ?? '';
                    self::$cache[$name] = sprintf(
                        '%s – %s, %s%s',
                        $name,
                        $intf[$ifname] ?? $ifname,
                        ($gw['ipprotocol'] ?? 'inet') == 'inet6' ? 'IPv6' : 'IPv4',
                        !empty($gw['gateway']) ? ', ' . $gw['gateway'] : ''
                    );
                }
            } catch (\Throwable $e) {
                self::$cache = [];
            }
        }
        $this->internalOptionList = self::$cache;
    }
}

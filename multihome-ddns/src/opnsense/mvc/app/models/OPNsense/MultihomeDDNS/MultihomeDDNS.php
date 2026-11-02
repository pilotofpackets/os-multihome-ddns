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

namespace OPNsense\MultihomeDDNS;

use OPNsense\Base\BaseModel;
use OPNsense\Base\Messages\Message;

class MultihomeDDNS extends BaseModel
{
    private function validateProvider($node, $key, $messages)
    {
        $service = (string)$node->service;
        if ($service == 'custom') {
            if ((string)$node->protocol == '') {
                $messages->appendMessage(new Message(gettext('Bitte ein Protokoll wählen.'), $key . '.protocol'));
            }
            if ((string)$node->server == '') {
                $messages->appendMessage(new Message(gettext('Bitte Server bzw. URL angeben.'), $key . '.server'));
            }
        }
        if ($service == 'powerdns' && (string)$node->server == '') {
            $messages->appendMessage(new Message(gettext('Bitte die API-URL angeben.'), $key . '.server'));
        }
        if ($service == 'azure' && (string)$node->resourceId == '') {
            $messages->appendMessage(new Message(gettext('Bitte die Resource-ID angeben.'), $key . '.resourceId'));
        }
        $needs_zone = ['allinkl', 'aws', 'cloudflare', 'dnspodcn', 'digitalocean', 'gandi', 'hetzner', 'hetzner-legacy', 'hostinger'];
        if (in_array($service, $needs_zone) && (string)$node->zone == '') {
            $messages->appendMessage(new Message(gettext('Für diesen Anbieter wird eine Zone benötigt.'), $key . '.zone'));
        }
        if ($service == 'cloudflare' && (int)(string)$node->ttl != 1 && (int)(string)$node->ttl < 30) {
            $messages->appendMessage(new Message(gettext('Cloudflare: TTL 1 (automatisch) oder mindestens 30.'), $key . '.ttl'));
        }
        $v6_only = ['desec-v6', 'nsupdatev6'];
        $v4_only = ['desec-v4', 'nsupdatev4', 'he-net-tunnel'];
        if ((string)$node->ipversion == 'v4' && in_array($service, $v6_only)) {
            $messages->appendMessage(new Message(gettext('Dieser Anbieter ist nur für IPv6.'), $key . '.service'));
        }
        if ((string)$node->ipversion == 'v6' && in_array($service, $v4_only)) {
            $messages->appendMessage(new Message(gettext('Dieser Anbieter ist nur für IPv4.'), $key . '.service'));
        }
    }

    public function performValidation($validateFullModel = false)
    {
        $messages = parent::performValidation($validateFullModel);

        foreach ($this->accounts->account->iterateItems() as $account) {
            if (!$validateFullModel && !$account->isFieldChanged()) {
                continue;
            }
            $key = $account->__reference;
            $this->validateProvider($account, $key, $messages);
            if ((string)$account->checkip != 'interface') {
                $svc = (string)$account->checkip_service;
                $ipv = (string)$account->ipversion;
                if ($svc == 'custom' && (string)$account->custom_url == '') {
                    $messages->appendMessage(new Message(gettext('Bitte eine URL für den Prüfdienst angeben.'), $key . '.custom_url'));
                }
                if (($ipv == 'v4' && substr($svc, -5) == '_ipv6') || ($ipv == 'v6' && substr($svc, -5) == '_ipv4')) {
                    $messages->appendMessage(new Message(gettext('Prüfdienst passt nicht zur IP-Version.'), $key . '.checkip_service'));
                }
            }
        }

        foreach ($this->failovers->failover->iterateItems() as $failover) {
            if (!$validateFullModel && !$failover->isFieldChanged()) {
                continue;
            }
            $key = $failover->__reference;
            $this->validateProvider($failover, $key, $messages);
            foreach (explode(',', (string)$failover->members) as $uuid) {
                $member = $uuid != '' ? $this->getNodeByReference('accounts.account.' . $uuid) : null;
                if ($member !== null && (string)$member->ipversion != (string)$failover->ipversion) {
                    $messages->appendMessage(new Message(
                        sprintf(gettext('Mitglied "%s" hat eine andere IP-Version.'), (string)$member->description),
                        $key . '.members'
                    ));
                }
            }
        }
        return $messages;
    }
}

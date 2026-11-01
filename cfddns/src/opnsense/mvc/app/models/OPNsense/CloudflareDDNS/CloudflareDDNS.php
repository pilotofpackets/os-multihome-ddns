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

namespace OPNsense\CloudflareDDNS;

use OPNsense\Base\BaseModel;
use OPNsense\Base\Messages\Message;

class CloudflareDDNS extends BaseModel
{
    public function performValidation($validateFullModel = false)
    {
        $messages = parent::performValidation($validateFullModel);

        foreach ($this->accounts->account->iterateItems() as $account) {
            if (!$validateFullModel && !$account->isFieldChanged()) {
                continue;
            }
            $key = $account->__reference;
            $ipversion = (string)$account->ipversion;
            if ((string)$account->service == 'custom' && (string)$account->checkip != 'interface') {
                if ($ipversion != 'v6' && (string)$account->custom_url4 == '') {
                    $messages->appendMessage(new Message(
                        gettext('Für den eigenen Dienst wird eine IPv4-URL benötigt.'),
                        $key . '.custom_url4'
                    ));
                }
                if ($ipversion != 'v4' && (string)$account->custom_url6 == '') {
                    $messages->appendMessage(new Message(
                        gettext('Für den eigenen Dienst wird eine IPv6-URL benötigt.'),
                        $key . '.custom_url6'
                    ));
                }
            }
            $ttl = (int)(string)$account->ttl;
            if ($ttl != 1 && $ttl < 30) {
                $messages->appendMessage(new Message(
                    gettext('TTL muss 1 (automatisch) oder mindestens 30 Sekunden sein.'),
                    $key . '.ttl'
                ));
            }
        }
        return $messages;
    }
}

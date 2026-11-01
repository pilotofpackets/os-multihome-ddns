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

namespace OPNsense\CloudflareDDNS\Api;

use OPNsense\Base\ApiMutableModelControllerBase;

class SettingsController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'cfddns';
    protected static $internalModelClass = 'OPNsense\CloudflareDDNS\CloudflareDDNS';

    public function getAction()
    {
        $data = parent::getAction();
        return ['cfddns' => ['general' => $data['cfddns']['general']]];
    }

    public function searchAccountAction()
    {
        return $this->searchBase(
            'accounts.account',
            ['enabled', 'description', 'interface', 'ipversion', 'checkip', 'zone', 'hostnames'],
            'description'
        );
    }

    public function getAccountAction($uuid = null)
    {
        return $this->getBase('account', 'accounts.account', $uuid);
    }

    public function addAccountAction()
    {
        return $this->addBase('account', 'accounts.account');
    }

    public function setAccountAction($uuid)
    {
        return $this->setBase('account', 'accounts.account', $uuid);
    }

    public function delAccountAction($uuid)
    {
        return $this->delBase('accounts.account', $uuid);
    }

    public function toggleAccountAction($uuid, $enabled = null)
    {
        return $this->toggleBase('accounts.account', $uuid, $enabled);
    }
}

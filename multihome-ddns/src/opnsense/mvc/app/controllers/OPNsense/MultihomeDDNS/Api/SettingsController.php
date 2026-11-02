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

namespace OPNsense\MultihomeDDNS\Api;

use OPNsense\Base\ApiMutableModelControllerBase;
use OPNsense\Core\Backend;

class SettingsController extends ApiMutableModelControllerBase
{
    protected static $internalModelName = 'multihomeddns';
    protected static $internalModelClass = 'OPNsense\MultihomeDDNS\MultihomeDDNS';

    private function runtimeStatus()
    {
        $data = json_decode((new Backend())->configdRun('multihomeddns status'), true);
        return is_array($data) ? $data : [];
    }

    public function getAction()
    {
        $data = parent::getAction();
        return ['multihomeddns' => ['general' => $data['multihomeddns']['general']]];
    }

    /* interface entries */

    public function searchAccountAction()
    {
        $result = $this->searchBase(
            'accounts.account',
            ['enabled', 'description', 'interface', 'ipversion', 'checkip', 'service', 'hostnames', 'interval'],
            'description'
        );
        $status = [];
        foreach ($this->runtimeStatus()['rows'] ?? [] as $row) {
            $status[$row['uuid']] = $row;
        }
        foreach ($result['rows'] as &$row) {
            $st = $status[$row['uuid']] ?? [];
            foreach (['local', 'local_class', 'detected', 'ip_class', 'written', 'cgnat', 'behind_nat', 'method',
                      'url', 'checked', 'next', 'updated', 'status', 'error', 'device'] as $field) {
                $row['rt_' . $field] = $st[$field] ?? null;
            }
        }
        return $result;
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

    /* failover entries */

    public function searchFailoverAction()
    {
        $result = $this->searchBase(
            'failovers.failover',
            ['enabled', 'description', 'ipversion', 'members', 'strategy', 'failback', 'service', 'hostnames'],
            'description'
        );
        $status = [];
        foreach ($this->runtimeStatus()['failovers'] ?? [] as $row) {
            $status[$row['uuid']] = $row;
        }
        foreach ($result['rows'] as &$row) {
            $st = $status[$row['uuid']] ?? [];
            foreach (['active', 'active_ip', 'written', 'updated', 'switched', 'members', 'history', 'status', 'error'] as $field) {
                $row['rt_' . $field] = $st[$field] ?? null;
            }
        }
        return $result;
    }

    public function getFailoverAction($uuid = null)
    {
        return $this->getBase('failover', 'failovers.failover', $uuid);
    }

    public function addFailoverAction()
    {
        return $this->addBase('failover', 'failovers.failover');
    }

    public function setFailoverAction($uuid)
    {
        return $this->setBase('failover', 'failovers.failover', $uuid);
    }

    public function delFailoverAction($uuid)
    {
        return $this->delBase('failovers.failover', $uuid);
    }

    public function toggleFailoverAction($uuid, $enabled = null)
    {
        return $this->toggleBase('failovers.failover', $uuid, $enabled);
    }
}

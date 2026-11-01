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

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;

class ServiceController extends ApiControllerBase
{
    private function decode($response)
    {
        $data = json_decode(trim((string)$response), true);
        return is_array($data) ? $data : ['status' => 'error', 'message' => trim((string)$response)];
    }

    /**
     * apply settings: firewall rules (policy routing), cron job, then an immediate check
     */
    public function reconfigureAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'failed'];
        }
        $backend = new Backend();
        $backend->configdRun('filter reload');
        $backend->configdRun('cron restart');
        $backend->configdRun('cfddns check', true);
        return ['status' => 'ok'];
    }

    public function statusAction()
    {
        return $this->decode((new Backend())->configdRun('cfddns status'));
    }

    public function checkAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'failed'];
        }
        return $this->decode((new Backend())->configdRun('cfddns check'));
    }

    public function forceAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'failed'];
        }
        return $this->decode((new Backend())->configdRun('cfddns force'));
    }

    public function testAction($uuid = null)
    {
        if (!$this->request->isPost() || !preg_match('/^[0-9a-f-]{36}$/i', (string)$uuid)) {
            return ['status' => 'failed'];
        }
        return $this->decode((new Backend())->configdpRun('cfddns test', [$uuid]));
    }
}

#!/usr/local/bin/php
<?php

/*
 * Multihome DynDNS - Einstellungen frueherer Versionen uebernehmen
 * (OPNsense/MultiWanDDNS -> OPNsense/MultihomeDDNS). Aendert nur etwas,
 * wenn der alte Abschnitt existiert und der neue noch nicht.
 *
 * BSD 2-Clause License
 */

require_once 'script/load_phalcon.php';

$cfg = \OPNsense\Core\Config::getInstance();
$root = $cfg->object();
if (isset($root->OPNsense->MultiWanDDNS) && !isset($root->OPNsense->MultihomeDDNS)) {
    $old = dom_import_simplexml($root->OPNsense->MultiWanDDNS);
    $new = $old->ownerDocument->createElement('MultihomeDDNS');
    foreach ($old->attributes as $attr) {
        $new->setAttribute($attr->name, $attr->value);
    }
    while ($old->firstChild) {
        $new->appendChild($old->firstChild);
    }
    $old->parentNode->replaceChild($new, $old);
    $cfg->save();
    echo "Einstellungen aus Multi-WAN DynDNS uebernommen\n";
}

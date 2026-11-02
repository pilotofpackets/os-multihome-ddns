<?php
namespace OPNsense\Core { class Config { static function getInstance(){return new self;} function object(){ return simplexml_load_string(file_get_contents(getenv('CFG'))); } } }
namespace OPNsense\Routing { class Gateways { function getInterfaceGateway($if,$inet,$only,$prop){ $m=['wan'=>['inet'=>'WAN_PPPOE','inet6'=>'WAN_V6'],'opt1'=>['inet'=>'DSL2_GW']]; return $m[$if][$inet] ?? null; } } }
namespace OPNsense\Firewall { class Plugin { public $rules=[]; private $map=['WAN_PPPOE'=>['logic'=>'x'],'WAN_V6'=>['logic'=>'y'],'DSL2_GW'=>['logic'=>'z']];
  function getInterfaceMapping(){ yield 'wan'=>['if'=>'pppoe0','descr'=>'DSL1']; yield 'opt1'=>['if'=>'igb1','descr'=>'DSL2']; yield 'opt2'=>['if'=>'igb2','descr'=>'DSL3']; }
  function getGateways(){ return new \OPNsense\Routing\Gateways; }
  function getGateway($gw){ return $this->map[$gw]; }
  function registerFilterRule($p,$c,$d=null){ $this->rules[]=[$p,$c]; } } }
namespace {
  function mwexec($c){ echo "mwexec: $c\n"; }
  require getenv('INC');
  $fw = new \OPNsense\Firewall\Plugin; multiwanddns_firewall($fw);
  foreach ($fw->rules as [$p,$c]) printf("prio %d: pass out quick %s %s from %s port %s gw=%s | %s\n",$p,$c['ipprotocol'],$c['protocol'],$c['from'],$c['destination']['port'],$c['gateway'],$c['descr']);
  print_r(multiwanddns_cron()); multiwanddns_configure_newwanip(); multiwanddns_configure_monitor(); print_r(array_keys(multiwanddns_configure()));
}

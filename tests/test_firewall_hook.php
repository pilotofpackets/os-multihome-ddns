<?php
namespace OPNsense\Core { class Config { static function getInstance(){return new self;} function object(){ return simplexml_load_string(file_get_contents(getenv('CFG'))); } } }
namespace OPNsense\Routing { class Gateways {
  function getInterfaceGateway($if,$inet,$only,$prop){ $m=['wan'=>['inet'=>'WAN_PPPOE','inet6'=>'WAN_V6'],'opt1'=>['inet'=>'DSL2_GW']]; return $m[$if][$inet] ?? null; }
  // opt2: gateway exists but is not the "interface gateway" -> fallback must find it
  function gatewaysIndexedByName($a=false,$b=false,$c=false){ return [
    'DSL3_BACKUP'=>['interface'=>'opt2','ipprotocol'=>'inet','priority'=>200],
    'DSL3_GW'=>['interface'=>'opt2','ipprotocol'=>'inet','priority'=>10],
    'DSL3_OFF'=>['interface'=>'opt2','ipprotocol'=>'inet','priority'=>1,'disabled'=>'1'],
    'DSL2_ALT'=>['interface'=>'opt1','ipprotocol'=>'inet','priority'=>5]]; }
} }
namespace OPNsense\Firewall { class Plugin { public $rules=[]; private $map=['WAN_PPPOE'=>['logic'=>'x'],'WAN_V6'=>['logic'=>'y'],'DSL2_GW'=>['logic'=>'z'],'DSL3_GW'=>['logic'=>'w'],'DSL2_ALT'=>['logic'=>'v']];
  function getInterfaceMapping(){ yield 'wan'=>['if'=>'pppoe0','descr'=>'DSL1']; yield 'opt1'=>['if'=>'igb1','descr'=>'DSL2']; yield 'opt2'=>['if'=>'igb2','descr'=>'DSL3']; }
  function getGateways(){ return new \OPNsense\Routing\Gateways; }
  function getGateway($gw){ return $this->map[$gw]; }
  function registerFilterRule($p,$c,$d=null){ $this->rules[]=[$p,$c]; } } }
namespace {
  function mwexec($c){ echo "mwexec: $c\n"; }
  require getenv('INC');
  $fw = new \OPNsense\Firewall\Plugin; multihomeddns_firewall($fw);
  $got = [];
  foreach ($fw->rules as [$p,$c]) { $got[$c['from'].' '.$c['ipprotocol'].' '.$c['protocol']] = $c['gateway']; }
  $expect = ['(pppoe0) inet tcp'=>'WAN_PPPOE', '(pppoe0) inet6 tcp'=>'WAN_V6', '(igb1) inet tcp'=>'DSL2_ALT', '(igb2) inet tcp'=>'DSL3_GW'];
  foreach ($expect as $k=>$v) { if (($got[$k] ?? null) !== $v) { fwrite(STDERR, "FAIL hook: $k -> ".($got[$k] ?? 'none')." (expected $v)\n"); exit(1); } }
  echo "hook OK: interface gateway, manual gateway, fallback gateway\n";
  foreach ($fw->rules as [$p,$c]) printf("prio %d: pass out quick %s %s from %s port %s gw=%s | %s\n",$p,$c['ipprotocol'],$c['protocol'],$c['from'],$c['destination']['port'],$c['gateway'],$c['descr']);
  print_r(multihomeddns_cron()); multihomeddns_configure_newwanip(); multihomeddns_configure_monitor(); print_r(array_keys(multihomeddns_configure()));
}

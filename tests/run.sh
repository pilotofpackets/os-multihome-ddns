#!/bin/sh
# Runs the backend scenario tests and the firewall hook test against simulated
# interfaces, gateways (dpinger), pf rules, check services and provider APIs.
# Requirements: python3 with requests + dnspython, optional php-cli.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
cp "$HERE"/fixtures/* "$T"/
chmod +x "$T/ifconfig" "$T/curl" "$T/pfctl" "$T/gateways"
mkdir -p "$T/state"
python3 "$T/gw.py"

export T SCRIPTDIR="$ROOT/multihome-ddns/src/opnsense/scripts/multihomeddns"
export MHDDNS_CONFIG="$T/config.xml" MHDDNS_STATE_DIR="$T/state" MHDDNS_LOCK="$T/lock"
export MHDDNS_CURL="$T/curl" MHDDNS_IFCONFIG="$T/ifconfig" MHDDNS_PFCTL="$T/pfctl" MHDDNS_GATEWAYS="$T/gateways"

echo "### backend scenarios"
(cd "$T" && python3 "$HERE/test_scenarios.py")

if command -v php >/dev/null 2>&1; then
    echo "### firewall hook"
    CFG="$T/hook_config.xml" INC="$ROOT/multihome-ddns/src/etc/inc/plugins.inc.d/multihomeddns.inc" \
        php -d error_reporting=E_ALL "$HERE/test_firewall_hook.php"
    echo "### php lint"
    find "$ROOT/multihome-ddns" \( -name '*.php' -o -name '*.inc' \) -exec php -l {} \; | grep -v '^No syntax errors' || true
fi
echo "### done"

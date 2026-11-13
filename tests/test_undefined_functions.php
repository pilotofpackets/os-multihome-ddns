<?php
/*
 * Static check: every function the plugin's PHP files call must exist - as a PHP builtin,
 * in the file itself or in OPNsense core (src/etc/inc). Catches calls to helpers that
 * were removed from core (e.g. mwexec()).
 * usage: php tests/test_undefined_functions.php <core-checkout> <file>...
 */
$core = $argv[1];
$coreFuncs = [];
$it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator("$core/src/etc/inc"));
foreach ($it as $f) {
    if (preg_match('/\.(inc|php)$/', (string)$f) && preg_match_all('/^\s*function\s+&?([a-zA-Z0-9_]+)\s*\(/m', file_get_contents((string)$f), $m)) {
        foreach ($m[1] as $name) {
            $coreFuncs[strtolower($name)] = true;
        }
    }
}
if (count($coreFuncs) < 100) {
    fwrite(STDERR, "FAIL: core functions not found in $core/src/etc/inc\n");
    exit(1);
}
$fail = 0;
foreach (array_slice($argv, 2) as $file) {
    $tokens = token_get_all(file_get_contents($file));
    $own = [];
    $calls = [];
    $n = count($tokens);
    for ($i = 0; $i < $n; $i++) {
        if (!is_array($tokens[$i]) || $tokens[$i][0] !== T_STRING) {
            continue;
        }
        $j = $i - 1;
        while ($j >= 0 && is_array($tokens[$j]) && $tokens[$j][0] === T_WHITESPACE) {
            $j--;
        }
        $k = $i + 1;
        while ($k < $n && is_array($tokens[$k]) && $tokens[$k][0] === T_WHITESPACE) {
            $k++;
        }
        $prev = $tokens[$j] ?? null;
        $prevId = is_array($prev) ? $prev[0] : $prev;
        if ($prevId === T_FUNCTION) {
            $own[strtolower($tokens[$i][1])] = true;
        } elseif (($tokens[$k] ?? null) === '(' && !in_array($prevId, [T_OBJECT_OPERATOR, T_NULLSAFE_OBJECT_OPERATOR, T_DOUBLE_COLON, T_NEW, T_NS_SEPARATOR], true)) {
            $calls[strtolower($tokens[$i][1])] = $tokens[$i][2];
        }
    }
    foreach ($calls as $name => $line) {
        if (!isset($own[$name]) && !function_exists($name) && !isset($coreFuncs[$name])) {
            fwrite(STDERR, "FAIL: $file:$line calls undefined function $name()\n");
            $fail = 1;
        }
    }
}
echo $fail ? '' : "function check OK\n";
exit($fail);

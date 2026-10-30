#!/usr/bin/env bash
# Run on the Ubuntu/macOS host connected to the Fire TV by USB or local network.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VPKG="${1:-$HERE/MK_Ekino_Vega_0.1.6_armv7.vpkg}"
DEVICE="${2:-}"
command -v vega >/dev/null || { echo 'Brak Vega CLI. Zainstaluj oficjalny SDK na Ubuntu/macOS.' >&2; exit 1; }
[[ -f "$VPKG" ]] || { echo "Nie znaleziono pakietu: $VPKG" >&2; exit 1; }
vega exec vpt validate "$VPKG"
if [[ -n "$DEVICE" && "$DEVICE" == *:* ]]; then
  vega exec vda connect "$DEVICE"
fi
vega device list
if [[ -n "$DEVICE" ]]; then
  vega device -d "$DEVICE" install-app --packagePath "$VPKG"
  vega device -d "$DEVICE" launch-app --appName org.mkapps.ekino.main
else
  vega device install-app --packagePath "$VPKG"
  vega device launch-app --appName org.mkapps.ekino.main
fi

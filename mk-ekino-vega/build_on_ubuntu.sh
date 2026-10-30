#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
command -v vega >/dev/null || { echo 'Zainstaluj oficjalny Vega SDK i dodaj vega do PATH.' >&2; exit 1; }
vega --version
npm ci
npm run typecheck
npm test
vega project doctor
npm run build:app
vega exec vpt validate build/armv7-release/mk-ekino-vega_armv7.vpkg
echo 'Gotowy pakiet: build/armv7-release/mk-ekino-vega_armv7.vpkg'

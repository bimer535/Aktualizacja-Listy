#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v xcodegen >/dev/null || brew install xcodegen
xcodegen generate
xcodebuild -resolvePackageDependencies -project MKEkino.xcodeproj -scheme MKEkino
xcodebuild -project MKEkino.xcodeproj -scheme MKEkino -configuration Release -destination 'generic/platform=iOS' -derivedDataPath build CODE_SIGNING_ALLOWED=NO build
mkdir -p dist/Payload
cp -R build/Build/Products/Release-iphoneos/MKEkino.app dist/Payload/
(cd dist && zip -qry MK_Ekino_iOS_1.0.3.ipa Payload)
rm -rf dist/Payload
shasum -a 256 dist/MK_Ekino_iOS_1.0.3.ipa > dist/SHA256SUMS.txt


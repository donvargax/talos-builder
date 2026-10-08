#!/usr/bin/env bash
# Networked CI bootstrap, not part of make check. Check the checksum manifest
# against the repository pin before trusting its per-platform archive checksum.
set -euo pipefail
version=6.5.1
manifest_sha=1a0ac1e1fdb920668e3cba96cad9ea94d23d2c1b667fe4f60d5d77f1573a8a08
case $(uname -m) in
    x86_64) arch=amd64 ;;
    aarch64) arch=arm64 ;;
    *) echo 'Unsupported itos installer architecture' >&2; exit 1 ;;
esac
archive="itos-${version}-linux-${arch}.tar.gz"
base="https://github.com/donvargax/itos/releases/download/v${version}"
mkdir -p .tools/itos
cd .tools/itos
curl --fail --silent --show-error --location --retry 3 "$base/checksums.txt" -o checksums.txt
printf '%s  checksums.txt\n' "$manifest_sha" | sha256sum --check --strict
curl --fail --silent --show-error --location --retry 3 "$base/$archive" -o "$archive"
awk -v archive="$archive" '$2 == archive {print}' checksums.txt > archive.sha256
test "$(wc -l < archive.sha256)" -eq 1
sha256sum --check --strict archive.sha256
tar -xzf "$archive" itos
chmod +x itos
test "$(./itos --version)" = "itos $version"
printf '%s\n' "$PWD" >> "$GITHUB_PATH"

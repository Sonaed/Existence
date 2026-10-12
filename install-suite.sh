#!/usr/bin/env bash
set -euo pipefail
root="${1:-$(dirname "${BASH_SOURCE[0]}")/packaging/dist/deb}"
keyring="${EXISTENCE_KEYRING:-}"
shopt -s nullglob
packages=("$root"/existence-*.deb)
if ((${#packages[@]} == 0)); then echo "No Debian packages found in $root" >&2; exit 2; fi
for package in "${packages[@]}"; do
  [[ -f "$package.asc" ]] || { echo "Missing detached signature: $package.asc" >&2; exit 3; }
  if [[ -n "$keyring" ]]; then
    gpg --batch --no-default-keyring --keyring "$keyring" --verify "$package.asc" "$package" >/dev/null \
      || { echo "Invalid package signature: $package" >&2; exit 4; }
  else
    echo "EXISTENCE_KEYRING is required for cryptographic verification" >&2; exit 5
  fi
done
exec sudo apt install "${packages[@]}"

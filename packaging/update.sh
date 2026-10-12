#!/usr/bin/env bash
set -euo pipefail

# Stable updater entry point. Package managers remain authoritative; this
# wrapper refuses unsigned local bundles unless explicitly overridden.
bundle="${1:?usage: update.sh PACKAGE [--allow-unsigned]}"
allow_unsigned="${2:-}"
if [[ ! -f "$bundle" ]]; then echo "bundle not found: $bundle" >&2; exit 2; fi
if [[ "$allow_unsigned" != "--allow-unsigned" && ! -f "$bundle.asc" ]]; then
  echo "refusing unsigned update; provide a detached .asc signature" >&2; exit 3
fi
if [[ "$allow_unsigned" != "--allow-unsigned" ]]; then
  [[ -n "${EXISTENCE_KEYRING:-}" ]] || { echo "EXISTENCE_KEYRING is required for cryptographic verification" >&2; exit 5; }
  gpg --batch --no-default-keyring --keyring "$EXISTENCE_KEYRING" --verify "$bundle.asc" "$bundle" >/dev/null \
    || { echo "invalid package signature" >&2; exit 6; }
fi
case "$bundle" in
  *.deb) exec sudo apt install "$bundle" ;;
  *) echo "unsupported bundle type: $bundle" >&2; exit 4 ;;
esac

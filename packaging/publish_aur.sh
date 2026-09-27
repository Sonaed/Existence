#!/usr/bin/env bash
# Publie (ou met à jour) les paquets Existence sur l'AUR.
# Prérequis : compte AUR avec ta clé SSH, et les dépôts GitHub taggés v26.0.
#   python packaging/build_packages.py --format arch --github <ton-compte>
#   ./packaging/publish_aur.sh                 # tous
#   ./packaging/publish_aur.sh existence-nova  # un seul
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dist="$here/dist/aur"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
packages=("$@")
[ ${#packages[@]} -eq 0 ] && mapfile -t packages < <(ls "$dist")
for pkg in "${packages[@]}"; do
  echo "▸ $pkg"
  git clone -q "ssh://aur@aur.archlinux.org/$pkg.git" "$work/$pkg"
  cp "$dist/$pkg/"* "$work/$pkg/"
  (cd "$work/$pkg" && makepkg --printsrcinfo > .SRCINFO && git add -A &&
     (git diff --cached --quiet && echo "  inchangé") ||
     (git commit -qm "Existence $(grep '^pkgver=' PKGBUILD | cut -d= -f2)-$(grep '^pkgrel=' PKGBUILD | cut -d= -f2)" && git push -q && echo "  publié"))
done

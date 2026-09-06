#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="$(cd "$(dirname "$0")" && pwd)"

for f in .bash_profile .gitconfig .gtkrc-2.0 .Xresources .blerc; do
  if [ -f "$HOME/$f" ]; then
    cp "$HOME/$f" "$HOME/$f.bak"
  fi
  cp "$HOME_DIR/$f" "$HOME/$f"
done

echo "Dotfiles de home instalados. Backups en ~/*.bak"
echo "Completa TU_EMAIL / TU_NOMBRE en ~/.gitconfig"
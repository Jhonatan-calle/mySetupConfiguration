# Dotfiles — setup Hyprland

Configuración de `~/.config` para Arch Linux + Hyprland (base ML4W). El objetivo
es clonar este repo en otra máquina para reproducir el setup lo más idéntico posible.

## Despliegue en máquina nueva

```sh
# 1. Clonar como ~/.config
git clone git@github.com:Jhonatan-calle/setupConfiguration.git ~/.config

# 2. Dotfiles de home (gitconfig, bash_profile, gtk/xresources, blerc)
~/.config/home/install.sh

# 3. Paquetes oficiales explícitos
sudo pacman -S --needed $(cat ~/.config/paquetes-arch.txt)

# 4. Paquetes AUR (requiere yay: sudo pacman -S yay)
yay -S --needed $(cat ~/.config/paquetes-aur.txt)

# 5. Servicios de sistema
sudo systemctl enable --now bluetooth docker earlyoom sshd NetworkManager-dispatcher fstrim.timer

# 6. Servicios de usuario
systemctl --user enable --now pipewire pipewire-pulse wireplumber xdg-user-dirs mic-fix.service mic-fix.timer
```

## Notas por componente

- **Tema ML4W**: varios dotfiles de home (`.zshrc`, `.Xresources`, `.gtkrc-2.0`,
  `.bashrc`) son symlinks a la instalación de ML4W en `~/.mydotfiles/`. Si querés
  replicarlos sin ML4W, usá las versiones en `home/` (corrigen la ruta `/home/raabe`
  del template y la ruta absoluta del usuario).
- **mic-fix** (`systemd/user/` + `pipewire/pipewire.conf.d/10-mic-fix.conf`): fix de
  ganancia de micrófono para "Internal Mic Boost". Es específico del hardware; si la
  otra máquina no lo necesita, no lo habilites.
- **Scheduler** (`scripts/scheduler/install.sh`): instala `scheduler` en `~/.local/bin`
   y usa datos de `~/OneDrive/varios/scheduler`. Correr el instalador manualmente.
- **Widgets/scripts** en `scripts/` ya se referencian desde hypr/waybar; los daemons
  de batería/pomodoro se corren desde la config de waybar.
- **Fuentes**: JetBrainsMono Nerd Font y Font Awesome vienen vía paquetes
  (`ttf-jetbrains-mono`, `woff2-font-awesome`); para la Nerd Font completa:
  `yay -S ttf-jetbrainsm-nerd-font` (no está en la lista, agregarla si aplica).

## Seguridad

- NO commitear secretos. `.wakatime.cfg`, claves de API o tokens deben quedar fuera.
  Este repo usa `gitignore` para eso; revisar antes de `git add`.
- El `home/.gitconfig` lleva placeholders (`TU_EMAIL`, `TU_NOMBRE`); completarlos en
  la máquina nueva.

## Archivo actual / historial

- `paquetes-arch.txt` (explicitos)  ← `pacman -Qqet`
- `paquetes-aur.txt`  (explicitos AUR, sin `-debug`)  ← `pacman -Qqem | grep -v -- -debug`
- Actualizar con: `pacman -Qqet > paquetes-arch.txt && pacman -Qqem | grep -v -- -debug > paquetes-aur.txt`
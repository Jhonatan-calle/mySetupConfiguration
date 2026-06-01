# ~/.config/waybar/toggle.sh
#!/usr/bin/env bash
# Este script lo corre hyprland con un bind
if pgrep -x waybar > /dev/null; then
    pkill waybar
else
    waybar &
fi

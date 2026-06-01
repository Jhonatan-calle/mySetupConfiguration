#!/bin/bash

# Detectar monitor externo
EXTERNAL=$(hyprctl monitors all | grep "Monitor" | awk '{print $2}' | grep -v "eDP-1")

if [ -z "$EXTERNAL" ]; then
    notify-send "No hay monitor externo conectado"
    exit 1
fi

# Preguntar qué modo
CHOICE=$(echo -e "Extender\nEspejo" | wofi --dmenu --prompt "Monitor $EXTERNAL:")

case $CHOICE in
    "Extender")
        hyprctl keyword monitor eDP-1,1366x768@60,0x0,1
        hyprctl keyword monitor $EXTERNAL,preferred,1366x0,1
        ;;
    "Espejo")
        hyprctl keyword monitor eDP-1,1366x768@60,0x0,1
        hyprctl keyword monitor $EXTERNAL,preferred,0x0,1,mirror,eDP-1
        ;;
esac

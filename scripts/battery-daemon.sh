#!/usr/bin/env bash
# este script lo ejecute hyprland (exete-once creo)

PIDFILE="/tmp/battery-daemon.pid"
LAST_NOTIFIED="/tmp/battery-last-notified"

if [ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
    echo "Daemon ya corriendo (PID $(cat $PIDFILE))"
    exit 1
fi
echo $$ > "$PIDFILE"
trap "rm -f $PIDFILE" EXIT
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"

while true; do
    CAPACITY=$(cat /sys/class/power_supply/BAT1/capacity)
    STATUS=$(cat /sys/class/power_supply/BAT1/status)

    if [ "$STATUS" = "Charging" ] || [ "$STATUS" = "Full" ]; then
        rm -f "$LAST_NOTIFIED"
    else
        last=$(cat "$LAST_NOTIFIED" 2>/dev/null || echo 100)

        if [ "$CAPACITY" -le 15 ] && [ "$last" -gt 15 ]; then
            notify-send -u critical "󰂃 Batería crítica" "${CAPACITY}% — conectá el cargador"
            echo "$CAPACITY" > "$LAST_NOTIFIED"
        elif [ "$CAPACITY" -le 30 ] && [ "$last" -gt 15 ]; then
            notify-send -u normal "󰁻 Batería baja ${CAPACITY}%"
            echo "$CAPACITY" > "$LAST_NOTIFIED"
        fi
    fi

    sleep 60 
done

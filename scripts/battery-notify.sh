#!/usr/bin/env bash
USER_ID=1000
LAST_NOTIFIED="/tmp/battery-last-notified"

# Solo corre cuando cambia el cargador (ACAD)
CAPACITY=$(cat /sys/class/power_supply/BAT1/capacity)

if [ "$POWER_SUPPLY_ONLINE" = "1" ]; then
    rm -f "$LAST_NOTIFIED"
    exit 0
fi


if [ "$CAPACITY" -le 15 ]; then
    systemd-run --uid=$USER_ID \
        --setenv=DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_ID/bus" \
        --scope \
        notify-send -u critical "󰂃 Batería crítica" "${CAPACITY}% — conectá el cargador"
    echo "$CAPACITY" > "$LAST_NOTIFIED"
elif [ "$CAPACITY" -le 30 ]; then
    systemd-run --uid=$USER_ID \
        --setenv=DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_ID/bus" \
        --scope \
        notify-send -u normal "󰁻 Batería baja ${CAPACITY}%"
    echo "$CAPACITY" > "$LAST_NOTIFIED"
fi


#la regla que corre este script es:
# /etc/udev/rules.d/99-battery-notify.rules

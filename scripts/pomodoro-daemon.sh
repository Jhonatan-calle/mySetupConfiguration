#!/usr/bin/env bash
# script ejecutado por hyprland (exec once creo)

STATE_FILE="/tmp/waybar-pomodoro"
WORK_MINS=30
BREAK_MINS=1
LONG_BREAK_MINS=15
PIDFILE="/tmp/waybar-pomodoro-daemon.pid"

# Evitar instancias duplicadas
if [ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
    echo "Daemon ya corriendo (PID $(cat $PIDFILE))"
    exit 1
fi
echo $$ > "$PIDFILE"
trap "rm -f $PIDFILE" EXIT

[ ! -f "$STATE_FILE" ] && echo "stopped|0|work" > "$STATE_FILE"

while true; do
    IFS='|' read -r status elapsed mode < "$STATE_FILE"

    if [ "$status" = "running" ]; then

        if [ "$mode" = "work" ]; then
            total=$(( WORK_MINS * 60 ))
        elif [ "$mode" = "break" ]; then
            total=$(( BREAK_MINS * 60 ))
        else
            total=$(( LONG_BREAK_MINS * 60 ))
        fi

        now=$(date +%s)
        spent=$(( now - elapsed ))

        if [ $spent -ge $total ]; then
            if [ "$mode" = "break" ] || [ "$mode" = "long_break" ]; then
                notify-send -u critical "󰅶 ¡Click clock! marioneta" "¡A trabajar!"
            fi
            echo "stopped|0|work" > "$STATE_FILE"
        fi
    fi

    sleep 1
done

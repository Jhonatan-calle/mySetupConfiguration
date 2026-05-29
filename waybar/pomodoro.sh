#!/usr/bin/env bash

# Archivo de estado
STATE_FILE="/tmp/waybar-pomodoro"
WORK_MINS=30
BREAK_MINS=1
LONG_BREAK_MINS=15

# Inicializar si no existe
if [ ! -f "$STATE_FILE" ]; then
  echo "stopped|0|work" >"$STATE_FILE"
fi


case "$1" in
toggle)
  IFS='|' read -r status elapsed mode <"$STATE_FILE"
  if [ "$status" = "stopped" ]; then
    echo "running|$(date +%s)|$mode" >"$STATE_FILE"
  elif [ "$status" = "paused" ]; then
    # Al reanudar, ajustar el start para que incluya el tiempo ya transcurrido
    now=$(date +%s)
    adjusted_start=$((now - elapsed))
    echo "running|$adjusted_start|$mode" >"$STATE_FILE"
  else
    # Pausar: guardar segundos transcurridos
    start=$elapsed
    now=$(date +%s)
    spent=$((now - start))
    echo "paused|$spent|$mode" >"$STATE_FILE"
  fi
  ;;
reset)
  IFS='|' read -r status elapsed mode <"$STATE_FILE"
  echo "stopped|0|$mode" >"$STATE_FILE"
  ;;
switch)
  IFS='|' read -r status elapsed mode <"$STATE_FILE"
  if [ "$mode" = "work" ]; then
        new_mode="break"
  elif [ "$mode" = "break" ]; then
        new_mode="long_break"
  else
        new_mode="work"
  fi
  echo "stopped|0|$new_mode" >"$STATE_FILE"
  ;;
*)
  # Leer y mostrar estado
  IFS='|' read -r status elapsed mode <"$STATE_FILE"

  if [ "$mode" = "work" ]; then
    total=$(( WORK_MINS * 60 ))
    icon="󰔛"
  elif [ "$mode" = "break" ]; then
    total=$(( BREAK_MINS * 60 ))
    icon="󰅶"
  else
    total=$(( LONG_BREAK_MINS * 60 ))
    icon="󰒲"
  fi

  if [ "$status" = "running" ]; then
    start=$elapsed
    now=$(date +%s)
    spent=$((now - start))
    if [ $spent -ge $total ]; then
      IFS='|' read -r status elapsed mode <"$STATE_FILE"
      total=$(( WORK_MINS * 60 ))
      icon="󰔛"
      spent=0
    fi
  elif [ "$status" = "paused" ]; then
    spent=$elapsed
  else
    spent=0
  fi

  remaining=$((total - spent))
  [ $remaining -lt 0 ] && remaining=0

  mins=$((remaining / 60))
  secs=$((remaining % 60))
  time_str=$(printf "%02d:%02d" $mins $secs)

  if [ "$status" = "running" ]; then
    state_icon="▶"
  elif [ "$status" = "paused" ]; then
    state_icon="⏸"
  else
    state_icon="⏹"
  fi

  echo "{\"text\": \"$icon $state_icon $time_str\", \"class\": \"$status\"}"
  ;;
esac

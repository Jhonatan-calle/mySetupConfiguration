#!/bin/bash

DATA_FILE="$HOME/OneDrive/varios/gastos/gastos.json"
MES_ACTUAL=$(date +%Y-%m)

init_if_needed() {
  if [ ! -f "$DATA_FILE" ]; then
    echo '{"mes":"'"$MES_ACTUAL"'","total":0,"items":[]}' >"$DATA_FILE"
    return
  fi
  MES_GUARDADO=$(jq -r '.mes' "$DATA_FILE")
  if [ "$MES_GUARDADO" != "$MES_ACTUAL" ]; then
    # Archivar mes anterior en lugar de sobreescribir
    ARCHIVO="$HOME/OneDrive/varios/gastos/history/${MES_GUARDADO}.json"
    cp "$DATA_FILE" "$ARCHIVO"
    echo '{"mes":"'"$MES_ACTUAL"'","total":0,"items":[]}' >"$DATA_FILE"
  fi
}

add_gasto() {
  DESC=$(echo "" | rofi -dmenu -p "desc" -theme ~/.config/rofi/gastos.rasi)
  [ -z "$DESC" ] && exit 0

  MONTO=$(echo "" | rofi -dmenu -p "monto" -theme ~/.config/rofi/gastos.rasi)
  [ -z "$MONTO" ] && exit 0
  MONTO=$(echo "$MONTO" | tr ',' '.')

  if ! echo "$MONTO" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
    notify-send "gastos" "monto inválido: $MONTO"
    exit 1
  fi

  FECHA=$(date +%d/%m\ %H:%M)
  jq --arg desc "$DESC" \
    --argjson monto "$MONTO" \
    --arg fecha "$FECHA" \
    '.total += $monto | .items += [{"desc":$desc,"monto":$monto,"fecha":$fecha}]' \
    "$DATA_FILE" >/tmp/gastos_tmp.json && mv /tmp/gastos_tmp.json "$DATA_FILE"

  TOTAL=$(jq -r '.total' "$DATA_FILE")
  notify-send "$DESC" "\$$MONTO — total: \$$TOTAL"
}

show_waybar() {
  init_if_needed
  TOTAL=$(jq -r '.total' "$DATA_FILE")
  COUNT=$(jq -r '.items | length' "$DATA_FILE")

  # Mostrar en miles (ej: 150000 -> 150k)
  TOTAL_DISPLAY=$(echo "$TOTAL" | awk '{
        if ($1 >= 1000) printf "%.1fk", $1/1000
        else printf "%s", $1
    }')

  echo "{\"text\":\"${TOTAL_DISPLAY}\"}"
}

case "$1" in
add)
  init_if_needed
  add_gasto
  ;;
*) show_waybar ;;
esac

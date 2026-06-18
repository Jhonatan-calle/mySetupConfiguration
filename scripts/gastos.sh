#!/bin/bash
DATA_FILE="$HOME/OneDrive/varios/gastos/gastos.json"
MES_ACTUAL=$(date +%Y-%m)

init_if_needed() {
  if [ ! -f "$DATA_FILE" ]; then
    mkdir -p "$(dirname "$DATA_FILE")/history"
    echo '{"mes":"'"$MES_ACTUAL"'","total":0,"items":[]}' >"$DATA_FILE"
    return
  fi
  MES_GUARDADO=$(jq -r '.mes' "$DATA_FILE")
  if [ "$MES_GUARDADO" != "$MES_ACTUAL" ]; then
    mkdir -p "$(dirname "$DATA_FILE")/history"
    ARCHIVO="$HOME/OneDrive/varios/gastos/history/${MES_GUARDADO}.json"
    cp "$DATA_FILE" "$ARCHIVO"
    echo '{"mes":"'"$MES_ACTUAL"'","total":0,"items":[]}' >"$DATA_FILE"
  fi
}

add_gasto() {
  init_if_needed

  DESCS=$(jq -r '[.items[].desc] | unique | sort | .[]' "$DATA_FILE" 2>/dev/null)

  DESC=$(echo -e "${DESCS}\n" | rofi -dmenu -p "desc" -theme ~/.config/rofi/gastos.rasi)
  [ -z "$DESC" ] && exit 0

  MONTO=$(echo "" | rofi -dmenu -p "monto" -theme ~/.config/rofi/gastos.rasi)
  [ -z "$MONTO" ] && exit 0
  MONTO=$(echo "$MONTO" | tr ',' '.')

  if ! echo "$MONTO" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
    notify-send "gastos" "monto inválido: $MONTO"
    exit 1
  fi

  if jq -e --arg desc "$DESC" --argjson monto "$MONTO" '
    .items | any(.desc == $desc and .monto == $monto)
  ' "$DATA_FILE" >/dev/null 2>&1; then
    CONFIRMAR=$(echo -e "Si\nNo" | rofi -dmenu -p "Ya existe, agregar igual?" -theme ~/.config/rofi/gastos.rasi)
    [ "$CONFIRMAR" != "Si" ] && exit 0
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

list_gastos() {
  init_if_needed

  COUNT=$(jq -r '.items | length' "$DATA_FILE")
  [ "$COUNT" -eq 0 ] && notify-send "gastos" "No hay gastos este mes" && exit 0

  ITEMS=$(jq -r '.items | to_entries[] | "\(.key+1) │ $\(.value.monto)  \(.value.desc)"' "$DATA_FILE")

  SEL=$(echo -e "$ITEMS\n← Volver" | rofi -dmenu -p "gasto #" -theme ~/.config/rofi/gastos.rasi -i)
  [ -z "$SEL" ] || [ "$SEL" = "← Volver" ] && exit 0

  IDX=$(echo "$SEL" | cut -d'│' -f1 | tr -d ' ')
  [ -z "$IDX" ] && exit 0
  IDX=$((IDX - 1))

  ACCION=$(echo -e "✏ Cambiar desc\n✏ Cambiar monto\n🗑 Eliminar\n← Volver" | rofi -dmenu -p "accion" -theme ~/.config/rofi/gastos.rasi)
  case "$ACCION" in
    "✏ Cambiar desc")
      DESC_ACTUAL=$(jq -r ".items[$IDX].desc" "$DATA_FILE")
      NUEVA=$(echo "$DESC_ACTUAL" | rofi -dmenu -p "nueva desc" -theme ~/.config/rofi/gastos.rasi)
      [ -z "$NUEVA" ] && exit 0
      jq --arg desc "$NUEVA" ".items[$IDX].desc = \$desc" "$DATA_FILE" >/tmp/gastos_tmp.json && mv /tmp/gastos_tmp.json "$DATA_FILE"
      notify-send "gastos" "Descripción actualizada"
      ;;
    "✏ Cambiar monto")
      MONTO_ACTUAL=$(jq -r ".items[$IDX].monto" "$DATA_FILE")
      NUEVO=$(echo "$MONTO_ACTUAL" | rofi -dmenu -p "nuevo monto" -theme ~/.config/rofi/gastos.rasi)
      [ -z "$NUEVO" ] && exit 0
      NUEVO=$(echo "$NUEVO" | tr ',' '.')
      if ! echo "$NUEVO" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
        notify-send "gastos" "monto inválido"
        exit 1
      fi
      DIF=$((NUEVO - MONTO_ACTUAL))
      jq --argjson nuevo "$NUEVO" --argjson dif "$DIF" \
        ".items[$IDX].monto = \$nuevo | .total += \$dif" \
        "$DATA_FILE" >/tmp/gastos_tmp.json && mv /tmp/gastos_tmp.json "$DATA_FILE"
      notify-send "gastos" "Monto actualizado"
      ;;
    "🗑 Eliminar")
      CONFIRMAR=$(echo -e "No\nSi" | rofi -dmenu -p "¿eliminar?" -theme ~/.config/rofi/gastos.rasi)
      [ "$CONFIRMAR" != "Si" ] && exit 0
      MONTO_ELIM=$(jq -r ".items[$IDX].monto" "$DATA_FILE")
      jq --argjson monto "$MONTO_ELIM" \
        "del(.items[$IDX]) | .total -= \$monto" \
        "$DATA_FILE" >/tmp/gastos_tmp.json && mv /tmp/gastos_tmp.json "$DATA_FILE"
      notify-send "gastos" "Gasto eliminado"
      ;;
  esac
}

show_waybar() {
  init_if_needed
  jq -c '
    def fmt: if . >= 1000 then ((./1000 * 10 | floor / 10 | tostring) + "k") else tostring end;
    def tooltip: if (.items | length) > 0 then
      (.items | .[-5:] | reverse | map("\(.desc)  $\(.monto)  \(.fecha)") | join("\n"))
    else
      "Sin gastos"
    end;
    {text: (.total | fmt), tooltip: tooltip}
  ' "$DATA_FILE" || echo '{"text":"err","tooltip":"Error leyendo gastos"}'
}

case "$1" in
add)   add_gasto ;;
list)  list_gastos ;;
*)     show_waybar ;;
esac

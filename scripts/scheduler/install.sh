#!/usr/bin/env bash
# ── Instalador del CPU Scheduler personal ─────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/OneDrive/varios/scheduler"
echo ""
echo "  CPU Scheduler Personal — Instalador"
echo "  ─────────────────────────────────────"

# Crear directorios
mkdir -p "$BIN_DIR" "$DATA_DIR"

# Copiar script principal
cp "$SCRIPT_DIR/scheduler.py" "$BIN_DIR/scheduler"
chmod +x "$BIN_DIR/scheduler"
echo "  ✓ scheduler instalado en $BIN_DIR/scheduler"

# Inicializar tasks.json vacío si no existe
if [ ! -f "$DATA_DIR/tasks.json" ]; then
    echo "[]" > "$DATA_DIR/tasks.json"
    echo "  ✓ base de datos creada en $DATA_DIR/tasks.json"
fi

# Verificar que ~/.local/bin está en el PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "  ⚠  ~/.local/bin no está en tu PATH."
    echo "     Agregá esta línea a tu ~/.zshrc o ~/.bashrc:"
    echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "  ─────────────────────────────────────"
echo "  Próximos pasos:"
echo ""
echo "  1. Agregá el módulo a waybar config:"
echo "     cat $SCRIPT_DIR/config/waybar-config-snippet.jsonc"
echo ""
echo "  2. Agregá el CSS a tu waybar style.css:"
echo "     cat $SCRIPT_DIR/config/waybar-style.css"
echo ""
echo "  3. Agregá tu primera tarea:"
echo "     scheduler add"
echo ""
echo "  4. Reiniciá waybar:"
echo "     pkill waybar && waybar &"
echo ""
echo "  Comandos disponibles:"
echo "    scheduler tui          → vista completa"
echo "    scheduler add          → agregar tarea"
echo "    scheduler done <id>    → marcar completada"
echo "    scheduler delete <id>  → eliminar tarea"
echo "    scheduler waybar       → output para waybar (JSON)"
echo ""

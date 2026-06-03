#!/usr/bin/env python3
"""
pomodoro — Script de waybar para el timer pomodoro.

Comandos:
  pomodoro.py             → JSON para waybar
  pomodoro.py toggle      → play/pause
  pomodoro.py reset       → reiniciar timer actual
  pomodoro.py skip        → saltar al siguiente modo

Estado en /tmp/waybar-pomodoro:
  status|elapsed|mode|pomo_count|acreditado
"""

import json
import sys
import time
import subprocess
from pathlib import Path

WORK_MINS       = 30
BREAK_MINS      = 5
LONG_BREAK_MINS = 15

STATE_FILE = Path("/tmp/waybar-pomodoro")
TASKS_FILE = Path.home() / "OneDrive" / "varios" / "scheduler" / "tasks.json"


def leer_estado():
    try:
        partes = STATE_FILE.read_text().strip().split("|")
        if len(partes) == 3:
            status, elapsed, mode = partes
            return status, float(elapsed), mode, 0, 0
        if len(partes) == 4:
            status, elapsed, mode, pomo_count = partes
            return status, float(elapsed), mode, int(pomo_count), 0
        status, elapsed, mode, pomo_count, acreditado = partes
        return status, float(elapsed), mode, int(pomo_count), int(acreditado)
    except Exception:
        return "stopped", 0.0, "work", 0, 0

def escribir_estado(status, elapsed, mode, pomo_count, acreditado=0):
    STATE_FILE.write_text(f"{status}|{elapsed}|{mode}|{pomo_count}|{acreditado}")

def duracion_seg(mode):
    return {
        "work":       WORK_MINS * 60,
        "break":      BREAK_MINS * 60,
        "long_break": LONG_BREAK_MINS * 60,
    }.get(mode, WORK_MINS * 60)

def segundos_restantes(status, elapsed, mode):
    total = duracion_seg(mode)
    if status == "running":
        spent = time.time() - elapsed
    elif status == "paused":
        spent = elapsed
    else:
        spent = 0
    return max(0, int(total - spent))

def tarea_en_foco():
    try:
        content = TASKS_FILE.read_text().strip()
        if not content:
            return None
        for t in json.loads(content):
            if t.get("estado") == "en_foco":
                return t
    except Exception:
        pass
    return None

def refrescar_waybar():
    try:
        subprocess.run(["pkill", "-SIGRTMIN+8", "waybar"], check=False, capture_output=True)
    except FileNotFoundError:
        pass


# ── Comandos ───────────────────────────────────────────────────────────────────
def cmd_toggle():
    status, elapsed, mode, pomo_count, acreditado = leer_estado()
    now = time.time()
    if status == "stopped":
        escribir_estado("running", now, mode, pomo_count, acreditado)
    elif status == "paused":
        # Reanudar: reconstruir el unix timestamp de inicio
        # elapsed contiene segundos transcurridos; acreditado los ya sumados al daemon
        adjusted = now - elapsed
        escribir_estado("running", adjusted, mode, pomo_count, acreditado)
    else:
        # Pausar: guardar segundos transcurridos para que el daemon sepa cuánto acreditar
        spent = now - elapsed
        escribir_estado("paused", spent, mode, pomo_count, acreditado)
    refrescar_waybar()

def cmd_reset():
    status, elapsed, mode, pomo_count, acreditado = leer_estado()
    escribir_estado("stopped", 0, mode, pomo_count, 0)
    refrescar_waybar()

def cmd_skip():
    status, elapsed, mode, pomo_count, acreditado = leer_estado()
    siguiente = {"work": "break", "break": "long_break", "long_break": "work"}.get(mode, "work")
    escribir_estado("stopped", 0, siguiente, pomo_count, 0)
    refrescar_waybar()

def cmd_waybar():
    status, elapsed, mode, pomo_count, acreditado = leer_estado()
    restantes = segundos_restantes(status, elapsed, mode)

    mins = restantes // 60
    secs = restantes % 60
    time_str = f"{mins:02d}:{secs:02d}"

    iconos_modo   = {"work": "󰔛", "break": "󰅶", "long_break": "󰒲"}
    iconos_estado = {"running": "▶", "paused": "⏸", "stopped": "⏹"}
    labels_modo   = {"work": "Trabajo", "break": "Descanso", "long_break": "Descanso largo"}

    text = f"{iconos_modo.get(mode,'󰔛')} {iconos_estado.get(status,'⏹')} {time_str}"

    tooltip_lines = [
        f"<b>{labels_modo.get(mode, mode)}</b>  ·  #{pomo_count} completados",
        f"{time_str} restantes",
    ]

    foco = tarea_en_foco()
    if foco and mode == "work":
        nombre = foco["name"][:40]
        acum   = round(foco.get("minutos_acumulados", 0))
        tooltip_lines.append(f"\n<b>En foco:</b> {nombre}")
        tooltip_lines.append(f"Acumulado: {acum} min")
    elif mode == "work":
        tooltip_lines.append("\n<i>Sin tarea en foco — el tiempo no se registra</i>")

    css_class = "running" if status == "running" else status
    print(json.dumps({
        "text":    text,
        "tooltip": "\n".join(tooltip_lines),
        "class":   css_class,
    }))


def main():
    args = sys.argv[1:]
    cmd  = args[0] if args else "waybar"
    if cmd == "toggle":   cmd_toggle()
    elif cmd == "reset":  cmd_reset()
    elif cmd == "skip":   cmd_skip()
    else:                 cmd_waybar()

if __name__ == "__main__":
    main()

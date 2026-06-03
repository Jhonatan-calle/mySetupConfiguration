#!/usr/bin/env python3
"""
pomodoro-daemon — Daemon del timer pomodoro.
Ejecutado por Hyprland al inicio (exec-once).

Funciones:
  - Avanza el timer pomodoro segundo a segundo
  - Al completar un bloque de trabajo, suma los minutos a la tarea en_foco
  - Notifica al completar cada bloque
  - Auto-avanza work → break → work

Estado compartido con waybar: /tmp/waybar-pomodoro
  formato: status|elapsed|mode
    status:  running | paused | stopped
    elapsed: unix timestamp si running, segundos transcurridos si paused, 0 si stopped
    mode:    work | break | long_break
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
WORK_MINS = 30
BREAK_MINS = 5
LONG_BREAK_MINS = 15
POMODOROS_ANTES_LARGO = 4  # cada cuántos work → long_break

STATE_FILE = Path("/tmp/waybar-pomodoro")
PIDFILE = Path("/tmp/waybar-pomodoro-daemon.pid")
TASKS_FILE = Path.home() / "OneDrive" / "varios" / "scheduler" / "tasks.json"


# ── Persistencia mínima ────────────────────────────────────────────────────────
def leer_estado():
    try:
        partes = STATE_FILE.read_text().strip().split("|")
        if len(partes) != 4:
            raise ValueError
        status, elapsed, mode, pomo_count = partes
        return status, float(elapsed), mode, int(pomo_count)
    except Exception:
        return "stopped", 0.0, "work", 0


def escribir_estado(status, elapsed, mode, pomo_count):
    STATE_FILE.write_text(f"{status}|{elapsed}|{mode}|{pomo_count}")


def leer_tareas():
    try:
        content = TASKS_FILE.read_text().strip()
        if not content:
            return []
        return json.loads(content)
    except Exception:
        return []


def guardar_tareas(tareas):
    try:
        TASKS_FILE.write_text(json.dumps(tareas, indent=2, ensure_ascii=False))
    except Exception:
        pass


def tarea_en_foco(tareas):
    for t in tareas:
        if t.get("estado") == "en_foco":
            return t
    return None


# ── Notificaciones ─────────────────────────────────────────────────────────────
def notificar(titulo, cuerpo, urgencia="normal"):
    try:
        subprocess.run(
            ["notify-send", "-u", urgencia, titulo, cuerpo],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass


def refrescar_waybar():
    try:
        subprocess.run(
            ["pkill", "-SIGRTMIN+8", "waybar"], check=False, capture_output=True
        )
    except FileNotFoundError:
        pass


# ── Lógica al completar un bloque ─────────────────────────────────────────────
def completar_bloque(mode, pomo_count):
    """
    Llamado cuando el timer llega a 0.
    - Si era work: acumula minutos en la tarea en_foco, avanza a break
    - Si era break/long_break: avanza a work
    Retorna el nuevo (mode, pomo_count).
    """
    if mode == "work":
        # Acumular minutos en la tarea en_foco
        tareas = leer_tareas()
        foco = tarea_en_foco(tareas)
        if foco is not None:
            foco["minutos_acumulados"] = foco.get("minutos_acumulados", 0) + WORK_MINS
            guardar_tareas(tareas)
            nombre = foco["name"][:35]
            notificar(
                "󰔛 Pomodoro completado",
                f"{nombre}\n+{WORK_MINS} min acumulados",
                "normal",
            )
        else:
            notificar("󰔛 Pomodoro completado", "¡A descansar!", "normal")

        pomo_count += 1
        if pomo_count % POMODOROS_ANTES_LARGO == 0:
            nuevo_mode = "long_break"
            notificar(
                "󰒲 Descanso largo", f"{LONG_BREAK_MINS} min — te lo ganaste", "low"
            )
        else:
            nuevo_mode = "break"
            notificar("󰅶 Descanso corto", f"{BREAK_MINS} min", "low")

    else:
        # Fin de break → volver a trabajo
        nuevo_mode = "work"
        notificar("󰔛 ¡A trabajar!", f"Pomodoro #{pomo_count + 1}", "normal")

    return nuevo_mode, pomo_count


# ── Loop principal ─────────────────────────────────────────────────────────────
def duracion_seg(mode):
    return {
        "work": WORK_MINS * 60,
        "break": BREAK_MINS * 60,
        "long_break": LONG_BREAK_MINS * 60,
    }.get(mode, WORK_MINS * 60)


def main():
    # Evitar instancias duplicadas
    if PIDFILE.exists():
        try:
            pid = int(PIDFILE.read_text().strip())
            os.kill(pid, 0)  # lanza OSError si no existe
            print(f"Daemon ya corriendo (PID {pid})")
            sys.exit(1)
        except (OSError, ValueError):
            pass  # proceso muerto, continuar
    PIDFILE.write_text(str(os.getpid()))

    def cleanup(sig=None, frame=None):
        PIDFILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # Inicializar estado si no existe o es formato viejo (3 campos)
    try:
        partes = STATE_FILE.read_text().strip().split("|")
        if len(partes) < 4:
            escribir_estado("stopped", 0, "work", 0)
    except Exception:
        escribir_estado("stopped", 0, "work", 0)

    ultimo_refresh = 0

    try:
        while True:
            status, elapsed, mode, pomo_count = leer_estado()

            if status == "running":
                now = time.time()
                total = duracion_seg(mode)
                spent = now - elapsed  # elapsed es unix timestamp cuando running

                if spent >= total:
                    nuevo_mode, pomo_count = completar_bloque(mode, pomo_count)
                    # Auto-arrancar el siguiente modo
                    escribir_estado("stopped", 0, nuevo_mode, pomo_count)
                    refrescar_waybar()
                else:
                    # Refrescar waybar cada 30s para actualizar countdown
                    if now - ultimo_refresh >= 30:
                        refrescar_waybar()
                        ultimo_refresh = now

            time.sleep(1)

    finally:
        cleanup()


if __name__ == "__main__":
    main()

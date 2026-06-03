#!/usr/bin/env python3
"""
pomodoro-daemon — Daemon del timer pomodoro.
Ejecutado por Hyprland al inicio (exec-once).

Funciones:
  - Avanza el timer pomodoro segundo a segundo
  - Acredita minutos a la tarea en_foco en tiempo real (no solo al completar)
  - Al pausar: acredita los minutos transcurridos desde la última acreditación
  - Al completar un bloque work: acredita el resto y notifica
  - Notifica al completar cada bloque

Estado compartido: /tmp/waybar-pomodoro
  status|elapsed|mode|pomo_count|acreditado
    status:      running | paused | stopped
    elapsed:     unix timestamp si running, segundos transcurridos si paused/stopped
    mode:        work | break | long_break
    pomo_count:  pomodoros de trabajo completados
    acreditado:  segundos ya sumados a la tarea en el ciclo actual (reset en cada nuevo bloque)
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

WORK_MINS             = 30
BREAK_MINS            = 5
LONG_BREAK_MINS       = 15
POMODOROS_ANTES_LARGO = 4
ACREDITAR_CADA_SEG    = 60   # acreditar en la tarea cada 60s mientras corre

STATE_FILE = Path("/tmp/waybar-pomodoro")
PIDFILE    = Path("/tmp/waybar-pomodoro-daemon.pid")
TASKS_FILE = Path.home() / "OneDrive" / "varios" / "scheduler" / "tasks.json"


# ── Estado ─────────────────────────────────────────────────────────────────────
def leer_estado():
    try:
        partes = STATE_FILE.read_text().strip().split("|")
        # Migrar formatos viejos
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


# ── Tareas ─────────────────────────────────────────────────────────────────────
def leer_tareas():
    try:
        content = TASKS_FILE.read_text().strip()
        return json.loads(content) if content else []
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


# ── Acreditación ───────────────────────────────────────────────────────────────
def acreditar_minutos(segundos):
    """
    Suma `segundos` a minutos_acumulados de la tarea en_foco.
    Solo actúa si hay tarea en foco y segundos > 0.
    Retorna los segundos efectivamente acreditados.
    """
    if segundos <= 0:
        return 0
    tareas = leer_tareas()
    foco   = tarea_en_foco(tareas)
    if foco is None:
        return 0
    mins = segundos / 60
    foco["minutos_acumulados"] = round(
        foco.get("minutos_acumulados", 0) + mins, 2
    )
    guardar_tareas(tareas)
    return segundos


# ── Notificaciones ─────────────────────────────────────────────────────────────
def notificar(titulo, cuerpo, urgencia="normal"):
    try:
        subprocess.run(
            ["notify-send", "-u", urgencia, titulo, cuerpo],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass

def refrescar_waybar():
    try:
        subprocess.run(["pkill", "-SIGRTMIN+8", "waybar"], check=False, capture_output=True)
    except FileNotFoundError:
        pass


# ── Completar bloque ───────────────────────────────────────────────────────────
def completar_bloque(mode, pomo_count, spent_seg, acreditado_seg):
    """
    Llamado cuando el timer llega a 0.
    Acredita los segundos finales aún no acreditados, luego avanza de modo.
    """
    if mode == "work":
        # Acreditar lo que faltaba
        pendiente = spent_seg - acreditado_seg
        acreditar_minutos(pendiente)

        tareas = leer_tareas()
        foco   = tarea_en_foco(tareas)
        if foco:
            nombre = foco["name"][:35]
            acum   = round(foco.get("minutos_acumulados", 0))
            notificar("󰔛 Pomodoro completado", f"{nombre}\n{acum} min acumulados", "normal")
        else:
            notificar("󰔛 Pomodoro completado", "¡A descansar!", "normal")

        pomo_count += 1
        if pomo_count % POMODOROS_ANTES_LARGO == 0:
            nuevo_mode = "long_break"
            notificar("󰒲 Descanso largo", f"{LONG_BREAK_MINS} min — te lo ganaste", "low")
        else:
            nuevo_mode = "break"
            notificar("󰅶 Descanso corto", f"{BREAK_MINS} min", "low")
    else:
        nuevo_mode = "work"
        notificar("󰔛 ¡A trabajar!", f"Pomodoro #{pomo_count + 1}", "normal")

    return nuevo_mode, pomo_count


# ── Duración ───────────────────────────────────────────────────────────────────
def duracion_seg(mode):
    return {
        "work":       WORK_MINS * 60,
        "break":      BREAK_MINS * 60,
        "long_break": LONG_BREAK_MINS * 60,
    }.get(mode, WORK_MINS * 60)


# ── Loop principal ─────────────────────────────────────────────────────────────
def main():
    if PIDFILE.exists():
        try:
            pid = int(PIDFILE.read_text().strip())
            os.kill(pid, 0)
            print(f"Daemon ya corriendo (PID {pid})")
            sys.exit(1)
        except (OSError, ValueError):
            pass
    PIDFILE.write_text(str(os.getpid()))

    def cleanup(sig=None, frame=None):
        PIDFILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT,  cleanup)

    try:
        partes = STATE_FILE.read_text().strip().split("|")
        if len(partes) < 5:
            escribir_estado("stopped", 0, "work", 0, 0)
    except Exception:
        escribir_estado("stopped", 0, "work", 0, 0)

    status_anterior  = None
    ultimo_refresh   = 0

    try:
        while True:
            status, elapsed, mode, pomo_count, acreditado = leer_estado()
            now = time.time()

            if status == "running":
                total   = duracion_seg(mode)
                spent   = now - elapsed   # elapsed es unix timestamp

                if spent >= total:
                    # Bloque completado
                    nuevo_mode, pomo_count = completar_bloque(
                        mode, pomo_count, int(total), acreditado
                    )
                    escribir_estado("stopped", 0, nuevo_mode, pomo_count, 0)
                    refrescar_waybar()

                elif mode == "work":
                    # Acreditar en intervalos mientras corre
                    pendiente = int(spent) - acreditado
                    if pendiente >= ACREDITAR_CADA_SEG:
                        acreditados = acreditar_minutos(pendiente)
                        if acreditados:
                            acreditado += acreditados
                            escribir_estado(status, elapsed, mode, pomo_count, acreditado)

                    # Refrescar waybar cada 30s
                    if now - ultimo_refresh >= 30:
                        refrescar_waybar()
                        ultimo_refresh = now

            elif status == "paused" and status_anterior == "running":
                # Acaba de pausar — acreditar lo transcurrido no acreditado aún
                if mode == "work":
                    # elapsed ahora contiene segundos transcurridos (lo setea pomodoro.py)
                    pendiente = int(elapsed) - acreditado
                    acreditados = acreditar_minutos(pendiente)
                    if acreditados:
                        nuevo_acreditado = acreditado + acreditados
                        escribir_estado(status, elapsed, mode, pomo_count, nuevo_acreditado)
                        refrescar_waybar()

            status_anterior = status
            time.sleep(1)

    finally:
        cleanup()


if __name__ == "__main__":
    main()

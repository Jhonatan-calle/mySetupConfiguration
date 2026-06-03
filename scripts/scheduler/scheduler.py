#!/usr/bin/env python3
"""
CPU Scheduler personal — EDF con ciclo de vida completo.

CICLO DE VIDA DE TAREA:
  inbox → backlog → active → done | dropped

COMANDOS:
  scheduler.py                        → waybar JSON (tarea activa o en foco)
  scheduler.py waybar                 → ídem
  scheduler.py tui                    → vista completa en terminal
  scheduler.py add                    → agregar tarea al INBOX
  scheduler.py process                → procesar tareas del INBOX (clasificar)
  scheduler.py plan                   → armar el Plan Diario desde el BACKLOG
  scheduler.py plan show              → mostrar el plan de hoy
  scheduler.py plan lock              → cerrar el plan (no acepta más tareas)
  scheduler.py focus start <id> [min] → iniciar bloque de foco (default 90 min)
  scheduler.py focus end <id>         → cerrar bloque de foco
  scheduler.py focus status           → ver bloque activo
  scheduler.py done <id>              → marcar tarea como completada
  scheduler.py drop <id>              → descartar tarea conscientemente
  scheduler.py eod                    → cierre de día (sweep de activas sin completar)
  scheduler.py delete <id>            → eliminar tarea (solo inbox/backlog)
  scheduler.py history                → historial de bloques de foco
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
import subprocess

# ── Configuración ──────────────────────────────────────────────────────────────
BASE_DIR = Path.home() / "OneDrive" / "varios" / "scheduler"
BASE_DIR.mkdir(parents=True, exist_ok=True)

TASKS_FILE     = BASE_DIR / "tasks.json"
PLAN_FILE      = BASE_DIR / "daily_plan.json"
FOCUS_FILE     = BASE_DIR / "focus_blocks.json"   # historial de bloques

# Tipos de tarea (reemplaza "categoría" como clasificador de peso)
TASK_TYPES = {
    "critica":   5,   # proyecto/app principal — máximo peso
    "intensiva": 3,   # estudio profundo, aprendizaje activo
    "fondo":     1,   # tareas administrativas, lectura ligera
}

# Peso base por categoría (dominio del contenido)
CATEGORY_WEIGHTS = {
    "universidad": 1,
    "software":    4,
    "learning":    3,
    "personal":    2,
}

CATEGORY_ICONS = {
    "universidad": "󰑴",
    "software":    "󰲋",
    "personal":    "󰋙",
    "trabajo":     "󰢮",
    "learning":    "󰿄",
}

TASK_TYPE_ICONS = {
    "critica":   "🔴",
    "intensiva": "🟡",
    "fondo":     "🟢",
}

# Slots del Plan Diario
PLAN_SLOTS = {
    "principal":   1,   # solo 1 tarea crítica/intensiva pesada
    "secundarias": 3,   # hasta 3 tareas de cualquier tipo
}

C = {
    "red":    "\033[91m",
    "yellow": "\033[93m",
    "green":  "\033[92m",
    "blue":   "\033[94m",
    "cyan":   "\033[96m",
    "magenta":"\033[95m",
    "gray":   "\033[90m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

# ── Persistencia ───────────────────────────────────────────────────────────────
def load_tasks():
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE) as f:
        return json.load(f)

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

def load_plan():
    if not PLAN_FILE.exists():
        return None
    with open(PLAN_FILE) as f:
        return json.load(f)

def save_plan(plan):
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

def load_focus_history():
    if not FOCUS_FILE.exists():
        return []
    with open(FOCUS_FILE) as f:
        return json.load(f)

def save_focus_history(history):
    with open(FOCUS_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def next_id(tasks):
    return max((t["id"] for t in tasks), default=0) + 1

# ── Plan Diario ────────────────────────────────────────────────────────────────
def get_today_plan():
    """Retorna el plan de hoy, o None si no existe o es de otro día."""
    plan = load_plan()
    if not plan:
        return None
    if plan.get("date") != date.today().isoformat():
        return None
    return plan

def create_plan(principal_id, secondary_ids, tasks):
    """Crea un Plan Diario nuevo para hoy."""
    today = date.today().isoformat()
    plan = {
        "date":         today,
        "locked":       False,
        "principal":    principal_id,
        "secundarias":  secondary_ids,
        "created_at":   datetime.now().isoformat(),
    }
    save_plan(plan)

    # Mover tareas asignadas a ACTIVE
    for t in tasks:
        if t["id"] in ([principal_id] + secondary_ids):
            t["status"] = "active"
            t["activated_date"] = today
    save_tasks(tasks)
    return plan

def is_plan_locked():
    plan = get_today_plan()
    return plan is not None and plan.get("locked", False)

def get_active_focus_block(tasks):
    """Retorna la tarea que está actualmente in_progress, si existe."""
    for t in tasks:
        if t.get("status") == "in_progress":
            return t
    return None

# ── Algoritmo de scheduling ────────────────────────────────────────────────────
def days_until(deadline_str):
    if not deadline_str:
        return 999
    deadline = date.fromisoformat(deadline_str)
    delta = (deadline - date.today()).days
    return delta if delta != 0 else 0.5

def is_blocked(task, tasks):
    for dep_id in task.get("depends_on", []):
        dep = next((t for t in tasks if t["id"] == dep_id), None)
        if dep and dep["status"] not in ("done", "dropped"):
            return True
    return False

def compute_priority(task, tasks):
    """
    P = (urgencia * tipo_peso * categoria_peso * distance_penalty) / max(días, 0.1)
    Solo aplica a tareas en backlog o active. inbox/done/dropped → 0.
    """
    if task["status"] in ("done", "dropped", "inbox"):
        return 0
    if is_blocked(task, tasks):
        return 0

    days         = days_until(task.get("deadline"))
    urgency_base = task.get("urgency", 5)
    tipo_weight  = TASK_TYPES.get(task.get("task_type", "fondo"), 1)
    cat_weight   = CATEGORY_WEIGHTS.get(task.get("category", "personal"), 1.0)

    # Excepción universidad: suprimir si no es urgente y hay otras tareas
    if task.get("category") == "universidad" and days > 7 and urgency_base <= 6:
        otras = [
            t for t in tasks
            if t["id"] != task["id"]
            and t["status"] not in ("done", "dropped", "inbox")
            and t.get("category") != "universidad"
        ]
        if otras:
            return 0

    distance_penalty = min(1.0, 30 / days) if days > 30 else 1.0
    priority = (urgency_base * tipo_weight * cat_weight * distance_penalty) / max(days, 0.1)

    if 0 < days <= 7:
        priority *= 1.5

    return round(priority, 4)

def get_sorted_backlog(tasks):
    backlog = [t for t in tasks if t["status"] in ("backlog", "active")]
    return sorted(backlog, key=lambda t: compute_priority(t, tasks), reverse=True)

def get_top_task(tasks):
    """Tarea con mayor prioridad del plan de hoy, o del backlog si no hay plan."""
    plan = get_today_plan()
    if plan:
        plan_ids = [plan["principal"]] + plan["secundarias"]
        active = [t for t in tasks if t["id"] in plan_ids and t["status"] in ("active", "in_progress")]
        if active:
            return sorted(active, key=lambda t: compute_priority(t, tasks), reverse=True)[0]
    # Fallback: top del backlog
    sorted_b = get_sorted_backlog(tasks)
    for t in sorted_b:
        if not is_blocked(t, tasks):
            return t
    return None

# ── Comandos ───────────────────────────────────────────────────────────────────
def cmd_add():
    """Agrega una tarea al INBOX — mínima fricción, solo nombre requerido."""
    tasks = load_tasks()

    print(f"\n{C['bold']}  Nueva tarea → INBOX{C['reset']}")
    print(f"{C['gray']}  Solo nombre requerido. Clasificar después con `process`.{C['reset']}\n")

    name = input("  Nombre: ").strip()
    if not name:
        print("  Nombre requerido.")
        return

    notes = input("  Notas rápidas (opcional): ").strip() or None

    task = {
        "id":      next_id(tasks),
        "name":    name,
        "notes":   notes,
        "status":  "inbox",
        "created": date.today().isoformat(),
        # Estos campos se completan en `process`:
        "category":  None,
        "task_type": None,
        "deadline":  None,
        "urgency":   5,
        "depends_on": [],
    }
    tasks.append(task)
    save_tasks(tasks)
    print(f"\n  {C['cyan']}→ [{task['id']}] '{name}' en INBOX{C['reset']}\n")


def cmd_process():
    """Procesa tareas del INBOX: las clasifica y mueve al BACKLOG."""
    tasks = load_tasks()
    inbox = [t for t in tasks if t["status"] == "inbox"]

    if not inbox:
        print(f"\n  {C['green']}INBOX vacío 🎉{C['reset']}\n")
        return

    print(f"\n{C['bold']}  Procesando INBOX ({len(inbox)} tarea/s){C['reset']}")
    print(f"{C['gray']}  Clasificá cada tarea para moverla al BACKLOG.{C['reset']}\n")

    for task in inbox:
        print(f"{C['bold']}  [{task['id']}] {task['name']}{C['reset']}")
        if task.get("notes"):
            print(f"  {C['gray']}  Nota: {task['notes']}{C['reset']}")

        action = input("  [b]acklog / [d]rop / [s]kip: ").strip().lower()
        if action == "d":
            task["status"] = "dropped"
            task["dropped"] = date.today().isoformat()
            task["drop_reason"] = input("  Motivo del descarte: ").strip() or "sin motivo"
            print(f"  {C['gray']}  → DROPPED{C['reset']}")
            continue
        elif action == "s":
            print(f"  {C['gray']}  → Saltada{C['reset']}")
            continue

        # Clasificar para BACKLOG
        while True:
            print(f"  Tipo [{'/'.join(TASK_TYPES.keys())}]: ", end="")
            task_type = input().strip().lower() or "fondo"
            if task_type in TASK_TYPES:
                break
            print("  Tipo inválido.")

        while True:
            print(f"  Categoría [{'/'.join(CATEGORY_WEIGHTS.keys())}]: ", end="")
            category = input().strip().lower() or "personal"
            if category in CATEGORY_WEIGHTS:
                break
            print("  Categoría inválida.")

        while True:
            deadline = input("  Deadline (YYYY-MM-DD, opcional): ").strip()
            if not deadline:
                deadline = None
                break
            try:
                date.fromisoformat(deadline)
                break
            except ValueError:
                print("  Fecha inválida.")

        urgency_raw = input("  Urgencia 1-10 [5]: ").strip() or "5"
        try:
            urgency = max(1, min(10, int(urgency_raw)))
        except ValueError:
            urgency = 5

        # Dependencias opcionales
        backlog_tasks = [t for t in tasks if t["status"] in ("backlog", "active") and t["id"] != task["id"]]
        if backlog_tasks:
            print(f"\n  {C['gray']}Tareas en backlog:{C['reset']}")
            for bt in backlog_tasks:
                print(f"    [{bt['id']}] {bt['name']}")
        dep_raw = input("  Depende de (IDs separados por coma, opcional): ").strip()
        depends_on = []
        if dep_raw:
            try:
                depends_on = [int(x.strip()) for x in dep_raw.split(",")]
            except ValueError:
                pass

        task.update({
            "status":     "backlog",
            "task_type":  task_type,
            "category":   category,
            "deadline":   deadline,
            "urgency":    urgency,
            "depends_on": depends_on,
            "processed":  date.today().isoformat(),
        })
        p = compute_priority(task, tasks)
        print(f"  {C['green']}  → BACKLOG (prioridad: {p:.3f}){C['reset']}\n")

    save_tasks(tasks)


def cmd_plan(sub=None):
    """Gestión del Plan Diario."""
    tasks = load_tasks()

    if sub == "show":
        _plan_show(tasks)
        return
    if sub == "lock":
        _plan_lock(tasks)
        return

    # Armar plan
    existing = get_today_plan()
    if existing and existing.get("locked"):
        print(f"\n  {C['red']}El plan de hoy ya está cerrado.{C['reset']}")
        print(f"  Usá `eod` al terminar el día para reiniciarlo.\n")
        return

    backlog = [t for t in tasks if t["status"] == "backlog" and not is_blocked(t, tasks)]
    if not backlog:
        print(f"\n  {C['yellow']}No hay tareas en el BACKLOG para planificar.{C['reset']}\n")
        return

    sorted_b = sorted(backlog, key=lambda t: compute_priority(t, tasks), reverse=True)

    print(f"\n{C['bold']}  Armando Plan Diario — {date.today().isoformat()}{C['reset']}")
    print(f"{C['gray']}  1 tarea principal + hasta 3 secundarias.{C['reset']}\n")

    print(f"{C['bold']}  BACKLOG por prioridad:{C['reset']}")
    for t in sorted_b:
        p = compute_priority(t, tasks)
        tipo_icon = TASK_TYPE_ICONS.get(t.get("task_type", "fondo"), "?")
        cat_icon  = CATEGORY_ICONS.get(t.get("category", "personal"), "?")
        days      = days_until(t.get("deadline"))
        d_str     = f"{int(days)}d" if t.get("deadline") else "∞"
        print(f"  [{t['id']}] {tipo_icon}{cat_icon} {t['name']}  {C['gray']}[{d_str}] p={p:.3f}{C['reset']}")

    print()

    # Slot principal (solo critica o intensiva)
    while True:
        pid_raw = input(f"  {C['bold']}Tarea PRINCIPAL{C['reset']} (ID, solo critica/intensiva): ").strip()
        try:
            pid = int(pid_raw)
            principal = next((t for t in sorted_b if t["id"] == pid), None)
            if not principal:
                print("  ID no encontrado en backlog.")
                continue
            if principal.get("task_type") == "fondo":
                print(f"  {C['yellow']}  ⚠ Slot principal rechaza tareas de tipo 'fondo'.{C['reset']}")
                override = input("  ¿Forzar igualmente? [s/N]: ").strip().lower()
                if override != "s":
                    continue
            break
        except ValueError:
            print("  Ingresá un ID numérico.")

    # Slots secundarios
    secondary_ids = []
    remaining = [t for t in sorted_b if t["id"] != pid]
    print(f"\n  Tareas SECUNDARIAS (hasta {PLAN_SLOTS['secundarias']}, Enter para terminar):")
    for i in range(PLAN_SLOTS["secundarias"]):
        sid_raw = input(f"  Secundaria {i+1} (ID o Enter para omitir): ").strip()
        if not sid_raw:
            break
        try:
            sid = int(sid_raw)
            if any(t["id"] == sid for t in remaining):
                secondary_ids.append(sid)
            else:
                print("  ID no válido, omitido.")
        except ValueError:
            print("  ID inválido, omitido.")

    plan = create_plan(pid, secondary_ids, tasks)
    total = 1 + len(secondary_ids)
    print(f"\n  {C['green']}✓ Plan creado con {total} tarea/s activas.{C['reset']}")
    print(f"  {C['gray']}Usá `plan lock` cuando empieces el día.{C['reset']}\n")


def _plan_show(tasks):
    plan = get_today_plan()
    if not plan:
        print(f"\n  {C['yellow']}No hay plan para hoy. Usá `plan` para crearlo.{C['reset']}\n")
        return

    locked_str = f"{C['red']}CERRADO{C['reset']}" if plan.get("locked") else f"{C['green']}abierto{C['reset']}"
    print(f"\n{C['bold']}  Plan Diario — {plan['date']}  [{locked_str}{C['bold']}]{C['reset']}")
    print(f"{C['gray']}{'─' * 50}{C['reset']}")

    all_ids = [plan["principal"]] + plan["secundarias"]
    for i, tid in enumerate(all_ids):
        t = next((x for x in tasks if x["id"] == tid), None)
        if not t:
            continue
        slot_label = "PRINCIPAL" if i == 0 else f"SEC {i}"
        tipo_icon  = TASK_TYPE_ICONS.get(t.get("task_type", "fondo"), "?")
        status_color = {
            "active":      C["cyan"],
            "in_progress": C["yellow"],
            "done":        C["green"],
            "dropped":     C["gray"],
        }.get(t["status"], C["reset"])
        print(f"  {C['gray']}{slot_label}{C['reset']}  {tipo_icon} {status_color}[{t['id']}] {t['name']}{C['reset']}  {C['gray']}({t['status']}){C['reset']}")

    focus = get_active_focus_block(tasks)
    if focus:
        elapsed = _focus_elapsed(focus)
        print(f"\n  {C['yellow']}⚡ EN FOCO: [{focus['id']}] {focus['name']}  ({elapsed} min transcurridos){C['reset']}")
    print()


def _plan_lock(tasks):
    plan = get_today_plan()
    if not plan:
        print(f"\n  {C['yellow']}No hay plan para hoy.{C['reset']}\n")
        return
    if plan.get("locked"):
        print(f"\n  Plan ya está cerrado.\n")
        return
    plan["locked"] = True
    plan["locked_at"] = datetime.now().isoformat()
    save_plan(plan)
    print(f"\n  {C['green']}✓ Plan cerrado. No se pueden agregar más tareas hoy.{C['reset']}\n")


def _focus_elapsed(task):
    """Minutos transcurridos desde que empezó el bloque de foco."""
    started = task.get("focus_started")
    if not started:
        return 0
    delta = datetime.now() - datetime.fromisoformat(started)
    return int(delta.total_seconds() / 60)


# ── Focus Blocks ───────────────────────────────────────────────────────────────
def cmd_focus(sub, args):
    tasks = load_tasks()

    if sub == "start":
        if not args:
            print("  Uso: focus start <id> [minutos]")
            return
        try:
            tid = int(args[0])
            duration = int(args[1]) if len(args) > 1 else 90
        except ValueError:
            print("  ID o duración inválidos.")
            return

        # Solo una tarea puede estar in_progress a la vez
        current_focus = get_active_focus_block(tasks)
        if current_focus:
            print(f"\n  {C['red']}Ya hay un bloque activo: [{current_focus['id']}] {current_focus['name']}{C['reset']}")
            print(f"  Cerralo primero con `focus end {current_focus['id']}`\n")
            return

        target = next((t for t in tasks if t["id"] == tid), None)
        if not target:
            print(f"  Tarea {tid} no encontrada.")
            return
        if target["status"] not in ("active", "backlog"):
            print(f"  {C['yellow']}La tarea debe estar ACTIVE o BACKLOG para iniciar foco (estado actual: {target['status']}).{C['reset']}")
            return

        prev_status = target["status"]
        target["status"] = "in_progress"
        target["focus_started"] = datetime.now().isoformat()
        target["focus_duration"] = duration
        target["_prev_status"] = prev_status
        save_tasks(tasks)

        ends_at = (datetime.now() + timedelta(minutes=duration)).strftime("%H:%M")
        print(f"\n  {C['yellow']}⚡ FOCO iniciado: [{tid}] {target['name']}{C['reset']}")
        print(f"  {C['gray']}Duración: {duration} min  |  Termina ~{ends_at}{C['reset']}\n")

    elif sub == "end":
        if not args:
            print("  Uso: focus end <id>")
            return
        try:
            tid = int(args[0])
        except ValueError:
            print("  ID inválido.")
            return

        target = next((t for t in tasks if t["id"] == tid), None)
        if not target or target["status"] != "in_progress":
            print(f"  Tarea {tid} no está en foco.")
            return

        elapsed = _focus_elapsed(target)
        print(f"\n  Bloque de foco: [{tid}] {target['name']}  ({elapsed} min)")
        outcome = input("  ¿Resultado? [d]one / [c]ontinúa mañana / [a]ctive (necesita más hoy): ").strip().lower()

        # Guardar en historial
        history = load_focus_history()
        history.append({
            "task_id":   tid,
            "task_name": target["name"],
            "date":      date.today().isoformat(),
            "started":   target.get("focus_started"),
            "ended":     datetime.now().isoformat(),
            "elapsed_min": elapsed,
            "planned_min": target.get("focus_duration", 90),
            "outcome":   outcome,
        })
        save_focus_history(history)

        # Limpiar campos de foco
        target.pop("focus_started", None)
        target.pop("focus_duration", None)
        prev = target.pop("_prev_status", "active")

        if outcome == "d":
            target["status"] = "done"
            target["completed"] = date.today().isoformat()
            print(f"  {C['green']}✓ [{tid}] '{target['name']}' completada 🎉{C['reset']}")
            _show_unblocked(tid, tasks)
        elif outcome == "c":
            target["status"] = "backlog"
            target.pop("activated_date", None)
            print(f"  {C['cyan']}→ Vuelve al BACKLOG para mañana.{C['reset']}")
        else:
            target["status"] = prev if prev in ("active", "backlog") else "active"
            print(f"  {C['cyan']}→ Sigue ACTIVE para otro bloque hoy.{C['reset']}")

        save_tasks(tasks)
        print()

    elif sub == "status":
        focus = get_active_focus_block(tasks)
        if not focus:
            print(f"\n  {C['gray']}No hay bloque de foco activo.{C['reset']}\n")
        else:
            elapsed  = _focus_elapsed(focus)
            planned  = focus.get("focus_duration", 90)
            remaining = max(0, planned - elapsed)
            pct = min(100, int(elapsed / planned * 100))
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"\n  {C['yellow']}⚡ EN FOCO: [{focus['id']}] {focus['name']}{C['reset']}")
            print(f"  [{bar}] {pct}%  |  {elapsed}/{planned} min  |  {remaining} min restantes\n")

    else:
        print("  Uso: focus start <id> [min] | focus end <id> | focus status")

    subprocess.run(["pkill", "-SIGRTMIN+8", "waybar"], check=False)


def _show_unblocked(completed_id, tasks):
    unblocked = [
        t for t in tasks
        if completed_id in t.get("depends_on", []) and t["status"] not in ("done", "dropped")
    ]
    if unblocked:
        print(f"\n  {C['cyan']}Desbloqueadas:{C['reset']}")
        for u in unblocked:
            p = compute_priority(u, tasks)
            print(f"    → [{u['id']}] {u['name']} (p={p:.3f})")


def cmd_done(task_id):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            if t["status"] == "in_progress":
                t.pop("focus_started", None)
                t.pop("focus_duration", None)
                t.pop("_prev_status", None)
            t["status"] = "done"
            t["completed"] = date.today().isoformat()
            save_tasks(tasks)
            print(f"\n  {C['green']}✓ [{task_id}] '{t['name']}' completada{C['reset']}")
            _show_unblocked(task_id, tasks)
            print()
            return
    print(f"  Tarea {task_id} no encontrada.")


def cmd_drop(task_id):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            if t["status"] in ("done", "dropped"):
                print(f"  Tarea ya está {t['status']}.")
                return
            reason = input(f"  Motivo para descartar [{t['name']}]: ").strip() or "sin motivo"
            t["status"] = "dropped"
            t["dropped"] = date.today().isoformat()
            t["drop_reason"] = reason
            save_tasks(tasks)
            print(f"\n  {C['gray']}✗ [{task_id}] '{t['name']}' descartada conscientemente.{C['reset']}\n")
            return
    print(f"  Tarea {task_id} no encontrada.")


def cmd_eod():
    """Cierre de día: barre activas sin completar y fuerza una decisión."""
    tasks  = load_tasks()
    plan   = get_today_plan()
    active = [t for t in tasks if t["status"] in ("active", "in_progress")]

    print(f"\n{C['bold']}  Cierre de Día — {date.today().isoformat()}{C['reset']}")
    print(f"{C['gray']}{'─' * 50}{C['reset']}")

    if not active:
        print(f"  {C['green']}No hay tareas activas sin resolver 🎉{C['reset']}")
    else:
        print(f"  {C['yellow']}{len(active)} tarea/s activas sin completar. Decidí qué hacer con cada una:{C['reset']}\n")
        for t in active:
            tipo_icon = TASK_TYPE_ICONS.get(t.get("task_type", "fondo"), "?")
            print(f"  {tipo_icon} [{t['id']}] {t['name']}  {C['gray']}({t.get('category','?')}){C['reset']}")
            while True:
                action = input("  [b]acklog (mañana) / [d]one / [x]drop: ").strip().lower()
                if action in ("b", "d", "x"):
                    break
                print("  Opción inválida.")

            # Limpiar campos de foco si estaba in_progress
            t.pop("focus_started", None)
            t.pop("focus_duration", None)
            t.pop("_prev_status", None)

            if action == "d":
                t["status"] = "done"
                t["completed"] = date.today().isoformat()
                print(f"  {C['green']}  → DONE{C['reset']}")
            elif action == "x":
                reason = input("  Motivo del descarte: ").strip() or "sin motivo"
                t["status"] = "dropped"
                t["dropped"] = date.today().isoformat()
                t["drop_reason"] = reason
                print(f"  {C['gray']}  → DROPPED{C['reset']}")
            else:
                t["status"] = "backlog"
                t.pop("activated_date", None)
                print(f"  {C['cyan']}  → BACKLOG (reaparece mañana){C['reset']}")
            print()

    save_tasks(tasks)

    # Archivar plan del día
    if plan:
        plan["archived"] = True
        plan["archived_at"] = datetime.now().isoformat()
        save_plan(plan)
        print(f"  {C['gray']}Plan de hoy archivado.{C['reset']}")

    print(f"\n  {C['bold']}Día cerrado. Mañana corrés `plan` para el siguiente ciclo.{C['reset']}\n")


def cmd_history():
    history = load_focus_history()
    if not history:
        print(f"\n  {C['gray']}Sin bloques de foco registrados.{C['reset']}\n")
        return

    print(f"\n{C['bold']}  Historial de Bloques de Foco{C['reset']}")
    print(f"{C['gray']}{'─' * 55}{C['reset']}")

    by_date = {}
    for b in history:
        d = b.get("date", "?")
        by_date.setdefault(d, []).append(b)

    for d in sorted(by_date.keys(), reverse=True)[:7]:  # últimos 7 días
        blocks = by_date[d]
        total_min = sum(b.get("elapsed_min", 0) for b in blocks)
        print(f"\n  {C['cyan']}{d}{C['reset']}  {C['gray']}({total_min} min totales){C['reset']}")
        for b in blocks:
            outcome_icon = {"d": "✓", "c": "↩", "a": "↻"}.get(b.get("outcome", "?"), "?")
            print(f"    {outcome_icon} [{b['task_id']}] {b['task_name']}  {C['gray']}{b.get('elapsed_min',0)}/{b.get('planned_min',90)} min{C['reset']}")

    total_all = sum(b.get("elapsed_min", 0) for b in history)
    print(f"\n  {C['gray']}Total acumulado: {total_all} min ({total_all//60}h {total_all%60}m){C['reset']}\n")


def cmd_delete(task_id):
    tasks = load_tasks()
    target = next((t for t in tasks if t["id"] == task_id), None)
    if not target:
        print(f"  Tarea {task_id} no encontrada.")
        return
    if target["status"] not in ("inbox", "backlog"):
        print(f"  {C['red']}Solo se pueden eliminar tareas en INBOX o BACKLOG (estado: {target['status']}).{C['reset']}")
        print(f"  Usá `drop {task_id}` para descartar conscientemente.")
        return
    tasks = [t for t in tasks if t["id"] != task_id]
    save_tasks(tasks)
    print(f"  {C['green']}✓ Tarea [{task_id}] eliminada{C['reset']}")


# ── TUI ────────────────────────────────────────────────────────────────────────
def cmd_tui():
    tasks = load_tasks()
    plan  = get_today_plan()

    print(f"\n{C['bold']}{C['cyan']}  CPU SCHEDULER PERSONAL{C['reset']}")
    print(f"{C['gray']}{'─' * 58}{C['reset']}")

    # INBOX
    inbox = [t for t in tasks if t["status"] == "inbox"]
    if inbox:
        print(f"\n{C['bold']}  INBOX ({len(inbox)}){C['reset']}  {C['gray']}← procesar con `process`{C['reset']}")
        for t in inbox:
            print(f"  {C['gray']}○ [{t['id']}] {t['name']}{C['reset']}")

    # FOCO ACTIVO
    focus = get_active_focus_block(tasks)
    if focus:
        elapsed  = _focus_elapsed(focus)
        planned  = focus.get("focus_duration", 90)
        remaining = max(0, planned - elapsed)
        pct = min(100, int(elapsed / planned * 100))
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\n{C['bold']}  ⚡ EN FOCO AHORA:{C['reset']}")
        print(f"  {C['yellow']}▶ [{focus['id']}] {focus['name']}{C['reset']}")
        print(f"  [{bar}] {pct}%  {elapsed}/{planned} min  |  {remaining} min restantes")

    # PLAN DE HOY
    if plan:
        locked_label = f"{C['red']}[CERRADO]{C['reset']}" if plan.get("locked") else f"{C['green']}[abierto]{C['reset']}"
        print(f"\n{C['bold']}  PLAN HOY {locked_label}{C['reset']}")
        all_ids = [plan["principal"]] + plan["secundarias"]
        for i, tid in enumerate(all_ids):
            t = next((x for x in tasks if x["id"] == tid), None)
            if not t:
                continue
            slot  = "MAIN" if i == 0 else f"S{i}  "
            tipo  = TASK_TYPE_ICONS.get(t.get("task_type", "fondo"), "?")
            cat   = CATEGORY_ICONS.get(t.get("category", "personal"), "?")
            days  = days_until(t.get("deadline"))
            d_str = f"{int(days)}d" if t.get("deadline") else "∞"
            status_color = {
                "active": C["cyan"], "in_progress": C["yellow"],
                "done": C["green"], "dropped": C["gray"],
            }.get(t["status"], C["reset"])
            print(f"  {C['gray']}{slot}{C['reset']}  {tipo}{cat} {status_color}[{t['id']}] {t['name']}{C['reset']}  {C['gray']}[{d_str}] {t['status']}{C['reset']}")
    else:
        print(f"\n  {C['yellow']}Sin plan de hoy. Usá `plan` para armar uno.{C['reset']}")

    # BACKLOG
    backlog = [t for t in tasks if t["status"] == "backlog"]
    if backlog:
        sorted_b = sorted(backlog, key=lambda t: compute_priority(t, tasks), reverse=True)
        print(f"\n{C['bold']}  BACKLOG ({len(backlog)}){C['reset']}")
        for t in sorted_b:
            p    = compute_priority(t, tasks)
            tipo = TASK_TYPE_ICONS.get(t.get("task_type", "fondo"), "?")
            cat  = CATEGORY_ICONS.get(t.get("category", "personal"), "?")
            days = days_until(t.get("deadline"))
            d_str = f"{int(days)}d" if t.get("deadline") else "∞"
            blocked = " 🔒" if is_blocked(t, tasks) else ""

            if days <= 0:
                color = C["red"]
            elif days <= 7:
                color = C["yellow"]
            else:
                color = C["reset"]

            print(f"  {color}{tipo}{cat} [{t['id']}] {t['name']}{C['reset']}  {C['gray']}[{d_str}] p={p:.3f}{blocked}{C['reset']}")

    # DONE recientes
    done = [t for t in tasks if t["status"] == "done"]
    if done:
        print(f"\n{C['gray']}  COMPLETADAS ({len(done)}) — últimas 3:")
        for t in done[-3:]:
            print(f"    ✓ [{t['id']}] {t['name']}  ({t.get('completed','?')})")
        print(C["reset"])

    print()
    input(f"  {C['gray']}Enter para cerrar...{C['reset']}")


# ── Waybar ─────────────────────────────────────────────────────────────────────
def cmd_waybar():
    tasks = load_tasks()

    # Prioridad 1: bloque de foco activo
    focus = get_active_focus_block(tasks)
    if focus:
        elapsed   = _focus_elapsed(focus)
        planned   = focus.get("focus_duration", 90)
        remaining = max(0, planned - elapsed)
        icon      = CATEGORY_ICONS.get(focus.get("category", "personal"), "⚡")
        name      = focus["name"][:20] + "..." if len(focus["name"]) > 20 else focus["name"]
        pct       = min(100, int(elapsed / planned * 100))
        print(json.dumps({
            "text":    f"⚡ {icon} {name} · {remaining}m",
            "tooltip": f"EN FOCO: {focus['name']}\n{elapsed}/{planned} min  ({pct}% completado)",
            "class":   "in_progress",
        }))
        return

    # Prioridad 2: tarea principal del plan / top de backlog
    current = get_top_task(tasks)
    if not current:
        print(json.dumps({
            "text":    "󰄭 Sin tareas",
            "tooltip": "No hay tareas pendientes",
            "class":   "idle",
        }))
        return

    days = days_until(current.get("deadline"))
    icon = CATEGORY_ICONS.get(current.get("category", "personal"), "󰋙")
    name = current["name"][:22] + "..." if len(current["name"]) > 22 else current["name"]

    if days <= 0:
        urgency_class, d_str = "overdue", "¡VENCIDA!"
    elif days <= 2:
        urgency_class, d_str = "critical", f"en {int(days)}d"
    elif days <= 7:
        urgency_class, d_str = "warning",  f"en {int(days)}d"
    elif current.get("deadline"):
        urgency_class, d_str = "normal",   f"en {int(days)}d"
    else:
        urgency_class, d_str = "normal",   "sin fecha"

    plan = get_today_plan()
    tooltip_lines = [f"<b>Plan de hoy — {date.today().isoformat()}</b>"] if plan else ["<b>Top Backlog:</b>"]
    sorted_active = get_sorted_backlog(tasks)
    for i, t in enumerate(sorted_active[:5]):
        p = compute_priority(t, tasks)
        blocked = " 🔒" if is_blocked(t, tasks) else ""
        d = days_until(t.get("deadline"))
        d_s = f"{int(d)}d" if t.get("deadline") else "∞"
        marker = "▶ " if t["id"] == current["id"] else f"{i+1}. "
        tipo = TASK_TYPE_ICONS.get(t.get("task_type", "fondo"), "")
        tooltip_lines.append(f"{marker}{tipo} {t['name']} [{d_s}] (p={p:.2f}){blocked}")

    inbox_count = sum(1 for t in tasks if t["status"] == "inbox")
    pending = sum(1 for t in tasks if t["status"] in ("backlog", "active", "in_progress"))
    if inbox_count:
        tooltip_lines.append(f"\n<i>⚠ {inbox_count} en INBOX sin procesar</i>")
    tooltip_lines.append(f"<i>{pending} en cola</i>")

    print(json.dumps({
        "text":    f"{icon} {name} · {d_str}",
        "tooltip": "\n".join(tooltip_lines),
        "class":   urgency_class,
    }))


# ── Entrypoint ─────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args or args[0] == "waybar":
        cmd_waybar()
    elif args[0] == "tui" or args[0] == "list":
        cmd_tui()
    elif args[0] == "add":
        cmd_add()
    elif args[0] == "process":
        cmd_process()
    elif args[0] == "plan":
        sub = args[1] if len(args) > 1 else None
        cmd_plan(sub)
    elif args[0] == "focus" and len(args) > 1:
        cmd_focus(args[1], args[2:])
    elif args[0] == "done" and len(args) > 1:
        cmd_done(int(args[1]))
    elif args[0] == "drop" and len(args) > 1:
        cmd_drop(int(args[1]))
    elif args[0] == "eod":
        cmd_eod()
    elif args[0] == "history":
        cmd_history()
    elif args[0] == "delete" and len(args) > 1:
        cmd_delete(int(args[1]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

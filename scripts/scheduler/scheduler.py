#!/usr/bin/env python3
"""
CPU Scheduler personal - algoritmo EDF (Earliest Deadline First) con
pesos por categoría.
Uso:
  scheduler.py                    → muestra tarea actual (para waybar)
  scheduler.py list               → lista todas las tareas con prioridad
  scheduler.py add                → asistente interactivo para agregar tarea
  scheduler.py done <id>          → marca tarea como completada
  scheduler.py waybar             → output JSON para waybar
  scheduler.py tui                → vista completa en terminal
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
DATA_FILE = Path.home() / "OneDrive" / "varios" / "scheduler" / "tasks.json"
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

# Peso base por categoría (multiplica la prioridad calculada)
CATEGORY_WEIGHTS = {
    "universidad": 1.5,
    "software": 1.0,
    "personal": 0.7,
    "trabajo": 1.2,
}

# Íconos por categoría para waybar
CATEGORY_ICONS = {
    "universidad": "󰑴",
    "software": "󰲋",
    "personal": "󰋙",
    "trabajo": "󰢮",
}

# Colores para la TUI
C = {
    "red": "\033[91m",
    "yellow": "\033[93m",
    "green": "\033[92m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "gray": "\033[90m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


# ── Persistencia ───────────────────────────────────────────────────────────────
def load_tasks():
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE) as f:
        return json.load(f)


def save_tasks(tasks):
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def next_id(tasks):
    return max((t["id"] for t in tasks), default=0) + 1


# ── Algoritmo de scheduling ────────────────────────────────────────────────────
def days_until(deadline_str):
    """Días hasta el deadline. Negativo = vencida."""
    if not deadline_str:
        return 999  # Sin deadline → baja urgencia
    deadline = date.fromisoformat(deadline_str)
    delta = (deadline - date.today()).days
    return delta if delta != 0 else 0.5  # evitar división por cero


def is_blocked(task, tasks):
    """Retorna True si alguna dependencia no está completada."""
    for dep_id in task.get("depends_on", []):
        dep = next((t for t in tasks if t["id"] == dep_id), None)
        if dep and dep["status"] != "done":
            return True
    return False


def compute_priority(task, tasks):
    """
    Prioridad EDF con pesos:
      P = (urgencia_base * peso_categoria) / max(días_restantes, 0.1)
    Tareas bloqueadas o completadas → prioridad 0
    """
    if task["status"] == "done":
        return 0
    if is_blocked(task, tasks):
        return 0

    days = days_until(task.get("deadline"))
    urgency_base = task.get("urgency", 5)  # 1-10, definida por el usuario
    cat_weight = CATEGORY_WEIGHTS.get(task.get("category", "personal"), 1.0)

    # Penalizar tareas muy lejanas (>30 días) para que no acaparen atención
    if days > 30:
        distance_penalty = 30 / days
    else:
        distance_penalty = 1.0

    priority = (urgency_base * cat_weight * distance_penalty) / max(days, 0.1)

    # Boost si el deadline es en ≤7 días (simula "interrupt de alta prioridad")
    if 0 < days <= 7:
        priority *= 1.5

    return round(priority, 4)


def get_sorted_tasks(tasks):
    """Retorna tareas activas ordenadas por prioridad descendente."""
    active = [t for t in tasks if t["status"] != "done"]
    return sorted(active, key=lambda t: compute_priority(t, tasks), reverse=True)


def get_current_task(tasks):
    """La tarea con mayor prioridad que no esté bloqueada."""
    sorted_tasks = get_sorted_tasks(tasks)
    for t in sorted_tasks:
        if not is_blocked(t, tasks):
            return t
    return None


# ── Comandos ───────────────────────────────────────────────────────────────────
def cmd_waybar():
    """Output JSON para waybar custom module."""
    tasks = load_tasks()
    current = get_current_task(tasks)

    if not current:
        print(
            json.dumps(
                {
                    "text": "󰄭 Sin tareas",
                    "tooltip": "No hay tareas pendientes",
                    "class": "idle",
                }
            )
        )
        return

    days = days_until(current.get("deadline"))
    icon = CATEGORY_ICONS.get(current.get("category", "personal"), "󰋙")
    name = current["name"]

    # Truncar nombre si es muy largo
    if len(name) > 25:
        name = name[:22] + "..."

    if days <= 0:
        urgency_class = "overdue"
        deadline_str = "¡VENCIDA!"
    elif days <= 2:
        urgency_class = "critical"
        deadline_str = f"en {int(days)}d"
    elif days <= 7:
        urgency_class = "warning"
        deadline_str = f"en {int(days)}d"
    elif current.get("deadline"):
        urgency_class = "normal"
        deadline_str = f"en {int(days)}d"
    else:
        urgency_class = "normal"
        deadline_str = "sin fecha"

    # Tooltip con las próximas 3 tareas
    sorted_tasks = get_sorted_tasks(tasks)
    tooltip_lines = ["<b>Cola de prioridad:</b>"]
    for i, t in enumerate(sorted_tasks[:5]):
        p = compute_priority(t, tasks)
        blocked = " 🔒" if is_blocked(t, tasks) else ""
        d = days_until(t.get("deadline"))
        d_str = f"{int(d)}d" if t.get("deadline") else "∞"
        marker = "▶ " if i == 0 and not is_blocked(t, tasks) else f"{i + 1}. "
        tooltip_lines.append(f"{marker}{t['name']} [{d_str}] (p={p:.2f}){blocked}")

    pending = sum(1 for t in tasks if t["status"] != "done")
    tooltip_lines.append(f"\n<i>{pending} tareas pendientes</i>")

    print(
        json.dumps(
            {
                "text": f"{icon} {name} · {deadline_str}",
                "tooltip": "\n".join(tooltip_lines),
                "class": urgency_class,
            }
        )
    )


def cmd_tui():
    """Vista completa en terminal con colores."""
    tasks = load_tasks()
    sorted_tasks = get_sorted_tasks(tasks)
    done_tasks = [t for t in tasks if t["status"] == "done"]

    print(f"\n{C['bold']}{C['cyan']}  CPU SCHEDULER PERSONAL{C['reset']}")
    print(f"{C['gray']}{'─' * 55}{C['reset']}")

    if not sorted_tasks:
        print(f"{C['green']}  No hay tareas pendientes 🎉{C['reset']}\n")
    else:
        current = get_current_task(tasks)
        print(f"{C['bold']}  EJECUTANDO AHORA:{C['reset']}")
        if current:
            p = compute_priority(current, tasks)
            days = days_until(current.get("deadline"))
            icon = CATEGORY_ICONS.get(current.get("category"), "?")
            d_str = f"{int(days)}d" if current.get("deadline") else "sin fecha"
            print(
                f"  {C['yellow']}▶ [{current['id']}] {icon} {current['name']}{C['reset']}"
            )
            print(
                f"     cat={current.get('category', '?')} | deadline={d_str} | prioridad={p:.3f}"
            )
        print()

        print(f"{C['bold']}  COLA DE PRIORIDAD:{C['reset']}")
        for i, t in enumerate(sorted_tasks):
            p = compute_priority(t, tasks)
            days = days_until(t.get("deadline"))
            d_str = f"{int(days)}d" if t.get("deadline") else "  ∞"
            blocked = is_blocked(t, tasks)
            icon = CATEGORY_ICONS.get(t.get("category"), "?")

            if blocked:
                color = C["gray"]
                status_icon = "🔒"
            elif days <= 0:
                color = C["red"]
                status_icon = "!!"
            elif days <= 7:
                color = C["yellow"]
                status_icon = f"{i + 1}."
            else:
                color = C["reset"]
                status_icon = f"{i + 1}."

            dep_str = ""
            if t.get("depends_on"):
                dep_str = f" → espera {t['depends_on']}"

            print(f"  {color}{status_icon} [{t['id']}] {icon} {t['name']}{C['reset']}")
            print(
                f"     {C['gray']}cat={t.get('category', '?')} | {d_str} | p={p:.3f}{dep_str}{C['reset']}"
            )

    if done_tasks:
        print(f"\n{C['gray']}  COMPLETADAS ({len(done_tasks)}):")
        for t in done_tasks[-3:]:  # solo últimas 3
            print(f"  ✓ [{t['id']}] {t['name']}")
        print(C["reset"])

    print()
    input(f"  {C['gray']}Enter para cerrar...{C['reset']}")


def cmd_add():
    """Asistente interactivo para agregar tarea."""
    tasks = load_tasks()

    print(f"\n{C['bold']}  Nueva tarea{C['reset']}")
    print(f"{C['gray']}  (Enter para omitir campos opcionales){C['reset']}\n")

    name = input("  Nombre: ").strip()
    if not name:
        print("  Nombre requerido.")
        return

    while True:
        print(f"  Categoría [{'/'.join(CATEGORY_WEIGHTS.keys())}]: ", end="")
        category = input().strip().lower() or "personal"

        if category in CATEGORY_WEIGHTS:
            break

        print("  Categoría inválida. Intente nuevamente.")

    while True:
        deadline = input("  Deadline (YYYY-MM-DD, opcional): ").strip()

        if not deadline:
            deadline = None
            break

        try:
            date.fromisoformat(deadline)
            break
        except ValueError:
            print("  Fecha inválida. Use el formato YYYY-MM-DD.")

    urgency_raw = input("  Urgencia base 1-10 [5]: ").strip() or "5"
    try:
        urgency = max(1, min(10, int(urgency_raw)))
    except ValueError:
        urgency = 5

    # Dependencias
    if tasks:
        print("\n  Tareas existentes (para definir dependencias):")
        for t in tasks:
            if t["status"] != "done":
                print(f"    [{t['id']}] {t['name']}")
    dep_raw = input("  Depende de (IDs separados por coma, opcional): ").strip()
    depends_on = []
    if dep_raw:
        try:
            depends_on = [int(x.strip()) for x in dep_raw.split(",")]
        except ValueError:
            depends_on = []

    task = {
        "id": next_id(tasks),
        "name": name,
        "category": category,
        "deadline": deadline,
        "urgency": urgency,
        "depends_on": depends_on,
        "status": "pending",
        "created": date.today().isoformat(),
    }

    tasks.append(task)
    save_tasks(tasks)

    p = compute_priority(task, tasks)
    print(
        f"\n  {C['green']}✓ Tarea [{task['id']}] agregada (prioridad inicial: {p:.3f}){C['reset']}\n"
    )


def cmd_done(task_id):
    """Marca una tarea como completada."""
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "done"
            t["completed"] = date.today().isoformat()
            save_tasks(tasks)
            print(f"  {C['green']}✓ [{task_id}] '{t['name']}' completada{C['reset']}")

            # Mostrar qué se desbloqueó
            newly_unblocked = [
                x
                for x in tasks
                if task_id in x.get("depends_on", []) and x["status"] != "done"
            ]
            if newly_unblocked:
                print(f"\n  {C['cyan']}Desbloqueadas:{C['reset']}")
                for u in newly_unblocked:
                    p = compute_priority(u, tasks)
                    print(f"    → [{u['id']}] {u['name']} (prioridad: {p:.3f})")
            print()
            return
    print(f"  Tarea {task_id} no encontrada.")


def cmd_delete(task_id):
    """Elimina una tarea."""
    tasks = load_tasks()
    original = len(tasks)
    tasks = [t for t in tasks if t["id"] != task_id]
    if len(tasks) < original:
        save_tasks(tasks)
        print(f"  {C['green']}✓ Tarea [{task_id}] eliminada{C['reset']}")
    else:
        print(f"  Tarea {task_id} no encontrada.")


# ── Entrypoint ─────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args or args[0] == "waybar":
        cmd_waybar()
    elif args[0] == "tui":
        cmd_tui()
    elif args[0] == "list":
        cmd_tui()
    elif args[0] == "add":
        cmd_add()
    elif args[0] == "done" and len(args) > 1:
        cmd_done(int(args[1]))
    elif args[0] == "delete" and len(args) > 1:
        cmd_delete(int(args[1]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

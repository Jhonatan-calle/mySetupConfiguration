#!/usr/bin/env python3
"""
scheduler — Centro de control personal.
Uso normal: scheduler tui
Waybar:     scheduler
"""

import json
import sys
import os
import tty
import termios
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR   = Path.home() / "OneDrive" / "varios" / "scheduler"
BASE_DIR.mkdir(parents=True, exist_ok=True)
TASKS_FILE = BASE_DIR / "tasks.json"
FOCUS_FILE = BASE_DIR / "focus_blocks.json"

TIPOS = {"critica": 5, "intensiva": 3, "fondo": 1}
CATEGORIAS = {"universidad": 1, "software": 4, "learning": 3, "personal": 2}
ICONOS_CAT = {"universidad": "󰑴", "software": "󰲋", "personal": "󰋙", "trabajo": "󰢮", "learning": "󰿄"}
ICONOS_TIPO = {"critica": "●", "intensiva": "●", "fondo": "●"}

ROFI_THEME = str(Path.home() / ".config" / "rofi" / "scheduler.rasi")

def _rofi(items, prompt="scheduler"):
    cmd = ["rofi", "-dmenu", "-p", prompt, "-i", "-theme", ROFI_THEME]
    r = subprocess.run(cmd, input="\n".join(items), capture_output=True, text=True)
    return r.stdout.rstrip("\n") if r.returncode == 0 else None

def _rofi_in(prompt="", prefill=""):
    cmd = ["rofi", "-dmenu", "-p", prompt, "-theme", ROFI_THEME]
    r = subprocess.run(cmd, input=prefill, capture_output=True, text=True)
    return r.stdout.rstrip("\n") if r.returncode == 0 else None

def _rofi_msg(text):
    subprocess.run(["notify-send", "-a", "scheduler", text])

def _menu(items_actions, prompt="scheduler"):
    items = [i for i, _ in items_actions]
    actions = dict(items_actions)
    sel = _rofi(items, prompt)
    if sel is None:
        return None
    return actions.get(sel)

R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
def fg(r,g,b):   return f"\033[38;2;{r};{g};{b}m"
ROJO    = fg(255, 100,  80)
NARANJA = fg(255, 165,  60)
AMARILLO= fg(255, 210,  80)
VERDE   = fg(100, 210, 120)
CYAN    = fg( 80, 200, 220)
AZUL    = fg(100, 150, 255)
MAGENTA = fg(200, 100, 255)
GRIS    = fg(120, 120, 130)
BLANCO  = fg(220, 220, 230)

COLOR_TIPO = {"critica": ROJO, "intensiva": AMARILLO, "fondo": VERDE}

ESTADOS_VALIDOS = ("pendiente", "hoy", "en_foco", "listo")
_K_HEADER = "__header__"  # sentinel for non-selectable menu items


def cargar_tareas():
    if not TASKS_FILE.exists():
        return []
    try:
        content = TASKS_FILE.read_text().strip()
        return json.loads(content) if content else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def guardar_tareas(tareas):
    TASKS_FILE.write_text(json.dumps(tareas, indent=2, ensure_ascii=False))

def cargar_historial():
    if not FOCUS_FILE.exists():
        return []
    return json.loads(FOCUS_FILE.read_text())

def guardar_historial(h):
    FOCUS_FILE.write_text(json.dumps(h, indent=2, ensure_ascii=False))

def proximo_id(tareas):
    return max((t["id"] for t in tareas), default=0) + 1


def foco_activo(tareas):
    return next((t for t in tareas if t.get("estado") == "en_foco"), None)

def minutos_en_foco(tarea):
    acum = tarea.get("minutos_acumulados")
    if acum is not None:
        return acum
    inicio = tarea.get("foco_inicio")
    if not inicio:
        return 0
    delta = datetime.now() - datetime.fromisoformat(inicio)
    return int(delta.total_seconds() / 60)


def dias_hasta(deadline_str):
    if not deadline_str:
        return 999
    d = date.fromisoformat(deadline_str)
    delta = (d - date.today()).days
    return delta if delta != 0 else 0.5

def esta_bloqueada(tarea, tareas):
    for dep_id in tarea.get("depende_de", []):
        dep = next((t for t in tareas if t["id"] == dep_id), None)
        if dep and dep["estado"] != "listo":
            return True
    return False

def calcular_prioridad(tarea, tareas):
    if tarea["estado"] == "listo":
        return 0
    if esta_bloqueada(tarea, tareas):
        return 0

    dias     = dias_hasta(tarea.get("limite"))
    urgencia = tarea.get("urgencia", 5)
    w_tipo   = TIPOS.get(tarea.get("tipo", "fondo"), 1)
    w_cat    = CATEGORIAS.get(tarea.get("categoria", "personal"), 1.0)

    if tarea.get("categoria") == "universidad" and dias > 7 and urgencia <= 6:
        otras = [t for t in tareas if t["id"] != tarea["id"] and t["estado"] not in ("listo",) and t.get("categoria") != "universidad"]
        if otras:
            return 0

    penalizacion = min(1.0, 30 / dias) if dias > 30 else 1.0
    p = (urgencia * w_tipo * w_cat * penalizacion) / max(dias, 0.1)
    if 0 < dias <= 7:
        p *= 1.5
    return round(p, 4)

def tareas_ordenadas(tareas):
    activas = [t for t in tareas if t["estado"] in ("pendiente", "hoy", "en_foco")]
    return sorted(activas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)

def tarea_principal(tareas):
    for t in tareas_ordenadas(tareas):
        if t["estado"] in ("hoy", "en_foco") and not esta_bloqueada(t, tareas):
            return t
    return None


def leer_tecla():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            sys.stdin.read(2)
            return None
        # Detectar mayúsculas para F (focus directo)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    termios.tcflush(fd, termios.TCIFLUSH)

def leer_linea(prompt=""):
    print(prompt, end="", flush=True)
    return input()


def limpiar():
    os.system("clear")

def ancho_terminal():
    return os.get_terminal_size().columns

def linea(char="─", color=GRIS):
    w = min(ancho_terminal(), 72)
    print(f"{color}{char * w}{R}")

def seccion(titulo, color=CYAN):
    print(f"\n{color}{BOLD} {titulo}{R}")

def barra_progreso(pct, ancho=20):
    lleno = int(pct / 100 * ancho)
    vacio = ancho - lleno
    return f"{AMARILLO}{'█' * lleno}{GRIS}{'░' * vacio}{R}"

def formato_dias(dias, con_limite):
    if not con_limite:
        return f"{GRIS}sin fecha{R}"
    d = int(dias)
    if dias <= 0:
        return f"{ROJO}{BOLD}¡VENCIDA!{R}"
    elif dias <= 2:
        return f"{ROJO}{d}d{R}"
    elif dias <= 7:
        return f"{AMARILLO}{d}d{R}"
    else:
        return f"{GRIS}{d}d{R}"

def etiqueta_tipo(tipo):
    col = COLOR_TIPO.get(tipo, GRIS)
    return f"{col}{ICONOS_TIPO.get(tipo,'?')}{R}"

def etiqueta_cat(cat):
    return ICONOS_CAT.get(cat, "?")

def nombre_corto(nombre, max_len=38):
    return nombre[:max_len-1] + "…" if len(nombre) > max_len else nombre


def mostrar_foco(foco):
    elapsed   = minutos_en_foco(foco)
    planned   = foco.get("foco_duracion", 90)
    remaining = max(0, planned - elapsed)
    pct       = min(100, int(elapsed / planned * 100))
    barra     = barra_progreso(pct)

    seccion("⚡  EN FOCO AHORA", AMARILLO)
    linea("─", AMARILLO)
    tipo_col = COLOR_TIPO.get(foco.get("tipo","fondo"), GRIS)
    print(f"  {tipo_col}{BOLD}{nombre_corto(foco['name'], 44)}{R}")
    acum = foco.get("minutos_acumulados", 0)
    print(f"  {barra}  {AMARILLO}{elapsed}m{R} reales  ·  objetivo {CYAN}{remaining}m{R}")
    if acum > 0:
        horas = acum // 60
        mins_r = acum % 60
        acum_str = f"{horas}h {mins_r}m" if horas else f"{mins_r}m"
        print(f"  {GRIS}⏱ {acum_str} de pomodoros completados{R}")
    linea("─", AMARILLO)

def mostrar_hoy(tareas):
    hoy = [t for t in tareas if t["estado"] == "hoy"]
    if not hoy:
        return
    ordenadas = sorted(hoy, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
    seccion(f"📋  HOY  ({len(hoy)})", CYAN)
    for i, t in enumerate(ordenadas):
        dias  = dias_hasta(t.get("limite"))
        d_fmt = formato_dias(dias, t.get("limite"))
        tipo  = etiqueta_tipo(t.get("tipo","fondo"))
        cat   = etiqueta_cat(t.get("categoria","personal"))
        bloq  = f"  {GRIS}🔒{R}" if esta_bloqueada(t, tareas) else ""
        print(f"  {GRIS}{i+1:2}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],34)}{R}  {d_fmt}{bloq}")

def mostrar_pendientes(tareas):
    pend = [t for t in tareas if t["estado"] == "pendiente"]
    if not pend:
        return
    ordenadas = sorted(pend, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
    seccion(f"📦  PENDIENTES  ({len(pend)})", AZUL)
    for i, t in enumerate(ordenadas):
        p     = calcular_prioridad(t, tareas)
        dias  = dias_hasta(t.get("limite"))
        d_fmt = formato_dias(dias, t.get("limite"))
        tipo  = etiqueta_tipo(t.get("tipo","fondo"))
        cat   = etiqueta_cat(t.get("categoria","personal"))
        bloq  = f"  {GRIS}🔒{R}" if esta_bloqueada(t, tareas) else ""
        print(f"  {GRIS}{i+1:2}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],34)}{R}  {d_fmt}  {GRIS}p={p:.2f}{R}{bloq}")

def mostrar_completadas_recientes(tareas):
    listas = [t for t in tareas if t["estado"] == "listo"]
    if not listas:
        return
    recientes = sorted(listas, key=lambda t: t.get("completado",""), reverse=True)[:3]
    print(f"\n{GRIS}  Completadas recientemente:")
    for t in recientes:
        print(f"    ✓  {nombre_corto(t['name'],44)}  {DIM}{t.get('completado','')}{R}")

def mostrar_stats_rapidas(tareas):
    total_pend = sum(1 for t in tareas if t["estado"] == "pendiente")
    total_hoy  = sum(1 for t in tareas if t["estado"] == "hoy")
    total_foco = sum(1 for t in tareas if t["estado"] == "en_foco")
    total_listo= sum(1 for t in tareas if t["estado"] == "listo")

    hist = cargar_historial()
    hoy_str = date.today().isoformat()
    min_hoy = sum(b.get("minutos_reales", 0) for b in hist if b.get("fecha") == hoy_str)

    partes = []
    if total_pend: partes.append(f"{AZUL}📦 {total_pend} pendientes{R}")
    if total_foco: partes.append(f"{AMARILLO}⚡ {total_foco} en foco{R}")
    if total_hoy:  partes.append(f"{CYAN}📋 {total_hoy} hoy{R}")
    if total_listo:partes.append(f"{VERDE}✓ {total_listo} listos{R}")
    if min_hoy:    partes.append(f"{MAGENTA}⏱ {min_hoy}m foco hoy{R}")

    if partes:
        print(f"\n  {'  ·  '.join(partes)}")


def construir_menu(tareas, foco):
    opciones = [("n", "nueva tarea", "nueva")]

    if foco:
        opciones.append(("f", "cerrar foco", "cerrar_foco"))
    else:
        hoy = [t for t in tareas if t["estado"] == "hoy"]
        if hoy:
            opciones.append(("f", "iniciar foco", "iniciar_foco"))
            opciones.append(("F", "foco directo", "foco_directo"))

    todo = [t for t in tareas if t["estado"] in ("pendiente", "hoy")]
    if todo:
        opciones.append(("p", "hoy / pendiente", "toggle_hoy"))

    activas = [t for t in tareas if t["estado"] in ("hoy","pendiente","en_foco")]
    if activas:
        opciones.append(("l", "marcar lista", "marcar_lista"))
        opciones.append(("d", "dependencias", "dependencias"))

    fin_dia = [t for t in tareas if t["estado"] in ("hoy","en_foco")]
    if fin_dia:
        opciones.append(("z", "cierre de día", "cierre_dia"))

    opciones.append(("h", "historial", "historial"))
    opciones.append(("q", "salir", "salir"))
    return opciones

def mostrar_menu(opciones):
    print()
    linea("─", GRIS)
    for i in range(0, len(opciones), 3):
        fila = opciones[i:i+3]
        print("  " + "    ".join(f"{CYAN}{BOLD}[{t}]{R} {BLANCO}{d}{R}" for t, d, _ in fila))
    linea("─", GRIS)
    print(f"  {GRIS}tecla → {R}", end="", flush=True)


def accion_nueva(tareas):
    limpiar()
    seccion("Nueva tarea", AZUL)
    linea()
    print(f"  {GRIS}Nombre | tipo(c/i/f) | categoria | AAAA-MM-DD{R}")
    print(f"  {GRIS}Solo el nombre es obligatorio. Ej: estudiar | c | universidad | 2026-07-01{R}\n")

    raw = leer_linea(f"  {BLANCO}→{R} ").strip()
    if not raw:
        return

    partes = [p.strip() for p in raw.split("|")]
    nombre = partes[0]
    if not nombre:
        print(f"  {ROJO}Nombre requerido.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    tipo = "intensiva"
    if len(partes) > 1 and partes[1]:
        tipo = {"c": "critica", "i": "intensiva", "f": "fondo"}.get(partes[1].lower(), partes[1])
        if tipo not in TIPOS:
            tipo = "intensiva"

    categoria = "personal"
    if len(partes) > 2 and partes[2]:
        cats = list(CATEGORIAS.keys())
        try:
            idx = int(partes[2]) - 1
            if 0 <= idx < len(cats):
                categoria = cats[idx]
            else:
                categoria = partes[2].lower()
                if categoria not in CATEGORIAS:
                    categoria = "personal"
        except ValueError:
            categoria = partes[2].lower()
            if categoria not in CATEGORIAS:
                categoria = "personal"

    limite_str = partes[3].strip() if len(partes) > 3 else ""
    limite = None
    if limite_str:
        try:
            date.fromisoformat(limite_str)
            limite = limite_str
        except ValueError:
            pass

    tarea = {
        "id":        proximo_id(tareas),
        "name":      nombre,
        "notas":     None,
        "estado":    "pendiente",
        "creado":    date.today().isoformat(),
        "categoria": categoria,
        "tipo":      tipo,
        "limite":    limite,
        "urgencia":  5,
        "depende_de": [],
    }
    tareas.append(tarea)
    guardar_tareas(tareas)
    p = calcular_prioridad(tarea, tareas)
    print(f"\n  {VERDE}✓ [{tarea['id']}] '{nombre}'{R}  {GRIS}{tipo}/{categoria}  p={p:.2f}{R}")

    # Dependencias
    activas = [t for t in tareas if t["estado"] in ("pendiente", "hoy") and t["id"] != tarea["id"]]
    if activas:
        print(f"\n  {GRIS}¿Depende de alguna tarea?{R}")
        ordenadas = sorted(activas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
        for i, t in enumerate(ordenadas):
            tipo = etiqueta_tipo(t.get("tipo","fondo"))
            cat  = etiqueta_cat(t.get("categoria","personal"))
            print(f"  {GRIS}{i+1:2}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],40)}{R}")
        raw = leer_linea(f"  {GRIS}Números (coma, Enter = ninguna):{R} ").strip()
        if raw:
            for s in raw.split(","):
                try:
                    dep = ordenadas[int(s.strip())-1]
                    tarea["depende_de"].append(dep["id"])
                except (ValueError, IndexError):
                    pass
            if tarea["depende_de"]:
                guardar_tareas(tareas)
                print(f"  {CYAN}→ {len(tarea['depende_de'])} dependencia/s registrada/s{R}")

    input(f"  {GRIS}Enter...{R}")


def accion_toggle_hoy(tareas):
    """Muestra pendientes y hoy, permite elegir número para cambiar estado."""
    limpiar()
    seccion("Mover tareas entre HOY y pendiente", CYAN)
    linea()

    todas = [t for t in tareas if t["estado"] in ("pendiente", "hoy")]
    if not todas:
        print(f"  {AMARILLO}No hay tareas pendientes ni en hoy.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    ordenadas = sorted(todas, key=lambda t: (0 if t["estado"] == "hoy" else 1, -calcular_prioridad(t, tareas)))
    print()
    for i, t in enumerate(ordenadas):
        estado_tag = f"{CYAN}hoy{R}" if t["estado"] == "hoy" else f"{GRIS}pendiente{R}"
        tipo = etiqueta_tipo(t.get("tipo","fondo"))
        cat  = etiqueta_cat(t.get("categoria","personal"))
        dias = dias_hasta(t.get("limite"))
        d_fmt= formato_dias(dias, t.get("limite"))
        bloq = f"  {GRIS}🔒{R}" if esta_bloqueada(t, tareas) else ""
        print(f"  {GRIS}{i+1:2}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],34)}{R}  {d_fmt}  {estado_tag}{bloq}")

    print(f"\n  {GRIS}Número → cambia entre hoy/pendiente. Enter para terminar.{R}")
    while True:
        raw = leer_linea(f"\n  {GRIS}número:{R} ").strip()
        if not raw:
            break
        try:
            tarea = ordenadas[int(raw)-1]
        except (ValueError, IndexError):
            print(f"  {ROJO}Número inválido.{R}")
            continue

        if tarea["estado"] == "hoy":
            tarea["estado"] = "pendiente"
            tarea.pop("fecha_activacion", None)
            print(f"  {CYAN}→ '{nombre_corto(tarea['name'],30)}' → pendiente{R}")
        else:
            tarea["estado"] = "hoy"
            tarea["fecha_activacion"] = date.today().isoformat()
            print(f"  {VERDE}→ '{nombre_corto(tarea['name'],30)}' → hoy{R}")
        guardar_tareas(tareas)

    input(f"\n  {GRIS}Enter...{R}")


def accion_iniciar_foco(tareas):
    limpiar()
    seccion("Iniciar Bloque de Foco", AMARILLO)
    linea()

    candidatas = [t for t in tareas if t["estado"] == "hoy"]
    if not candidatas:
        print(f"  {AMARILLO}No hay tareas en el plan de hoy.{R}")
        print(f"  {GRIS}Usá [p] para armar el plan primero.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    ordenadas = sorted(candidatas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
    print()
    for i, t in enumerate(ordenadas):
        tipo  = etiqueta_tipo(t.get("tipo","fondo"))
        cat   = etiqueta_cat(t.get("categoria","personal"))
        dias  = dias_hasta(t.get("limite"))
        d_fmt = formato_dias(dias, t.get("limite"))
        print(f"  {GRIS}{i+1}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],34)}{R}  {d_fmt}")

    raw = leer_linea(f"\n  {GRIS}Número (Enter = top):{R} ").strip()
    if raw:
        try:
            tarea = ordenadas[int(raw)-1]
        except (ValueError, IndexError):
            print(f"  {ROJO}Número inválido.{R}")
            input(f"  {GRIS}Enter...{R}")
            return
    else:
        tarea = ordenadas[0]

    raw = leer_linea(f"  {GRIS}Duración en minutos [90]:{R} ").strip()
    try:
        duracion = max(5, int(raw)) if raw else 90
    except ValueError:
        duracion = 90

    tarea["_estado_previo"]     = tarea["estado"]
    tarea["estado"]             = "en_foco"
    tarea["foco_inicio"]        = datetime.now().isoformat()
    tarea["foco_duracion"]      = duracion
    tarea["minutos_acumulados"] = tarea.get("minutos_acumulados", 0)
    guardar_tareas(tareas)
    refrescar_waybar()

    termina = (datetime.now() + timedelta(minutes=duracion)).strftime("%H:%M")
    print(f"\n  {AMARILLO}⚡ Foco: {tarea['name']}{R}")
    print(f"  {GRIS}{duracion} min  ·  termina ~{termina}{R}")
    input(f"  {GRIS}Enter...{R}")


def accion_foco_directo(tareas):
    """Foco directo en la tarea top del plan sin preguntar nada."""
    candidatas = [t for t in tareas if t["estado"] == "hoy"]
    if not candidatas:
        return
    tarea = sorted(candidatas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)[0]

    tarea["_estado_previo"]     = tarea["estado"]
    tarea["estado"]             = "en_foco"
    tarea["foco_inicio"]        = datetime.now().isoformat()
    tarea["foco_duracion"]      = 90
    tarea["minutos_acumulados"] = tarea.get("minutos_acumulados", 0)
    guardar_tareas(tareas)
    refrescar_waybar()

    termina = (datetime.now() + timedelta(minutes=90)).strftime("%H:%M")
    print(f"\n  {AMARILLO}⚡ Foco directo: {tarea['name']}{R}")
    print(f"  {GRIS}90 min  ·  termina ~{termina}{R}")
    input(f"  {GRIS}Enter...{R}")


def accion_cerrar_foco(tareas):
    foco = foco_activo(tareas)
    if not foco:
        return

    limpiar()
    seccion("Cerrar Bloque de Foco", AMARILLO)
    linea()

    elapsed  = minutos_en_foco(foco)
    planned  = foco.get("foco_duracion", 90)
    pct      = min(100, int(elapsed / planned * 100))
    barra    = barra_progreso(pct)

    print(f"\n  {BLANCO}{BOLD}{nombre_corto(foco['name'],46)}{R}")
    print(f"  {barra}  {elapsed}/{planned} min")

    print(f"\n  {VERDE}[l]{R} lista   {CYAN}[s]{R} sigue pendiente   {AMARILLO}[h]{R} sigue en hoy\n")
    print(f"  {GRIS}tecla → {R}", end="", flush=True)
    ch = leer_tecla()
    print(ch or "")

    hist = cargar_historial()
    hist.append({
        "tarea_id": foco["id"],
        "tarea_nombre": foco["name"],
        "fecha":   date.today().isoformat(),
        "inicio":  foco.get("foco_inicio"),
        "fin":     datetime.now().isoformat(),
        "minutos_reales": elapsed,
        "minutos_plan":   planned,
        "resultado": ch,
    })
    guardar_historial(hist)

    for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
        foco.pop(campo, None)

    if ch == "l":
        foco["estado"]     = "listo"
        foco["completado"] = date.today().isoformat()
        print(f"\n  {VERDE}✓ ¡Completada!{R}")
        mostrar_desbloqueadas(foco["id"], tareas)
    elif ch == "h":
        foco["estado"] = "hoy"
        print(f"\n  {AMARILLO}→ Sigue en el plan de hoy.{R}")
    else:
        foco["estado"] = "pendiente"
        foco.pop("fecha_activacion", None)
        print(f"\n  {CYAN}→ Vuelve a pendientes.{R}")

    guardar_tareas(tareas)
    refrescar_waybar()
    input(f"\n  {GRIS}Enter...{R}")


def accion_marcar_lista(tareas):
    activas = [t for t in tareas if t["estado"] in ("hoy","pendiente","en_foco")]
    if not activas:
        return

    limpiar()
    seccion("Marcar como lista", VERDE)
    linea()
    print()
    for i, t in enumerate(activas):
        tipo = etiqueta_tipo(t.get("tipo","fondo"))
        print(f"  {GRIS}{i+1}.{R}  {tipo}  {BLANCO}{nombre_corto(t['name'],44)}{R}  {GRIS}[{t['estado']}]{R}")

    raw = leer_linea(f"\n  {GRIS}Número (Enter = cancelar):{R} ").strip()
    if not raw:
        return
    try:
        tarea = activas[int(raw)-1]
    except (ValueError, IndexError):
        return

    for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
        tarea.pop(campo, None)
    tarea["estado"]     = "listo"
    tarea["completado"] = date.today().isoformat()
    guardar_tareas(tareas)
    refrescar_waybar()

    print(f"\n  {VERDE}✓ '{nombre_corto(tarea['name'],40)}' lista{R}")
    mostrar_desbloqueadas(tarea["id"], tareas)
    input(f"\n  {GRIS}Enter...{R}")


def accion_cierre_dia(tareas):
    activas = [t for t in tareas if t["estado"] in ("hoy","en_foco")]
    if not activas:
        print(f"\n  {VERDE}No hay tareas activas sin resolver{R}\n")
    else:
        limpiar()
        seccion("Cierre de Día", MAGENTA)
        linea()
        print(f"\n  {AMARILLO}{len(activas)} tarea/s sin completar:{R}\n")

        for t in activas:
            for campo in ("foco_inicio","foco_duracion","_estado_previo"):
                t.pop(campo, None)
            tipo = etiqueta_tipo(t.get("tipo","fondo"))
            print(f"  {tipo}  {BLANCO}{BOLD}{nombre_corto(t['name'],44)}{R}")
            print(f"  {CYAN}[p]{R} pendiente   {VERDE}[l]{R} lista\n")
            print(f"  {GRIS}tecla → {R}", end="", flush=True)
            ch = leer_tecla()
            print(ch or "")
            if ch == "l":
                t["estado"]     = "listo"
                t["completado"] = date.today().isoformat()
                print(f"  {VERDE}  → Lista{R}")
            else:
                t["estado"] = "pendiente"
                t.pop("fecha_activacion", None)
                print(f"  {CYAN}  → Pendiente{R}")
            print()

        guardar_tareas(tareas)

    refrescar_waybar()
    print(f"\n  {BOLD}Día cerrado.{R}")
    input(f"  {GRIS}Enter...{R}")


def accion_historial():
    limpiar()
    seccion("Historial de Bloques de Foco", MAGENTA)
    linea()

    hist = cargar_historial()
    if not hist:
        print(f"\n  {GRIS}Sin bloques registrados.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    by_fecha = {}
    for b in hist:
        by_fecha.setdefault(b.get("fecha","?"), []).append(b)

    total_acum = sum(b.get("minutos_reales", 0) for b in hist)
    print(f"\n  {GRIS}Total: {MAGENTA}{total_acum//60}h {total_acum%60}m{R}  ({len(hist)} bloques)\n")

    for fecha in sorted(by_fecha.keys(), reverse=True)[:10]:
        bloques   = by_fecha[fecha]
        total_dia = sum(b.get("minutos_reales", 0) for b in bloques)
        print(f"  {CYAN}{fecha}{R}  {GRIS}{total_dia} min — {len(bloques)} bloque/s{R}")
        for b in bloques:
            icono = {"l":"✓","s":"↩","h":"↻","m":"↻"}.get(b.get("resultado","?"),"?")
            real  = b.get("minutos_reales", 0)
            plan_ = b.get("minutos_plan", 90)
            print(f"    {GRIS}{icono}{R} {BLANCO}{nombre_corto(b.get('tarea_nombre','?'),38)}{R}  {GRIS}{real}/{plan_} min{R}")
        print()

    input(f"  {GRIS}Enter...{R}")


def mostrar_desbloqueadas(tarea_id, tareas):
    recien = [t for t in tareas if tarea_id in t.get("depende_de", []) and t["estado"] != "listo"]
    if recien:
        print(f"\n  {CYAN}Desbloqueadas:{R}")
        for u in recien:
            p = calcular_prioridad(u, tareas)
            print(f"    → [{u['id']}] {u['name']} (p={p:.3f})")


def accion_dependencias(tareas):
    activas = [t for t in tareas if t["estado"] in ("pendiente", "hoy", "en_foco")]
    if not activas:
        print(f"  {AMARILLO}No hay tareas activas.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    limpiar()
    seccion("Editar dependencias", CYAN)
    linea()
    print()
    for i, t in enumerate(activas):
        tipo = etiqueta_tipo(t.get("tipo","fondo"))
        cat  = etiqueta_cat(t.get("categoria","personal"))
        dep  = f"  {GRIS}deps: {t.get('depende_de', [])}{R}" if t.get("depende_de") else ""
        print(f"  {GRIS}{i+1}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],36)}{R}{dep}")

    raw = leer_linea(f"\n  {GRIS}Número de tarea:{R} ").strip()
    if not raw:
        return
    try:
        tarea = activas[int(raw)-1]
    except (ValueError, IndexError):
        return

    limpiar()
    seccion(f"Dependencias de: {nombre_corto(tarea['name'],40)}", CYAN)
    linea()

    otras = [t for t in tareas if t["id"] != tarea["id"] and t["estado"] != "listo"]
    if not otras:
        print(f"\n  {GRIS}No hay otras tareas para elegir.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    print()
    for i, t in enumerate(otras):
        marcado = f"{CYAN}[x]{R}" if t["id"] in tarea.get("depende_de", []) else f"{GRIS}[ ]{R}"
        tipo = etiqueta_tipo(t.get("tipo","fondo"))
        cat  = etiqueta_cat(t.get("categoria","personal"))
        print(f"  {marcado}  {GRIS}{i+1:2}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],36)}{R}")

    print(f"\n  {GRIS}Números (coma): marca/desmarca. Enter = guardar.{R}")
    raw = leer_linea(f"\n  {GRIS}números:{R} ").strip()
    if raw:
        deps = []
        for s in raw.split(","):
            try:
                dep = otras[int(s.strip())-1]
                deps.append(dep["id"])
            except (ValueError, IndexError):
                pass
        tarea["depende_de"] = deps
        guardar_tareas(tareas)
        print(f"  {VERDE}✓ {len(deps)} dependencia/s guardadas{R}")
    input(f"  {GRIS}Enter...{R}")


def refrescar_waybar():
    try:
        subprocess.run(["pkill", "-SIGRTMIN+8", "waybar"], check=False, capture_output=True)
    except FileNotFoundError:
        pass


# ── Rofi UI ──────────────────────────────────────────────────────────────

def _rofi_tarea(tarea, tareas):
    tipo = ICONOS_TIPO.get(tarea.get("tipo","fondo"),"●")
    dias = dias_hasta(tarea.get("limite"))
    d_fmt = f"{int(dias)}d" if tarea.get("limite") else "∞"
    p = calcular_prioridad(tarea, tareas)
    estado = tarea["estado"]

    menu = [
        (f"  {tarea['name']}", _K_HEADER),
        (f"  {tipo} {tarea.get('tipo','')}  [{estado}]  {d_fmt}  p={p:.2f}", _K_HEADER),
        ("", _K_HEADER),
    ]
    if estado in ("hoy", "pendiente"):
        menu.append(("[t]  toggle hoy / pendiente", "toggle"))
    if estado == "hoy" and not foco_activo(tareas):
        menu.append(("[f]  iniciar foco", "iniciar_foco"))
    if estado == "en_foco":
        menu.append(("[c]  cerrar foco", "cerrar_foco"))
    menu.append(("[l]  marcar lista", "marcar_lista"))
    menu.append(("[d]  editar dependencias", "dependencias"))
    if estado in ("hoy", "en_foco"):
        menu.append(("[s]  saltear → pendiente", "saltar"))
    menu.append(("[←]  volver", "volver"))

    acc = _menu(menu, prompt=tarea["name"][:20])
    if acc is None or acc == "volver":
        return

    tareas = cargar_tareas()
    tarea = next((t for t in tareas if t["id"] == tarea["id"]), None)
    if tarea is None:
        return

    if acc == "toggle":
        if tarea["estado"] == "hoy":
            tarea["estado"] = "pendiente"
            tarea.pop("fecha_activacion", None)
        else:
            tarea["estado"] = "hoy"
            tarea["fecha_activacion"] = date.today().isoformat()
        guardar_tareas(tareas)
        refrescar_waybar()
        _rofi_msg(f"✓ '{tarea['name'][:30]}' → {tarea['estado']}")

    elif acc == "iniciar_foco":
        _rofi_iniciar_foco(tareas, tarea)
    elif acc == "cerrar_foco":
        _rofi_cerrar_foco(tareas, tarea)
    elif acc == "marcar_lista":
        for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
            tarea.pop(campo, None)
        tarea["estado"] = "listo"
        tarea["completado"] = date.today().isoformat()
        guardar_tareas(tareas)
        refrescar_waybar()
        _rofi_msg(f"✓ '{tarea['name'][:30]}' lista!")
    elif acc == "dependencias":
        _rofi_dependencias(tareas, tarea)
    elif acc == "saltar":
        for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
            tarea.pop(campo, None)
        tarea["estado"] = "pendiente"
        tarea.pop("fecha_activacion", None)
        guardar_tareas(tareas)
        refrescar_waybar()
        _rofi_msg(f"↩ '{tarea['name'][:30]}' → pendiente")


def _rofi_nueva(tareas=None):
    if tareas is None:
        tareas = cargar_tareas()

    raw = _rofi_in("nombre [| tipo | categoria | fecha]")
    if raw is None:
        return

    partes = [p.strip() for p in raw.split("|")]
    nombre = partes[0]
    if not nombre:
        _rofi_msg("Nombre requerido")
        return

    tipo = "intensiva"
    if len(partes) > 1 and partes[1]:
        tipo = {"c": "critica", "i": "intensiva", "f": "fondo"}.get(partes[1].lower(), partes[1])
        if tipo not in TIPOS:
            tipo = "intensiva"
    else:
        sel = _menu([
            ("[c]  critica", "critica"),
            ("[i]  intensiva", "intensiva"),
            ("[f]  fondo", "fondo"),
        ], "tipo")
        if sel:
            tipo = sel

    categoria = "personal"
    if len(partes) > 2 and partes[2]:
        cats = list(CATEGORIAS.keys())
        try:
            idx = int(partes[2]) - 1
            categoria = cats[idx] if 0 <= idx < len(cats) else "personal"
        except ValueError:
            categoria = partes[2].lower() if partes[2].lower() in CATEGORIAS else "personal"
    else:
        sel = _menu([
            ("[1]  universidad", "universidad"),
            ("[2]  software", "software"),
            ("[3]  learning", "learning"),
            ("[4]  personal", "personal"),
        ], "categoria")
        if sel:
            categoria = sel

    limite = None
    if len(partes) > 3 and partes[3]:
        try:
            date.fromisoformat(partes[3].strip())
            limite = partes[3].strip()
        except ValueError:
            pass
    else:
        r = _rofi_in("fecha límite AAAA-MM-DD (opcional)")
        if r:
            try:
                date.fromisoformat(r)
                limite = r
            except ValueError:
                _rofi_msg("Fecha inválida")

    tarea = {
        "id": proximo_id(tareas), "name": nombre, "notas": None,
        "estado": "pendiente", "creado": date.today().isoformat(),
        "categoria": categoria, "tipo": tipo, "limite": limite,
        "urgencia": 5, "depende_de": [],
    }
    tareas.append(tarea)
    guardar_tareas(tareas)
    refrescar_waybar()
    _rofi_msg(f"✓ [{tarea['id']}] '{nombre}' ({tipo}/{categoria})")

    activas = [t for t in tareas if t["estado"] in ("pendiente", "hoy") and t["id"] != tarea["id"]]
    if activas:
        ordenadas = sorted(activas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
        dep_items = [("(ninguna, Enter)", "ninguna")]
        for i, t in enumerate(ordenadas):
            dep_items.append((f"{i+1:2}. {ICONOS_TIPO.get(t.get('tipo',''),'●')} {t['name'][:40]}", i))
        sel = _menu(dep_items, "¿depende de?")
        if sel is not None and sel != "ninguna":
            tarea["depende_de"].append(ordenadas[sel]["id"])
            guardar_tareas(tareas)
            _rofi_msg(f"✓ Dependencia: {ordenadas[sel]['name'][:30]}")


def _rofi_iniciar_foco(tareas=None, tarea=None):
    if tareas is None:
        tareas = cargar_tareas()
    candidatas = [t for t in tareas if t["estado"] == "hoy"]
    if not candidatas:
        _rofi_msg("No hay tareas en HOY")
        return
    ordenadas = sorted(candidatas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)

    if tarea is None:
        items = [(f"{i+1:2}. {ICONOS_TIPO.get(t.get('tipo',''),'●')} {t['name'][:40]}", i) for i, t in enumerate(ordenadas)]
        sel = _menu(items, "iniciar foco")
        if sel is None:
            return
        tarea = ordenadas[sel]

    dur = _rofi_in("duración (Enter=90)")
    try:
        duracion = max(5, int(dur)) if dur else 90
    except ValueError:
        duracion = 90

    tarea["_estado_previo"] = tarea["estado"]
    tarea["estado"] = "en_foco"
    tarea["foco_inicio"] = datetime.now().isoformat()
    tarea["foco_duracion"] = duracion
    tarea["minutos_acumulados"] = tarea.get("minutos_acumulados", 0)
    guardar_tareas(tareas)
    refrescar_waybar()
    termina = (datetime.now() + timedelta(minutes=duracion)).strftime("%H:%M")
    _rofi_msg(f"⚡ Foco: {tarea['name'][:30]}\n{duracion} min · termina ~{termina}")


def _rofi_foco_directo(tareas=None):
    if tareas is None:
        tareas = cargar_tareas()
    candidatas = [t for t in tareas if t["estado"] == "hoy"]
    if not candidatas:
        _rofi_msg("No hay tareas en HOY")
        return
    tarea = sorted(candidatas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)[0]
    tarea["_estado_previo"] = tarea["estado"]
    tarea["estado"] = "en_foco"
    tarea["foco_inicio"] = datetime.now().isoformat()
    tarea["foco_duracion"] = 90
    tarea["minutos_acumulados"] = tarea.get("minutos_acumulados", 0)
    guardar_tareas(tareas)
    refrescar_waybar()
    termina = (datetime.now() + timedelta(minutes=90)).strftime("%H:%M")
    _rofi_msg(f"⚡ Foco directo: {tarea['name'][:30]}\n90 min · termina ~{termina}")


def _rofi_cerrar_foco(tareas=None, tarea=None):
    if tareas is None:
        tareas = cargar_tareas()
    if tarea is None:
        tarea = foco_activo(tareas)
    if tarea is None:
        _rofi_msg("No hay foco activo")
        return

    elapsed = minutos_en_foco(tarea)
    planned = tarea.get("foco_duracion", 90)
    pct = min(100, int(elapsed / planned * 100))

    acc = _menu([
        (f"'{tarea['name'][:30]}'  {elapsed}/{planned}m ({pct}%)", _K_HEADER),
        ("", _K_HEADER),
        ("[l]  marcar lista ✓", "lista"),
        ("[s]  sigue pendiente", "pendiente"),
        ("[h]  sigue en hoy", "hoy"),
        ("[←]  cancelar", "cancelar"),
    ], "cerrar foco")
    if acc is None or acc == "cancelar":
        return

    hist = cargar_historial()
    hist.append({
        "tarea_id": tarea["id"], "tarea_nombre": tarea["name"],
        "fecha": date.today().isoformat(), "inicio": tarea.get("foco_inicio"),
        "fin": datetime.now().isoformat(), "minutos_reales": elapsed,
        "minutos_plan": planned,
        "resultado": {"lista": "l", "pendiente": "s", "hoy": "h"}.get(acc, "?"),
    })
    guardar_historial(hist)

    for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
        tarea.pop(campo, None)

    if acc == "lista":
        tarea["estado"] = "listo"
        tarea["completado"] = date.today().isoformat()
        _rofi_msg(f"✓ '{tarea['name'][:30]}' lista!")
    elif acc == "hoy":
        tarea["estado"] = "hoy"
        _rofi_msg(f"↻ '{tarea['name'][:30]}' sigue en HOY")
    else:
        tarea["estado"] = "pendiente"
        tarea.pop("fecha_activacion", None)
        _rofi_msg(f"↩ '{tarea['name'][:30]}' → pendiente")

    guardar_tareas(tareas)
    refrescar_waybar()


def _rofi_toggle_hoy(tareas=None):
    if tareas is None:
        tareas = cargar_tareas()
    todas = [t for t in tareas if t["estado"] in ("pendiente", "hoy")]
    if not todas:
        _rofi_msg("No hay tareas pendientes ni en HOY")
        return

    ordenadas = sorted(todas, key=lambda t: (
        0 if t["estado"] == "hoy" else 1, -calcular_prioridad(t, tareas)
    ))

    while True:
        items = [("(terminar)", "terminar")]
        for i, t in enumerate(ordenadas):
            estado_tag = "📋" if t["estado"] == "hoy" else "📦"
            tipo = ICONOS_TIPO.get(t.get("tipo","fondo"),"●")
            dias = dias_hasta(t.get("limite"))
            d_fmt = f"{int(dias)}d" if t.get("limite") else "∞"
            bloq = " 🔒" if esta_bloqueada(t, tareas) else ""
            items.append((f"{i+1:2}. {tipo} {estado_tag} {t['name'][:36]}  {d_fmt}{bloq}", i))
        sel = _menu(items, "toggle hoy/pendiente")
        if sel is None or sel == "terminar":
            return

        tareas = cargar_tareas()
        tarea = next((t for t in tareas if t["id"] == ordenadas[sel]["id"]), None)
        if tarea is None:
            return
        if tarea["estado"] == "hoy":
            tarea["estado"] = "pendiente"
            tarea.pop("fecha_activacion", None)
        else:
            tarea["estado"] = "hoy"
            tarea["fecha_activacion"] = date.today().isoformat()
        guardar_tareas(tareas)
        refrescar_waybar()


def _rofi_marcar_lista(tareas=None):
    if tareas is None:
        tareas = cargar_tareas()
    activas = [t for t in tareas if t["estado"] in ("hoy","pendiente","en_foco")]
    if not activas:
        _rofi_msg("No hay tareas activas")
        return

    items = [(f"{i+1:2}. {ICONOS_TIPO.get(t.get('tipo','fondo'),'●')} {t['name'][:40]}  [{t['estado']}]", i) for i, t in enumerate(activas)]
    sel = _menu(items, "marcar lista")
    if sel is None:
        return

    tareas = cargar_tareas()
    tarea = next((t for t in tareas if t["id"] == activas[sel]["id"]), None)
    if tarea is None:
        return
    for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
        tarea.pop(campo, None)
    tarea["estado"] = "listo"
    tarea["completado"] = date.today().isoformat()
    guardar_tareas(tareas)
    refrescar_waybar()
    _rofi_msg(f"✓ '{tarea['name'][:30]}' lista!")


def _rofi_dependencias(tareas=None, tarea=None):
    if tareas is None:
        tareas = cargar_tareas()

    activas = [t for t in tareas if t["estado"] in ("pendiente", "hoy", "en_foco")]
    if tarea is None:
        if not activas:
            _rofi_msg("No hay tareas activas")
            return
        items = [(f"{i+1:2}. {ICONOS_TIPO.get(t.get('tipo','fondo'),'●')} {t['name'][:36]}", i) for i, t in enumerate(activas)]
        sel = _menu(items, "editar deps de")
        if sel is None:
            return
        tarea = activas[sel]

    tareas = cargar_tareas()
    tarea = next((t for t in tareas if t["id"] == tarea["id"]), None)
    if tarea is None:
        return

    otras = [t for t in tareas if t["id"] != tarea["id"] and t["estado"] != "listo"]
    if not otras:
        _rofi_msg("No hay otras tareas")
        return

    while True:
        deps_actuales = set(tarea.get("depende_de", []))
        items = [("(guardar y volver)", "guardar")]
        for i, t in enumerate(otras):
            marcado = "✓" if t["id"] in deps_actuales else " "
            items.append((f"[{marcado}] {i+1:2}. {ICONOS_TIPO.get(t.get('tipo','fondo'),'●')} {t['name'][:36]}", i))
        sel = _menu(items, f"deps de {tarea['name'][:16]}")
        if sel is None or sel == "guardar":
            break
        dep_tarea = otras[sel]
        if dep_tarea["id"] in deps_actuales:
            tarea["depende_de"].remove(dep_tarea["id"])
        else:
            tarea["depende_de"].append(dep_tarea["id"])
        guardar_tareas(tareas)

    guardar_tareas(tareas)
    refrescar_waybar()


def _rofi_cierre_dia(tareas=None):
    if tareas is None:
        tareas = cargar_tareas()
    activas = [t for t in tareas if t["estado"] in ("hoy", "en_foco")]
    if not activas:
        _rofi_msg("✓ No hay tareas activas sin resolver")
        refrescar_waybar()
        return

    for tarea in activas:
        for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
            tarea.pop(campo, None)
        acc = _menu([
            (f"{ICONOS_TIPO.get(tarea.get('tipo','fondo'),'●')}  {tarea['name'][:40]}", _K_HEADER),
            ("", _K_HEADER),
            ("[l]  marcar lista ✓", "lista"),
            ("[p]  → pendiente", "pendiente"),
        ], f"cierre: {tarea['name'][:16]}")
        if acc is None:
            acc = "pendiente"
        if acc == "lista":
            tarea["estado"] = "listo"
            tarea["completado"] = date.today().isoformat()
        else:
            tarea["estado"] = "pendiente"
            tarea.pop("fecha_activacion", None)
        guardar_tareas(tareas)

    refrescar_waybar()
    _rofi_msg("✓ Día cerrado")


def _rofi_historial():
    hist = cargar_historial()
    if not hist:
        _rofi_msg("Sin bloques de foco registrados")
        return

    total_min = sum(b.get("minutos_reales", 0) for b in hist)
    items = [(f"Total: {total_min//60}h {total_min%60}m  ({len(hist)} bloques)", _K_HEADER)]
    by_fecha = {}
    for b in hist:
        by_fecha.setdefault(b.get("fecha","?"), []).append(b)
    for fecha in sorted(by_fecha.keys(), reverse=True)[:10]:
        bloques = by_fecha[fecha]
        dia_min = sum(b.get("minutos_reales", 0) for b in bloques)
        items.append((f"── {fecha}  ({dia_min}m) ──", _K_HEADER))
        for b in bloques:
            icono = {"l":"✓","s":"↩","h":"↻","m":"↻"}.get(b.get("resultado","?"),"?")
            real = b.get("minutos_reales", 0)
            plan_ = b.get("minutos_plan", 90)
            items.append((f"  {icono}  {b.get('tarea_nombre','?')[:36]}  ({real}/{plan_}m)", _K_HEADER))
    items.append(("", _K_HEADER))
    items.append(("[Enter]  cerrar", _K_HEADER))
    _menu(items, "historial")


def cmd_rofi():
    while True:
        tareas = cargar_tareas()
        foco = foco_activo(tareas)
        activas = [t for t in tareas if t["estado"] in ("pendiente", "hoy")]
        ordenadas = sorted(activas, key=lambda t: (
            0 if t["estado"] == "hoy" else 1, -calcular_prioridad(t, tareas)
        ))

        menu = []
        if foco:
            elapsed = int(minutos_en_foco(foco))
            planned = foco.get("foco_duracion", 90)
            pct = min(100, int(elapsed / planned * 100))
            menu.append((f"⚡ {foco['name']} · {elapsed}/{planned}m ({pct}%)", "foco_abrir"))

        if not ordenadas and not foco:
            menu.append(("📭 Sin tareas activas", _K_HEADER))

        for i, t in enumerate(ordenadas):
            tipo = ICONOS_TIPO.get(t.get("tipo","fondo"),"●")
            dias = dias_hasta(t.get("limite"))
            d_fmt = f"{int(dias)}d" if t.get("limite") else "∞"
            estado_tag = "📋" if t["estado"] == "hoy" else "📦"
            bloq = " 🔒" if esta_bloqueada(t, tareas) else ""
            menu.append((f"{i+1:2}. {tipo} {estado_tag} {t['name'][:36]}  {d_fmt}{bloq}", ("tarea", i)))

        menu.append(("── ACCIONES ──", _K_HEADER))
        menu.append(("[n]  nueva tarea", "nueva"))
        hoy_tasks = [t for t in tareas if t["estado"] == "hoy"]
        if hoy_tasks:
            menu.append(("[f]  iniciar foco", "iniciar_foco"))
            menu.append(("[F]  foco directo", "foco_directo"))
        if foco:
            menu.append(("[c]  cerrar foco", "cerrar_foco"))
        if activas:
            menu.append(("[p]  toggle hoy / pendiente", "toggle_hoy"))
            menu.append(("[l]  marcar lista", "marcar_lista"))
            menu.append(("[d]  editar dependencias", "dependencias"))
        fin_dia = [t for t in tareas if t["estado"] in ("hoy", "en_foco")]
        if fin_dia:
            menu.append(("[z]  cierre de día", "cierre_dia"))
        menu.append(("[h]  historial", "historial"))
        menu.append(("[q]  salir", "salir"))

        acc = _menu(menu)
        if acc is None or acc == _K_HEADER:
            if acc is None:
                break
            continue

        if acc == "salir":
            break
        elif isinstance(acc, tuple) and acc[0] == "tarea":
            _, idx = acc
            tareas = cargar_tareas()
            activas = [t for t in tareas if t["estado"] in ("pendiente", "hoy")]
            ordenadas = sorted(activas, key=lambda t: (
                0 if t["estado"] == "hoy" else 1, -calcular_prioridad(t, tareas)
            ))
            if idx < len(ordenadas):
                _rofi_tarea(ordenadas[idx], tareas)
        elif acc == "foco_abrir":
            tareas = cargar_tareas()
            foco = foco_activo(tareas)
            if foco:
                _rofi_tarea(foco, tareas)
        else:
            tareas = cargar_tareas()
            {
                "nueva": _rofi_nueva,
                "iniciar_foco": _rofi_iniciar_foco,
                "foco_directo": _rofi_foco_directo,
                "cerrar_foco": _rofi_cerrar_foco,
                "toggle_hoy": _rofi_toggle_hoy,
                "marcar_lista": _rofi_marcar_lista,
                "dependencias": _rofi_dependencias,
                "cierre_dia": _rofi_cierre_dia,
                "historial": _rofi_historial,
            }.get(acc, lambda: None)(tareas)


def cmd_tui():
    while True:
        limpiar()
        tareas = cargar_tareas()
        foco   = foco_activo(tareas)

        hoy_str = date.today().strftime("%A %d %b").capitalize()
        print(f"\n  {BOLD}{CYAN}SCHEDULER{R}  {GRIS}{hoy_str}{R}", end="")
        mostrar_stats_rapidas(tareas)
        linea()

        if foco:
            mostrar_foco(foco)

        mostrar_hoy(tareas)
        mostrar_pendientes(tareas)
        mostrar_completadas_recientes(tareas)

        opciones = construir_menu(tareas, foco)
        mostrar_menu(opciones)

        tecla = leer_tecla()
        if tecla is None:
            continue

        accion_map = {op[0]: op[2] for op in opciones}

        accion = accion_map.get(tecla)
        if accion == "salir" or tecla == "q":
            limpiar()
            break
        elif accion == "nueva":
            tareas = cargar_tareas()
            accion_nueva(tareas)
        elif accion == "toggle_hoy":
            tareas = cargar_tareas()
            accion_toggle_hoy(tareas)
        elif accion == "iniciar_foco":
            tareas = cargar_tareas()
            accion_iniciar_foco(tareas)
        elif accion == "foco_directo":
            tareas = cargar_tareas()
            accion_foco_directo(tareas)
        elif accion == "cerrar_foco":
            tareas = cargar_tareas()
            accion_cerrar_foco(tareas)
        elif accion == "marcar_lista":
            tareas = cargar_tareas()
            accion_marcar_lista(tareas)
        elif accion == "dependencias":
            tareas = cargar_tareas()
            accion_dependencias(tareas)
        elif accion == "cierre_dia":
            tareas = cargar_tareas()
            accion_cierre_dia(tareas)
        elif accion == "historial":
            accion_historial()


def cmd_waybar():
    tareas = cargar_tareas()

    foco = foco_activo(tareas)
    if foco:
        elapsed   = int(minutos_en_foco(foco))
        planned   = foco.get("foco_duracion", 90)
        remaining = max(0, int(planned - elapsed))
        pct       = min(100, int(elapsed / planned * 100))
        icono     = ICONOS_CAT.get(foco.get("categoria","personal"), "⚡")
        nombre    = foco["name"][:20] + "…" if len(foco["name"]) > 20 else foco["name"]
        print(json.dumps({
            "text":    f"⚡ {icono} {nombre} · {remaining}m",
            "tooltip": f"EN FOCO: {foco['name']}\n{elapsed}/{planned} min ({pct}%)",
            "class":   "en_foco",
        }))
        return

    actual = tarea_principal(tareas)
    if not actual:
        pend_n = sum(1 for t in tareas if t["estado"] == "pendiente")
        print(json.dumps({
            "text":    "󰄭 Sin tareas" if not pend_n else f"󰄭 {pend_n} pendientes",
            "tooltip": f"{pend_n} tareas pendientes" if pend_n else "Sin tareas",
            "class":   "vacio" if not pend_n else "pendiente",
        }))
        return

    dias   = dias_hasta(actual.get("limite"))
    icono  = ICONOS_CAT.get(actual.get("categoria","personal"), "󰋙")
    nombre = actual["name"][:22] + "…" if len(actual["name"]) > 22 else actual["name"]

    if dias <= 0:
        clase, d_str = "vencida",  "¡VENCIDA!"
    elif dias <= 2:
        clase, d_str = "critica",  f"en {int(dias)}d"
    elif dias <= 7:
        clase, d_str = "alerta",   f"en {int(dias)}d"
    elif actual.get("limite"):
        clase, d_str = "normal",   f"en {int(dias)}d"
    else:
        clase, d_str = "normal",   "sin fecha"

    header = "<b>Siguiente tarea:</b>"
    lineas = [header]
    for i, t in enumerate(tareas_ordenadas(tareas)[:5]):
        p    = calcular_prioridad(t, tareas)
        d    = dias_hasta(t.get("limite"))
        d_s  = f"{int(d)}d" if t.get("limite") else "∞"
        bloq = " 🔒" if esta_bloqueada(t, tareas) else ""
        marca = "▶ " if t["id"] == actual["id"] else f"{i+1}. "
        tipo  = ICONOS_TIPO.get(t.get("tipo","fondo"),"")
        lineas.append(f"{marca}{tipo} {t['name']} [{d_s}] (p={p:.2f}){bloq}")

    print(json.dumps({
        "text":    f"{icono} {nombre} · {d_str}",
        "tooltip": "\n".join(lineas),
        "class":   clase,
    }))


def cmd_migrar():
    """Migra tareas del esquema anterior (bandeja/cola/descartado) al nuevo (pendiente)."""
    tareas = cargar_tareas()
    cambios = 0
    for t in tareas:
        if t.get("estado") in ("bandeja", "cola"):
            t["estado"] = "pendiente"
            cambios += 1
        if t.get("estado") == "descartado":
            t["estado"] = "pendiente"
            cambios += 1
        if t.get("estado") is None and t.get("status"):
            mapa = {"pending": "pendiente", "inbox": "pendiente", "backlog": "pendiente",
                    "active": "hoy", "in_progress": "en_foco", "done": "listo", "dropped": "pendiente"}
            t["estado"] = mapa.get(t.pop("status"), "pendiente")
            cambios += 1
        if not t.get("categoria"):
            t["categoria"] = "personal"
            cambios += 1
        if not t.get("tipo"):
            t["tipo"] = "intensiva"
            cambios += 1
    guardar_tareas(tareas)
    print(f"Migración completa — {len(tareas)} tareas, {cambios} cambios.")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "waybar":
        cmd_waybar()
    elif args[0] in ("tui", "list"):
        cmd_tui()
    elif args[0] == "rofi":
        cmd_rofi()
    elif args[0] == "migrar":
        cmd_migrar()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
scheduler — Centro de control personal.
Uso normal: scheduler tui   (o click en waybar)
Waybar:     scheduler        (sin args, devuelve JSON)
"""

import json
import sys
import os
import tty
import termios
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR   = Path.home() / "OneDrive" / "varios" / "scheduler"
BASE_DIR.mkdir(parents=True, exist_ok=True)
TASKS_FILE = BASE_DIR / "tasks.json"
PLAN_FILE  = BASE_DIR / "daily_plan.json"
FOCUS_FILE = BASE_DIR / "focus_blocks.json"

# Peso por tipo de tarea
TIPOS = {
    "critica":   5,
    "intensiva": 3,
    "fondo":     1,
}

# Peso por categoría
CATEGORIAS = {
    "universidad": 1,
    "software":    4,
    "learning":    3,
    "personal":    2,
}

ICONOS_CAT = {
    "universidad": "󰑴",
    "software":    "󰲋",
    "personal":    "󰋙",
    "trabajo":     "󰢮",
    "learning":    "󰿄",
}

ICONOS_TIPO = {
    "critica":   "●",   # rojo
    "intensiva": "●",   # amarillo
    "fondo":     "●",   # verde
}

# Colores ANSI
R = "\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"

def fg(r,g,b):   return f"\033[38;2;{r};{g};{b}m"
def bg(r,g,b):   return f"\033[48;2;{r};{g};{b}m"

# Paleta
ROJO    = fg(255, 100,  80)
NARANJA = fg(255, 165,  60)
AMARILLO= fg(255, 210,  80)
VERDE   = fg(100, 210, 120)
CYAN    = fg( 80, 200, 220)
AZUL    = fg(100, 150, 255)
MAGENTA = fg(200, 100, 255)
GRIS    = fg(120, 120, 130)
BLANCO  = fg(220, 220, 230)

# Color por tipo
COLOR_TIPO = {
    "critica":   ROJO,
    "intensiva": AMARILLO,
    "fondo":     VERDE,
}

# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTENCIA
# ══════════════════════════════════════════════════════════════════════════════
def cargar_tareas():
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE) as f:
        return json.load(f)

def guardar_tareas(tareas):
    with open(TASKS_FILE, "w") as f:
        json.dump(tareas, f, indent=2, ensure_ascii=False)

def cargar_plan():
    if not PLAN_FILE.exists():
        return None
    with open(PLAN_FILE) as f:
        return json.load(f)

def guardar_plan(plan):
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

def cargar_historial():
    if not FOCUS_FILE.exists():
        return []
    with open(FOCUS_FILE) as f:
        return json.load(f)

def guardar_historial(h):
    with open(FOCUS_FILE, "w") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)

def proximo_id(tareas):
    return max((t["id"] for t in tareas), default=0) + 1

# ══════════════════════════════════════════════════════════════════════════════
#  LÓGICA DE PLAN Y FOCO
# ══════════════════════════════════════════════════════════════════════════════
def plan_de_hoy():
    plan = cargar_plan()
    if not plan:
        return None
    if plan.get("fecha") != date.today().isoformat():
        return None
    return plan

def foco_activo(tareas):
    for t in tareas:
        if t.get("estado") == "en_foco":
            return t
    return None

def minutos_en_foco(tarea):
    inicio = tarea.get("foco_inicio")
    if not inicio:
        return 0
    delta = datetime.now() - datetime.fromisoformat(inicio)
    return int(delta.total_seconds() / 60)

# ══════════════════════════════════════════════════════════════════════════════
#  ALGORITMO EDF
# ══════════════════════════════════════════════════════════════════════════════
def dias_hasta(deadline_str):
    if not deadline_str:
        return 999
    d = date.fromisoformat(deadline_str)
    delta = (d - date.today()).days
    return delta if delta != 0 else 0.5

def esta_bloqueada(tarea, tareas):
    for dep_id in tarea.get("depende_de", []):
        dep = next((t for t in tareas if t["id"] == dep_id), None)
        if dep and dep["estado"] not in ("listo", "descartado"):
            return True
    return False

def calcular_prioridad(tarea, tareas):
    if tarea["estado"] in ("listo", "descartado", "bandeja"):
        return 0
    if esta_bloqueada(tarea, tareas):
        return 0

    dias        = dias_hasta(tarea.get("limite"))
    urgencia    = tarea.get("urgencia", 5)
    w_tipo      = TIPOS.get(tarea.get("tipo", "fondo"), 1)
    w_cat       = CATEGORIAS.get(tarea.get("categoria", "personal"), 1.0)

    # Suprimir universidad no urgente si hay otras cosas
    if tarea.get("categoria") == "universidad" and dias > 7 and urgencia <= 6:
        otras = [
            t for t in tareas
            if t["id"] != tarea["id"]
            and t["estado"] not in ("listo", "descartado", "bandeja")
            and t.get("categoria") != "universidad"
        ]
        if otras:
            return 0

    penalizacion = min(1.0, 30 / dias) if dias > 30 else 1.0
    p = (urgencia * w_tipo * w_cat * penalizacion) / max(dias, 0.1)

    if 0 < dias <= 7:
        p *= 1.5

    return round(p, 4)

def cola_ordenada(tareas):
    activas = [t for t in tareas if t["estado"] in ("cola", "hoy", "en_foco")]
    return sorted(activas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)

def tarea_principal(tareas):
    plan = plan_de_hoy()
    if plan:
        ids_plan = [plan["principal"]] + plan.get("secundarias", [])
        candidatas = [
            t for t in tareas
            if t["id"] in ids_plan and t["estado"] in ("hoy", "en_foco")
        ]
        if candidatas:
            return sorted(candidatas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)[0]
    for t in cola_ordenada(tareas):
        if not esta_bloqueada(t, tareas):
            return t
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  LECTURA DE TECLADO (sin Enter)
# ══════════════════════════════════════════════════════════════════════════════

def leer_tecla():
    """Lee un solo carácter sin necesitar Enter."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Secuencias de escape (flechas, etc.) — ignorar por ahora
        if ch == '\x1b':
            sys.stdin.read(2)
            return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
     # limpiar caracteres pendientes
    termios.tcflush(fd, termios.TCIFLUSH)
    return ch

def leer_linea(prompt=""):
    """Lee una línea normal (con Enter). Restaura el modo canónico."""
    print(prompt, end="", flush=True)
    return input()

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS DE DISPLAY
# ══════════════════════════════════════════════════════════════════════════════
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
    color = COLOR_TIPO.get(tipo, GRIS)
    return f"{color}{ICONOS_TIPO.get(tipo,'?')}{R}"

def etiqueta_cat(cat):
    return ICONOS_CAT.get(cat, "?")

def nombre_corto(nombre, max_len=38):
    return nombre[:max_len-1] + "…" if len(nombre) > max_len else nombre

# ══════════════════════════════════════════════════════════════════════════════
#  SECCIONES DE LA PANTALLA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
def mostrar_foco(foco):
    elapsed  = minutos_en_foco(foco)
    planned  = foco.get("foco_duracion", 90)
    remaining = max(0, planned - elapsed)
    pct      = min(100, int(elapsed / planned * 100))
    barra    = barra_progreso(pct)

    seccion("⚡  EN FOCO AHORA", AMARILLO)
    linea("─", AMARILLO)
    tipo_col = COLOR_TIPO.get(foco.get("tipo","fondo"), GRIS)
    print(f"  {tipo_col}{BOLD}{nombre_corto(foco['name'], 44)}{R}")
    print(f"  {barra}  {AMARILLO}{elapsed}m{R} transcurridos  ·  {CYAN}{remaining}m{R} restantes")
    linea("─", AMARILLO)

def mostrar_plan(tareas):
    plan = plan_de_hoy()
    if not plan:
        return False

    bloqueado_str = f" {ROJO}[CERRADO]{R}" if plan.get("cerrado") else f" {VERDE}[abierto]{R}"
    seccion(f"📋  PLAN DE HOY{bloqueado_str}", CYAN)

    ids_plan = [plan["principal"]] + plan.get("secundarias", [])
    numeracion = []
    for i, tid in enumerate(ids_plan):
        t = next((x for x in tareas if x["id"] == tid), None)
        if not t:
            continue
        slot_label = f"{MAGENTA}PRINCIPAL{R}" if i == 0 else f"{GRIS}  SEC {i}  {R}"
        tipo_col   = COLOR_TIPO.get(t.get("tipo","fondo"), GRIS)
        estado_str = {
            "hoy":       f"{CYAN}hoy{R}",
            "en_foco":   f"{AMARILLO}⚡ en foco{R}",
            "listo":     f"{VERDE}✓ listo{R}",
            "descartado":f"{GRIS}✗ descartado{R}",
        }.get(t["estado"], t["estado"])
        dias  = dias_hasta(t.get("limite"))
        d_fmt = formato_dias(dias, t.get("limite"))
        cat   = etiqueta_cat(t.get("categoria","personal"))

        print(f"  {slot_label}  {tipo_col}●{R} {cat} {BLANCO}{nombre_corto(t['name'],36)}{R}  {d_fmt}  {estado_str}")
        numeracion.append(t)
    return numeracion

def mostrar_bandeja(tareas):
    bandeja = [t for t in tareas if t["estado"] == "bandeja"]
    if not bandeja:
        return []
    seccion(f"📥  BANDEJA  ({len(bandeja)} sin procesar)", NARANJA)
    for t in bandeja:
        print(f"  {GRIS}○  {nombre_corto(t['name'], 50)}{R}  {DIM}{(t.get('notas') or '')[:30]}{R}")
    return bandeja

def mostrar_cola(tareas):
    cola = [t for t in tareas if t["estado"] == "cola"]
    if not cola:
        return []
    ordenadas = sorted(cola, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
    seccion(f"📦  COLA  ({len(cola)} tareas)", AZUL)

    numeracion = []
    for i, t in enumerate(ordenadas):
        p     = calcular_prioridad(t, tareas)
        dias  = dias_hasta(t.get("limite"))
        d_fmt = formato_dias(dias, t.get("limite"))
        tipo  = etiqueta_tipo(t.get("tipo","fondo"))
        cat   = etiqueta_cat(t.get("categoria","personal"))
        bloq  = f"  {GRIS}🔒{R}" if esta_bloqueada(t, tareas) else ""
        idx   = f"{GRIS}{i+1:2}.{R}"
        print(f"  {idx}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],34)}{R}  {d_fmt}  {GRIS}p={p:.2f}{R}{bloq}")
        numeracion.append(t)
    return numeracion

def mostrar_completadas_recientes(tareas):
    listas = [t for t in tareas if t["estado"] == "listo"]
    if not listas:
        return
    recientes = sorted(listas, key=lambda t: t.get("completado",""), reverse=True)[:3]
    print(f"\n{GRIS}  Completadas recientemente:")
    for t in recientes:
        print(f"    ✓  {nombre_corto(t['name'],44)}  {DIM}{t.get('completado','')}{R}")
    print(R, end="")

def mostrar_stats_rapidas(tareas):
    total_cola  = sum(1 for t in tareas if t["estado"] == "cola")
    total_hoy   = sum(1 for t in tareas if t["estado"] == "hoy")
    total_foco  = sum(1 for t in tareas if t["estado"] == "en_foco")
    total_listo = sum(1 for t in tareas if t["estado"] == "listo")
    bandeja_n   = sum(1 for t in tareas if t["estado"] == "bandeja")

    hist = cargar_historial()
    hoy_str = date.today().isoformat()
    min_hoy = sum(b.get("minutos_reales",0) for b in hist if b.get("fecha") == hoy_str)

    partes = []
    if bandeja_n:  partes.append(f"{NARANJA}📥 {bandeja_n} en bandeja{R}")
    if total_foco: partes.append(f"{AMARILLO}⚡ {total_foco} en foco{R}")
    if total_hoy:  partes.append(f"{CYAN}📋 {total_hoy} en plan{R}")
    if total_cola: partes.append(f"{AZUL}📦 {total_cola} en cola{R}")
    if total_listo:partes.append(f"{VERDE}✓ {total_listo} listos{R}")
    if min_hoy:    partes.append(f"{MAGENTA}⏱ {min_hoy}m foco hoy{R}")

    if partes:
        print(f"\n  {'  ·  '.join(partes)}")

# ══════════════════════════════════════════════════════════════════════════════
#  MENÚ CONTEXTUAL DINÁMICO
# ══════════════════════════════════════════════════════════════════════════════
def construir_menu(tareas, foco, plan, bandeja):
    """
    Devuelve lista de (tecla, descripción, acción_id) según el estado actual.
    Las acciones disponibles cambian según contexto.
    """
    opciones = []

    # Siempre disponible
    opciones.append(("n", "nueva tarea",     "nueva"))

    # Bandeja pendiente
    if bandeja:
        opciones.append(("i", f"procesar bandeja ({len(bandeja)})", "procesar"))

    # Foco activo: cerrar foco es prioritario
    if foco:
        opciones.append(("f", "cerrar bloque de foco", "cerrar_foco"))
    else:
        # Sin foco: opciones según si hay plan
        if plan:
            tareas_hoy = [t for t in tareas if t["estado"] == "hoy"]
            if tareas_hoy:
                opciones.append(("f", "iniciar foco",  "iniciar_foco"))
        else:
            cola = [t for t in tareas if t["estado"] == "cola"]
            if cola:
                opciones.append(("f", "iniciar foco desde cola", "iniciar_foco"))

    # Plan
    if not plan:
        cola = [t for t in tareas if t["estado"] == "cola"]
        if cola:
            opciones.append(("p", "armar plan de hoy", "armar_plan"))
    else:
        if not plan.get("cerrado"):
            opciones.append(("p", "cerrar plan del día", "cerrar_plan"))

    # Marcar como lista / descartar (solo si hay tareas activas)
    activas = [t for t in tareas if t["estado"] in ("hoy","cola","en_foco")]
    if activas:
        opciones.append(("l", "marcar como lista",   "marcar_lista"))
        opciones.append(("x", "descartar tarea",      "descartar"))

    # Cierre de día (solo si hay tareas en "hoy" o "en_foco")
    fin_dia = [t for t in tareas if t["estado"] in ("hoy","en_foco")]
    if fin_dia:
        opciones.append(("z", "cierre de día",        "cierre_dia"))

    # Historial siempre
    opciones.append(("h", "historial de foco",    "historial"))
    opciones.append(("q", "salir",                "salir"))

    return opciones

def mostrar_menu(opciones):
    print()
    linea("─", GRIS)
    partes = []
    for tecla, desc, _ in opciones:
        partes.append(f"{CYAN}{BOLD}[{tecla}]{R} {BLANCO}{desc}{R}")
    # Imprimir en filas de hasta 3
    por_fila = 3
    for i in range(0, len(partes), por_fila):
        fila = partes[i:i+por_fila]
        print("  " + "    ".join(fila))
    linea("─", GRIS)
    print(f"  {GRIS}tecla → {R}", end="", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
#  ACCIONES INTERACTIVAS
# ══════════════════════════════════════════════════════════════════════════════
def accion_nueva(tareas):
    limpiar()
    seccion("Nueva tarea → Bandeja", NARANJA)
    linea()
    print(f"  {GRIS}Solo el nombre es obligatorio. Clasificás después.{R}\n")

    nombre = leer_linea(f"  {BLANCO}Nombre:{R} ").strip()
    if not nombre:
        print(f"  {ROJO}Nombre requerido.{R}")
        input(f"  {GRIS}Enter para continuar...{R}")
        return

    notas = leer_linea(f"  {GRIS}Nota rápida (opcional):{R} ").strip() or None

    tarea = {
        "id":        proximo_id(tareas),
        "name":      nombre,
        "notas":     notas,
        "estado":    "bandeja",
        "creado":    date.today().isoformat(),
        "categoria": None,
        "tipo":      None,
        "limite":    None,
        "urgencia":  5,
        "depende_de": [],
    }
    tareas.append(tarea)
    guardar_tareas(tareas)
    print(f"\n  {VERDE}✓ [{tarea['id']}] '{nombre}' en bandeja{R}\n")
    input(f"  {GRIS}Enter para continuar...{R}")


def accion_procesar(tareas):
    bandeja = [t for t in tareas if t["estado"] == "bandeja"]
    if not bandeja:
        return

    for tarea in bandeja:
        limpiar()
        seccion(f"Procesar bandeja — {len(bandeja)} pendientes", NARANJA)
        linea()
        print(f"\n  {BLANCO}{BOLD}{nombre_corto(tarea['name'],52)}{R}")
        if tarea.get("notas"):
            print(f"  {GRIS}Nota: {tarea['notas']}{R}")

        print(f"\n  {CYAN}[b]{R} → cola   {GRIS}[x]{R} → descartar   {GRIS}[s]{R} → saltar\n")
        print(f"  {GRIS}tecla → {R}", end="", flush=True)
        ch = leer_tecla()
        print(ch or "")

        if ch == "x":
            motivo = leer_linea(f"  {GRIS}Motivo del descarte:{R} ").strip() or "sin motivo"
            tarea.update({"estado": "descartado", "descartado": date.today().isoformat(), "motivo_descarte": motivo})
            print(f"  {GRIS}✗ Descartada{R}")
            guardar_tareas(tareas)
            continue
        elif ch == "s":
            print(f"  {GRIS}→ Saltada{R}")
            continue

        # → cola: clasificar
        print(f"\n  {BOLD}Tipo:{R}  {ROJO}[c]{R} crítica   {AMARILLO}[i]{R} intensiva   {VERDE}[f]{R} fondo\n")
        print(f"  {GRIS}tecla → {R}", end="", flush=True)
        tipo_ch = leer_tecla()
        tipo = {"c": "critica", "i": "intensiva", "f": "fondo"}.get(tipo_ch, "fondo")
        print(tipo)

        print(f"\n  {BOLD}Categoría:{R}")
        cats = list(CATEGORIAS.keys())
        for idx, cat in enumerate(cats):
            print(f"    {CYAN}[{idx+1}]{R} {cat}")
        print(f"  {GRIS}número → {R}", end="", flush=True)
        cat_ch = leer_tecla()
        try:
            categoria = cats[int(cat_ch)-1]
        except (ValueError, IndexError):
            categoria = "personal"
        print(categoria)

        limite = leer_linea(f"\n  {GRIS}Límite AAAA-MM-DD (Enter para omitir):{R} ").strip() or None
        if limite:
            try:
                date.fromisoformat(limite)
            except ValueError:
                print(f"  {ROJO}Fecha inválida, ignorada.{R}")
                limite = None

        urg_raw = leer_linea(f"  {GRIS}Urgencia 1-10 [5]:{R} ").strip() or "5"
        try:
            urgencia = max(1, min(10, int(urg_raw)))
        except ValueError:
            urgencia = 5

        tarea.update({
            "estado":    "cola",
            "tipo":      tipo,
            "categoria": categoria,
            "limite":    limite,
            "urgencia":  urgencia,
            "procesado": date.today().isoformat(),
        })
        p = calcular_prioridad(tarea, tareas)
        print(f"\n  {VERDE}✓ → Cola  (prioridad: {p:.3f}){R}")
        guardar_tareas(tareas)

    print(f"\n  {VERDE}Bandeja procesada{R}")
    input(f"  {GRIS}Enter para continuar...{R}")


def accion_armar_plan(tareas):
    limpiar()
    seccion("Armar Plan de Hoy", CYAN)
    linea()

    cola = [t for t in tareas if t["estado"] == "cola" and not esta_bloqueada(t, tareas)]
    if not cola:
        print(f"  {AMARILLO}No hay tareas en la cola.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    ordenadas = sorted(cola, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
    print(f"\n  {BOLD}Cola ordenada por prioridad:{R}\n")
    for i, t in enumerate(ordenadas):
        p    = calcular_prioridad(t, tareas)
        tipo = etiqueta_tipo(t.get("tipo","fondo"))
        cat  = etiqueta_cat(t.get("categoria","personal"))
        dias = dias_hasta(t.get("limite"))
        d_fmt= formato_dias(dias, t.get("limite"))
        print(f"  {GRIS}{i+1:2}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],34)}{R}  {d_fmt}  {GRIS}p={p:.2f}{R}")

    print(f"\n  {MAGENTA}PRINCIPAL{R} — 1 tarea (crítica o intensiva recomendada)")
    pid_raw = leer_linea(f"  {GRIS}Número:{R} ").strip()
    try:
        principal = ordenadas[int(pid_raw)-1]
    except (ValueError, IndexError):
        print(f"  {ROJO}Número inválido.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    if principal.get("tipo") == "fondo":
        print(f"  {AMARILLO}⚠ El slot principal funciona mejor con tareas críticas o intensivas.{R}")
        ch = leer_tecla() if leer_linea(f"  {GRIS}¿Continuar igual? [s/N]:{R} ").strip().lower() == "s" else "n"
        if ch == "n":
            input(f"  {GRIS}Enter...{R}")
            return

    secundarias_ids = []
    restantes = [t for t in ordenadas if t["id"] != principal["id"]]
    print(f"\n  {GRIS}SECUNDARIAS{R} — hasta 3 (Enter para terminar)")
    for slot in range(1, 4):
        raw = leer_linea(f"  Secundaria {slot} (número o Enter): ").strip()
        if not raw:
            break
        try:
            t = restantes[int(raw)-1]
            secundarias_ids.append(t["id"])
        except (ValueError, IndexError):
            print(f"  {GRIS}Número inválido, omitido.{R}")

    # Crear plan y mover tareas a "hoy"
    plan = {
        "fecha":       date.today().isoformat(),
        "cerrado":     False,
        "principal":   principal["id"],
        "secundarias": secundarias_ids,
        "creado_en":   datetime.now().isoformat(),
    }
    guardar_plan(plan)

    todos_ids = [principal["id"]] + secundarias_ids
    for t in tareas:
        if t["id"] in todos_ids:
            t["estado"] = "hoy"
            t["fecha_activacion"] = date.today().isoformat()
    guardar_tareas(tareas)

    total = len(todos_ids)
    print(f"\n  {VERDE}✓ Plan creado — {total} tarea/s activas para hoy{R}")
    print(f"  {GRIS}Usá [p] para cerrar el plan cuando empieces.{R}\n")
    input(f"  {GRIS}Enter para continuar...{R}")


def accion_cerrar_plan():
    plan = plan_de_hoy()
    if not plan:
        return
    plan["cerrado"]    = True
    plan["cerrado_en"] = datetime.now().isoformat()
    guardar_plan(plan)
    print(f"\n  {VERDE}✓ Plan cerrado — no se pueden agregar más tareas hoy.{R}\n")
    input(f"  {GRIS}Enter para continuar...{R}")


def accion_iniciar_foco(tareas):
    limpiar()
    seccion("Iniciar Bloque de Foco", AMARILLO)
    linea()

    plan = plan_de_hoy()
    if plan:
        candidatas = [t for t in tareas if t["estado"] == "hoy"]
    else:
        candidatas = [t for t in tareas if t["estado"] == "cola" and not esta_bloqueada(t, tareas)]

    if not candidatas:
        print(f"  {AMARILLO}No hay tareas disponibles para enfocar.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    ordenadas = sorted(candidatas, key=lambda t: calcular_prioridad(t, tareas), reverse=True)
    print()
    for i, t in enumerate(ordenadas):
        tipo = etiqueta_tipo(t.get("tipo","fondo"))
        cat  = etiqueta_cat(t.get("categoria","personal"))
        dias = dias_hasta(t.get("limite"))
        d_fmt= formato_dias(dias, t.get("limite"))
        print(f"  {GRIS}{i+1}.{R}  {tipo} {cat}  {BLANCO}{nombre_corto(t['name'],36)}{R}  {d_fmt}")

    raw = leer_linea(f"\n  {GRIS}Número de tarea:{R} ").strip()
    try:
        tarea = ordenadas[int(raw)-1]
    except (ValueError, IndexError):
        print(f"  {ROJO}Número inválido.{R}")
        input(f"  {GRIS}Enter...{R}")
        return

    dur_raw = leer_linea(f"  {GRIS}Duración en minutos [90]:{R} ").strip() or "90"
    try:
        duracion = max(5, int(dur_raw))
    except ValueError:
        duracion = 90

    tarea["_estado_previo"] = tarea["estado"]
    tarea["estado"]         = "en_foco"
    tarea["foco_inicio"]    = datetime.now().isoformat()
    tarea["foco_duracion"]  = duracion
    guardar_tareas(tareas)
    refrescar_waybar()

    termina = (datetime.now() + timedelta(minutes=duracion)).strftime("%H:%M")
    print(f"\n  {AMARILLO}⚡ Foco iniciado: {tarea['name']}{R}")
    print(f"  {GRIS}{duracion} min  ·  termina ~{termina}{R}\n")
    input(f"  {GRIS}Enter para continuar...{R}")


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

    print(f"\n  ¿Cómo terminó este bloque?\n")
    print(f"  {VERDE}[l]{R} Tarea lista       {CYAN}[s]{R} Sigue mañana (→ cola)   {AMARILLO}[m]{R} Necesita más bloques hoy\n")
    print(f"  {GRIS}tecla → {R}", end="", flush=True)
    ch = leer_tecla()
    print(ch or "")

    # Guardar en historial
    hist = cargar_historial()
    hist.append({
        "tarea_id":      foco["id"],
        "tarea_nombre":  foco["name"],
        "fecha":         date.today().isoformat(),
        "inicio":        foco.get("foco_inicio"),
        "fin":           datetime.now().isoformat(),
        "minutos_reales":elapsed,
        "minutos_plan":  planned,
        "resultado":     ch,
    })
    guardar_historial(hist)

    # Limpiar campos de foco
    for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
        foco.pop(campo, None)

    if ch == "l":
        foco["estado"]     = "listo"
        foco["completado"] = date.today().isoformat()
        print(f"\n  {VERDE}✓ ¡Tarea completada!{R}")
        mostrar_desbloqueadas(foco["id"], tareas)
    elif ch == "s":
        foco["estado"] = "cola"
        foco.pop("fecha_activacion", None)
        print(f"\n  {CYAN}→ Vuelve a la cola para mañana.{R}")
    else:
        foco["estado"] = "hoy" if plan_de_hoy() else "cola"
        print(f"\n  {AMARILLO}→ Sigue activa para otro bloque hoy.{R}")

    guardar_tareas(tareas)
    refrescar_waybar()
    input(f"\n  {GRIS}Enter para continuar...{R}")


def accion_marcar_lista(tareas):
    activas = [t for t in tareas if t["estado"] in ("hoy","cola","en_foco")]
    if not activas:
        return

    limpiar()
    seccion("Marcar como lista", VERDE)
    linea()
    print()
    for i, t in enumerate(activas):
        tipo = etiqueta_tipo(t.get("tipo","fondo"))
        print(f"  {GRIS}{i+1}.{R}  {tipo}  {BLANCO}{nombre_corto(t['name'],44)}{R}  {GRIS}[{t['estado']}]{R}")

    raw = leer_linea(f"\n  {GRIS}Número (o Enter para cancelar):{R} ").strip()
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

    print(f"\n  {VERDE}✓ '{nombre_corto(tarea['name'],40)}' lista 🎉{R}")
    mostrar_desbloqueadas(tarea["id"], tareas)
    input(f"\n  {GRIS}Enter para continuar...{R}")


def accion_descartar(tareas):
    activas = [t for t in tareas if t["estado"] in ("hoy","cola","bandeja","en_foco")]
    if not activas:
        return

    limpiar()
    seccion("Descartar tarea", GRIS)
    linea()
    print()
    for i, t in enumerate(activas):
        tipo = etiqueta_tipo(t.get("tipo","fondo")) if t["estado"] != "bandeja" else f"{GRIS}○{R}"
        print(f"  {GRIS}{i+1}.{R}  {tipo}  {BLANCO}{nombre_corto(t['name'],44)}{R}  {GRIS}[{t['estado']}]{R}")

    raw = leer_linea(f"\n  {GRIS}Número (o Enter para cancelar):{R} ").strip()
    if not raw:
        return
    try:
        tarea = activas[int(raw)-1]
    except (ValueError, IndexError):
        return

    motivo = leer_linea(f"  {GRIS}Motivo (opcional):{R} ").strip() or "sin motivo"
    for campo in ("foco_inicio", "foco_duracion", "_estado_previo"):
        tarea.pop(campo, None)
    tarea.update({
        "estado":          "descartado",
        "descartado":      date.today().isoformat(),
        "motivo_descarte": motivo,
    })
    guardar_tareas(tareas)
    print(f"\n  {GRIS}✗ Descartada conscientemente.{R}\n")
    input(f"  {GRIS}Enter para continuar...{R}")


def accion_cierre_dia(tareas):
    activas = [t for t in tareas if t["estado"] in ("hoy","en_foco")]
    if not activas:
        print(f"\n  {VERDE}No hay tareas activas sin resolver 🎉{R}\n")
    else:
        limpiar()
        seccion("Cierre de Día", MAGENTA)
        linea()
        print(f"\n  {AMARILLO}{len(activas)} tarea/s activas sin completar — decidí qué hacer:{R}\n")

        for t in activas:
            for campo in ("foco_inicio","foco_duracion","_estado_previo"):
                t.pop(campo, None)
            tipo = etiqueta_tipo(t.get("tipo","fondo"))
            print(f"  {tipo}  {BLANCO}{BOLD}{nombre_corto(t['name'],44)}{R}")
            print(f"  {CYAN}[c]{R} cola (mañana)   {VERDE}[l]{R} lista   {GRIS}[x]{R} descartar\n")
            print(f"  {GRIS}tecla → {R}", end="", flush=True)
            ch = leer_tecla()
            print(ch or "")
            if ch == "l":
                t["estado"]     = "listo"
                t["completado"] = date.today().isoformat()
                print(f"  {VERDE}  → Lista{R}\n")
            elif ch == "x":
                motivo = leer_linea(f"  {GRIS}Motivo:{R} ").strip() or "sin motivo"
                t["estado"]          = "descartado"
                t["descartado"]      = date.today().isoformat()
                t["motivo_descarte"] = motivo
                print(f"  {GRIS}  → Descartada{R}\n")
            else:
                t["estado"] = "cola"
                t.pop("fecha_activacion", None)
                print(f"  {CYAN}  → Cola (aparece mañana){R}\n")

        guardar_tareas(tareas)

    # Archivar plan
    plan = plan_de_hoy()
    if plan:
        plan["archivado"]    = True
        plan["archivado_en"] = datetime.now().isoformat()
        guardar_plan(plan)
        print(f"  {GRIS}Plan de hoy archivado.{R}")

    refrescar_waybar()
    print(f"\n  {BOLD}Día cerrado. Mañana: armar nuevo plan con [p]{R}\n")
    input(f"  {GRIS}Enter para continuar...{R}")


def accion_historial():
    limpiar()
    seccion("Historial de Bloques de Foco", MAGENTA)
    linea()

    hist = cargar_historial()
    if not hist:
        print(f"\n  {GRIS}Sin bloques registrados.{R}\n")
        input(f"  {GRIS}Enter para continuar...{R}")
        return

    by_fecha = {}
    for b in hist:
        by_fecha.setdefault(b.get("fecha","?"), []).append(b)

    total_acum = sum(b.get("minutos_reales",0) for b in hist)
    print(f"\n  {GRIS}Total acumulado: {MAGENTA}{total_acum//60}h {total_acum%60}m{R}  ({len(hist)} bloques)\n")

    for fecha in sorted(by_fecha.keys(), reverse=True)[:10]:
        bloques   = by_fecha[fecha]
        total_dia = sum(b.get("minutos_reales",0) for b in bloques)
        print(f"  {CYAN}{fecha}{R}  {GRIS}{total_dia} min — {len(bloques)} bloque/s{R}")
        for b in bloques:
            icono = {"l":"✓","s":"↩","m":"↻"}.get(b.get("resultado","?"),"?")
            real  = b.get("minutos_reales",0)
            plan_ = b.get("minutos_plan",90)
            print(f"    {GRIS}{icono}{R} {BLANCO}{nombre_corto(b.get('tarea_nombre','?'),38)}{R}  {GRIS}{real}/{plan_} min{R}")
        print()

    input(f"  {GRIS}Enter para continuar...{R}")


def mostrar_desbloqueadas(tarea_id, tareas):
    recien = [
        t for t in tareas
        if tarea_id in t.get("depende_de", [])
        and t["estado"] not in ("listo","descartado")
    ]
    if recien:
        print(f"\n  {CYAN}Desbloqueadas:{R}")
        for u in recien:
            p = calcular_prioridad(u, tareas)
            print(f"    → [{u['id']}] {u['name']} (p={p:.3f})")


def refrescar_waybar():
    """Manda señal a waybar para refrescar el módulo scheduler."""
    try:
        subprocess.run(["pkill", "-SIGRTMIN+8", "waybar"], check=False, capture_output=True)
    except FileNotFoundError:
        pass

# ══════════════════════════════════════════════════════════════════════════════
#  TUI PRINCIPAL — LOOP
# ══════════════════════════════════════════════════════════════════════════════
def cmd_tui():
    while True:
        limpiar()
        tareas = cargar_tareas()
        plan   = plan_de_hoy()
        foco   = foco_activo(tareas)
        bandeja_tareas = [t for t in tareas if t["estado"] == "bandeja"]

        # ── Header ──
        hoy = date.today().strftime("%A %d %b").capitalize()
        print(f"\n  {BOLD}{CYAN}SCHEDULER{R}  {GRIS}{hoy}{R}", end="")
        mostrar_stats_rapidas(tareas)
        linea()

        # ── Secciones contextuales ──
        if foco:
            mostrar_foco(foco)

        if plan:
            mostrar_plan(tareas)

        if bandeja_tareas:
            mostrar_bandeja(tareas)

        cola_tareas = [t for t in tareas if t["estado"] == "cola"]
        if cola_tareas:
            mostrar_cola(tareas)

        mostrar_completadas_recientes(tareas)

        # ── Menú ──
        opciones = construir_menu(tareas, foco, plan, bandeja_tareas)
        mostrar_menu(opciones)

        tecla = leer_tecla()
        if tecla is None:
            continue

        accion_map = {a: aid for _, a, aid in [("","","")] }  # dummy
        accion_map = {op[0]: op[2] for op in opciones}

        accion = accion_map.get(tecla)

        if accion == "salir" or tecla == "q":
            limpiar()
            break
        elif accion == "nueva":
            tareas = cargar_tareas()
            accion_nueva(tareas)
        elif accion == "procesar":
            tareas = cargar_tareas()
            accion_procesar(tareas)
        elif accion == "armar_plan":
            tareas = cargar_tareas()
            accion_armar_plan(tareas)
        elif accion == "cerrar_plan":
            accion_cerrar_plan()
        elif accion == "iniciar_foco":
            tareas = cargar_tareas()
            accion_iniciar_foco(tareas)
        elif accion == "cerrar_foco":
            tareas = cargar_tareas()
            accion_cerrar_foco(tareas)
        elif accion == "marcar_lista":
            tareas = cargar_tareas()
            accion_marcar_lista(tareas)
        elif accion == "descartar":
            tareas = cargar_tareas()
            accion_descartar(tareas)
        elif accion == "cierre_dia":
            tareas = cargar_tareas()
            accion_cierre_dia(tareas)
        elif accion == "historial":
            accion_historial()
        # tecla inválida → solo redibuja

# ══════════════════════════════════════════════════════════════════════════════
#  WAYBAR
# ══════════════════════════════════════════════════════════════════════════════
def cmd_waybar():
    tareas = cargar_tareas()

    # Prioridad 1: bloque de foco activo
    foco = foco_activo(tareas)
    if foco:
        elapsed   = minutos_en_foco(foco)
        planned   = foco.get("foco_duracion", 90)
        remaining = max(0, planned - elapsed)
        pct       = min(100, int(elapsed / planned * 100))
        icono     = ICONOS_CAT.get(foco.get("categoria","personal"), "⚡")
        nombre    = foco["name"][:20] + "…" if len(foco["name"]) > 20 else foco["name"]
        print(json.dumps({
            "text":    f"⚡ {icono} {nombre} · {remaining}m",
            "tooltip": f"EN FOCO: {foco['name']}\n{elapsed}/{planned} min ({pct}%)",
            "class":   "en_foco",
        }))
        return

    # Prioridad 2: tarea principal
    actual = tarea_principal(tareas)
    if not actual:
        bandeja_n = sum(1 for t in tareas if t["estado"] == "bandeja")
        tooltip   = f"⚠ {bandeja_n} en bandeja sin procesar" if bandeja_n else "No hay tareas pendientes"
        print(json.dumps({
            "text":    "󰄭 Sin tareas" if not bandeja_n else f"󰄭 Bandeja ({bandeja_n})",
            "tooltip": tooltip,
            "class":   "vacio" if not bandeja_n else "bandeja",
        }))
        return

    dias  = dias_hasta(actual.get("limite"))
    icono = ICONOS_CAT.get(actual.get("categoria","personal"), "󰋙")
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

    # Tooltip
    plan = plan_de_hoy()
    header = f"<b>Plan de hoy — {date.today().isoformat()}</b>" if plan else "<b>Top Cola:</b>"
    lineas = [header]
    for i, t in enumerate(cola_ordenada(tareas)[:5]):
        p     = calcular_prioridad(t, tareas)
        d     = dias_hasta(t.get("limite"))
        d_s   = f"{int(d)}d" if t.get("limite") else "∞"
        bloq  = " 🔒" if esta_bloqueada(t, tareas) else ""
        marca = "▶ " if t["id"] == actual["id"] else f"{i+1}. "
        tipo  = ICONOS_TIPO.get(t.get("tipo","fondo"),"")
        lineas.append(f"{marca}{tipo} {t['name']} [{d_s}] (p={p:.2f}){bloq}")

    bandeja_n = sum(1 for t in tareas if t["estado"] == "bandeja")
    pendientes = sum(1 for t in tareas if t["estado"] in ("cola","hoy","en_foco"))
    if bandeja_n:
        lineas.append(f"\n<i>⚠ {bandeja_n} en bandeja sin procesar</i>")
    lineas.append(f"<i>{pendientes} en cola</i>")

    print(json.dumps({
        "text":    f"{icono} {nombre} · {d_str}",
        "tooltip": "\n".join(lineas),
        "class":   clase,
    }))

# ══════════════════════════════════════════════════════════════════════════════
#  MIGRACIÓN — tareas con estados viejos
# ══════════════════════════════════════════════════════════════════════════════
def cmd_migrar():
    """Convierte tareas con estados del esquema anterior al nuevo."""
    tareas = cargar_tareas()
    mapa_estados = {
        "pending":     "cola",
        "active":      "hoy",
        "in_progress": "en_foco",
        "done":        "listo",
        "dropped":     "descartado",
        "inbox":       "bandeja",
        "backlog":     "cola",
    }
    mapa_campos = {
        "category":   "categoria",
        "task_type":  "tipo",
        "deadline":   "limite",
        "depends_on": "depende_de",
        "created":    "creado",
        "completed":  "completado",
        "notes":      "notas",
    }
    cambiadas = 0
    for t in tareas:
        # Estados
        if t.get("estado") is None and t.get("status"):
            t["estado"] = mapa_estados.get(t.pop("status"), "cola")
            cambiadas += 1
        elif t.get("status"):
            t["estado"] = mapa_estados.get(t.pop("status"), t.get("estado","cola"))

        # Campos renombrados
        for viejo, nuevo in mapa_campos.items():
            if viejo in t and nuevo not in t:
                t[nuevo] = t.pop(viejo)

        # task_type viejo → tipo
        if "task_type" in t:
            t["tipo"] = t.pop("task_type")

    guardar_tareas(tareas)
    print(f"  Migración completa — {len(tareas)} tareas actualizadas.")

# ══════════════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════
def main():
    args = sys.argv[1:]

    if not args or args[0] == "waybar":
        cmd_waybar()
    elif args[0] in ("tui", "list"):
        cmd_tui()
    elif args[0] == "migrar":
        cmd_migrar()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()

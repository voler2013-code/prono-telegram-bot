#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script: pronostico_termico_open_meteo.py

Descripción:
  - Interpreta una consulta flexible tipo: "hoy; 15hs; cuchi" o "01-12-2025; 14hs; -31,55; -64,33; -9; 25"
  - Llama a múltiples modelos de Open-Meteo (icon, gfs, meteo-france, ecmwf, ukmo, gem, cma) para obtener
    temperatura y humedad por alturas (2 m y niveles ~1000–500 hPa) en una fecha y hora dadas.
  - Calcula promedios y desviaciones estándar por altura.
  - Calcula punto de rocío con la fórmula: Td = T + 35 * log10(RH/100).
  - Calcula "velocTermica" por altura > elevación usando:
        v = 5.6 * sqrt( ( (1.1^|RocioTermica - Rocio|) - 1 ) / (1.1^|Temp - Rocio|) )
    *Para la primera altura > elevación*: RocioTermica = Td_2m (o personalizado).
    *Para el resto de alturas*: RocioTermica = Td_2m (o personalizado) - [(altura_actual - elevación) * 0.0018]
  - Presenta salida formateada desde la primera altura superior a la elevación hacia arriba
    y agrega la fila de la elevación con Td_2m; T_2m y 0.
  - Incluye un sondeo gráfico con barras oblicuas según pendientes.

Requisitos:
  pip install requests numpy

Uso en Windows (ejemplos):
  python pronostico_termico_open_meteo.py "hoy; 15hs; cuchi"
  python pronostico_termico_open_meteo.py "mañ; merlo; 10hs; -5,5; 8,1"
  python pronostico_termico_open_meteo.py "01-12-2025; 14hs; -31,55; -64,33; -9; 25"

Notas:
  - Timezone de las consultas: America/Sao_Paulo (según requerimiento).
  - Si falta fecha, hora o lugar/coordenadas, el script lo indica.
  - Acepta decimales con coma o punto.
"""

import sys
import re
import math
import json
import decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple

import requests
import numpy as np

# ----------------------------- Configuración ----------------------------- #
TZ = "America/Sao_Paulo"

# Mapa de lugares predefinidos
LUGARES: Dict[str, Tuple[float, float]] = {
    "merlo": (-32.34, -64.98),
    "trasla": (-31.72, -65.00),
    "ped": (-31.76, -64.65),
    "alpina": (-32.02, -64.81),
    "sj": (-31.32, -64.34),
    "cuchi": (-30.99, -64.71),
    "rioja": (-29.40, -66.82),
    "tuc": (-26.77, -65.28),
}

# Alturas (m) por variable en el JSON (ahora incluye 600 hPa y 500 hPa)
LEVELS = [
    ("2m", 2, "temperature_2m", "relative_humidity_2m"),
    ("1000hPa", 110, "temperature_1000hPa", "relative_humidity_1000hPa"),
    ("975hPa", 320, "temperature_975hPa", "relative_humidity_975hPa"),
    ("950hPa", 500, "temperature_950hPa", "relative_humidity_950hPa"),
    ("925hPa", 800, "temperature_925hPa", "relative_humidity_925hPa"),
    ("900hPa", 1000, "temperature_900hPa", "relative_humidity_900hPa"),
    ("850hPa", 1500, "temperature_850hPa", "relative_humidity_850hPa"),
    ("800hPa", 1900, "temperature_800hPa", "relative_humidity_800hPa"),
    ("750hPa", 2500, "temperature_750hPa", "relative_humidity_750hPa"),
    ("700hPa", 3000, "temperature_700hPa", "relative_humidity_700hPa"),
    ("600hPa", 4200, "temperature_600hPa", "relative_humidity_600hPa"),   # NUEVO
    ("500hPa", 5600, "temperature_500hPa", "relative_humidity_500hPa"),   # NUEVO
]

# Modelos y sus conjuntos de variables disponibles.
# NOTA: ecmwf_ifs solo maneja un subconjunto reducido; los demás modelos tienen
# disponibilidad completa incluyendo 600 y 500 hPa.
MODELOS = {
    "icon_seamless": {
        "vars": [
            "temperature_2m",
            "relative_humidity_2m",
            "temperature_1000hPa","temperature_975hPa","temperature_950hPa","temperature_925hPa",
            "temperature_900hPa","temperature_850hPa","temperature_800hPa","temperature_700hPa",
            "temperature_600hPa","temperature_500hPa",                                                # NUEVO
            "relative_humidity_1000hPa","relative_humidity_975hPa","relative_humidity_950hPa","relative_humidity_925hPa",
            "relative_humidity_900hPa","relative_humidity_850hPa","relative_humidity_800hPa","relative_humidity_700hPa",
            "relative_humidity_600hPa","relative_humidity_500hPa",                                    # NUEVO
        ]
    },
    "gfs_seamless": {
        "vars": [
            "temperature_2m","relative_humidity_2m",
            "temperature_700hPa","temperature_750hPa","temperature_800hPa","temperature_850hPa",
            "temperature_900hPa","temperature_925hPa","temperature_950hPa","temperature_975hPa","temperature_1000hPa",
            "temperature_600hPa","temperature_500hPa",                                                # NUEVO
            "relative_humidity_700hPa","relative_humidity_750hPa","relative_humidity_800hPa","relative_humidity_850hPa",
            "relative_humidity_900hPa","relative_humidity_925hPa","relative_humidity_950hPa","relative_humidity_975hPa","relative_humidity_1000hPa",
            "relative_humidity_600hPa","relative_humidity_500hPa",                                    # NUEVO
        ]
    },
    "meteofrance_seamless": {
        "vars": [
            "temperature_2m","relative_humidity_2m",
            "temperature_1000hPa","temperature_950hPa","temperature_925hPa","temperature_900hPa",
            "temperature_850hPa","temperature_800hPa","temperature_750hPa","temperature_700hPa",
            "temperature_600hPa","temperature_500hPa",                                                # NUEVO
            "relative_humidity_1000hPa","relative_humidity_950hPa","relative_humidity_925hPa","relative_humidity_900hPa",
            "relative_humidity_850hPa","relative_humidity_800hPa","relative_humidity_750hPa","relative_humidity_700hPa",
            "relative_humidity_600hPa","relative_humidity_500hPa",                                    # NUEVO
        ]
    },
    "ecmwf_ifs": {
        "vars": [
            "temperature_2m","relative_humidity_2m",
            "temperature_1000hPa","temperature_925hPa","temperature_850hPa","temperature_700hPa",
            "relative_humidity_1000hPa","relative_humidity_925hPa","relative_humidity_850hPa","relative_humidity_700hPa",
            # ecmwf no dispone de más niveles en la API gratuita
        ]
    },
    "ukmo_seamless": {
        "vars": [
            "temperature_2m","relative_humidity_2m",
            "temperature_1000hPa","temperature_975hPa","temperature_950hPa","temperature_925hPa",
            "temperature_900hPa","temperature_850hPa","temperature_800hPa","temperature_750hPa","temperature_700hPa",
            "temperature_600hPa","temperature_500hPa",                                                # NUEVO
            "relative_humidity_1000hPa","relative_humidity_975hPa","relative_humidity_950hPa","relative_humidity_925hPa",
            "relative_humidity_900hPa","relative_humidity_850hPa","relative_humidity_800hPa","relative_humidity_750hPa","relative_humidity_700hPa",
            "relative_humidity_600hPa","relative_humidity_500hPa",                                    # NUEVO
        ]
    },
    "gem_seamless": {
        "vars": [
            "temperature_2m","relative_humidity_2m",
            "temperature_1000hPa","temperature_950hPa","temperature_925hPa","temperature_900hPa",
            "temperature_850hPa","temperature_800hPa","temperature_750hPa","temperature_700hPa",
            "temperature_600hPa","temperature_500hPa",                                                # NUEVO
            "relative_humidity_700hPa","relative_humidity_750hPa","relative_humidity_800hPa","relative_humidity_850hPa",
            "relative_humidity_900hPa","relative_humidity_925hPa","relative_humidity_950hPa","relative_humidity_1000hPa",
            "relative_humidity_600hPa","relative_humidity_500hPa",                                    # NUEVO
        ]
    },
    "cma_grapes_global": {
        "vars": [
            "temperature_2m","relative_humidity_2m",
            "temperature_1000hPa","temperature_975hPa","temperature_950hPa","temperature_925hPa",
            "temperature_900hPa","temperature_850hPa","temperature_800hPa","temperature_750hPa","temperature_700hPa",
            "temperature_600hPa","temperature_500hPa",                                                # NUEVO
            "relative_humidity_1000hPa","relative_humidity_975hPa","relative_humidity_950hPa","relative_humidity_925hPa",
            "relative_humidity_900hPa","relative_humidity_850hPa","relative_humidity_800hPa","relative_humidity_750hPa","relative_humidity_700hPa",
            "relative_humidity_600hPa","relative_humidity_500hPa",                                    # NUEVO
        ]
    },
}

# ----------------------------- Utilidades ----------------------------- #

def parse_float(token: str) -> Optional[float]:
    token = token.strip()
    # Reemplazar coma decimal por punto, y quitar espacios
    token = token.replace(" ", "").replace(",", ".")
    # Permitir signo y decimales
    m = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", token)
    if not m:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def detectar_fecha(token: str) -> Optional[date]:
    t = token.strip().lower()
    hoy = datetime.now().date()
    if t in {"hoy"}:
        return hoy
    if t in {"ayer"}:
        return hoy - timedelta(days=1)
    if t in {"mañ", "mañana", "man", "mana", "manana"}:
        return hoy + timedelta(days=1)
    # Formato DD-MM-YYYY
    t2 = t.replace(" ", "")
    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", t2):
        try:
            d, m, y = map(int, t2.split("-"))
            return date(y, m, d)
        except Exception:
            return None
    return None


def detectar_hora(token: str) -> Optional[int]:
    t = token.strip().lower().replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})hs", t)
    if m:
        hh = int(m.group(1))
        if 0 <= hh <= 23:
            return hh
    return None


def detectar_lugar(token: str) -> Optional[Tuple[str, Tuple[float, float]]]:
    t = token.strip().lower()
    if t in LUGARES:
        return t, LUGARES[t]
    return None


def armar_fecha_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def construir_url(lat: float, lon: float, fecha: date, modelo: str, vars_list: List[str]) -> str:
    hourly = ",".join(vars_list)
    return (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&hourly={hourly}&models={modelo}"
        f"&timezone={requests.utils.quote(TZ)}&start_date={armar_fecha_str(fecha)}&end_date={armar_fecha_str(fecha)}&format=json"
    )


def log10(x: float) -> float:
    return math.log10(x)


def dewpoint_from_T_RH(T: float, RH: float) -> Optional[float]:
    if RH is None or T is None:
        return None
    if RH <= 0:
        return None
    try:
        return T + 35.0 * log10(RH / 100.0)
    except ValueError:
        return None


def fetch_model_data(lat: float, lon: float, fecha: date, modelo: str, vars_list: List[str]) -> Optional[dict]:
    url = construir_url(lat, lon, fecha, modelo, vars_list)
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

# ---------------------- SONDEO GRÁFICO ----------------------
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

def D(x) -> Decimal:
    return Decimal(str(x))

def round_half_up(x) -> int:
    return int(D(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def pendiente(
    h1: int,
    h2: int,
    v1: Decimal,
    v2: Decimal,
    eps: Decimal = Decimal("0.001")
) -> Decimal:
    dx = v2 - v1
    if dx == 0:
        dx = eps
    return Decimal(h2 - h1) / dx

def char_humedad(p: Decimal) -> str:
    if p > 1 and p < 460:
        return "/"
    if p >= 460 and p < 10000:
        return "|"
    return "\\"

def char_temperatura(p: Decimal) -> str:
    if p < -1 and p > -400:
        return "\\"
    if p <= -400 and p > -10000:
        return "|"
    return "/"

def generar_sondeo(
    stats: Dict[int, Dict[str, float]],
    elevacion: int,
    t_2m: Optional[float] = None,
    td_2m: Optional[float] = None,
    ancho: int = 40
) -> List[str]:
    if not stats:
        return []

    base = int(round(elevacion))

    # Alturas por encima de la base
    alturas_superiores = sorted(h for h in stats if h > base)
    if not alturas_superiores:
        return []

    # Base con T_2m / Td_2m
    if t_2m is None or td_2m is None:
        if 2 in stats:
            if t_2m is None:
                t_2m = stats[2]["T_mean"]
            if td_2m is None:
                td_2m = stats[2]["Td_mean"]
        elif base in stats:
            if t_2m is None:
                t_2m = stats[base]["T_mean"]
            if td_2m is None:
                td_2m = stats[base]["Td_mean"]
        else:
            return []

    alturas = [base] + alturas_superiores

    T = {h: D(stats[h]["T_mean"]) for h in alturas_superiores}
    Td = {h: D(stats[h]["Td_mean"]) for h in alturas_superiores}
    T[base] = D(t_2m)
    Td[base] = D(td_2m)

    # Normalización exacta
    T_norm = {h: T[h] + D("0.5") * D(h) / D("100") for h in alturas}
    Td_norm = {h: Td[h] + D("0.5") * D(h) / D("100") for h in alturas}

    # Offset dewpoint
    offset = round_half_up(abs(min(Td_norm.values())))

    # Paso 4
    Td_shift = {h: round_half_up(Td_norm[h] + D(offset)) for h in alturas}

    # Paso 7
    diff = {h: round_half_up(abs(T_norm[h] - Td_norm[h])) for h in alturas}

    # Filas visibles: la más alta solo sirve para calcular pendiente
    visibles = sorted(alturas, reverse=True)[1:]

    # Para buscar vecinos en ascendente
    idx = {h: i for i, h in enumerate(alturas)}

    def barra_h_por_fila(h: int) -> str:
        if h == base:
            h1, h2 = alturas[0], alturas[1]
        else:
            i = idx[h]
            h1, h2 = alturas[i - 1], alturas[i]
        p = pendiente(h1, h2, Td_norm[h1], Td_norm[h2])
        return char_humedad(p)

    def barra_t_por_fila(h: int) -> str:
        if h == base:
            h1, h2 = alturas[0], alturas[1]
        else:
            i = idx[h]
            h1, h2 = alturas[i - 1], alturas[i]
        p = pendiente(h1, h2, T_norm[h1], T_norm[h2])
        return char_temperatura(p)

    # Ancho del prefijo "0600m "
    prefijo_len = 6
    ancho_cuerpo = max(1, ancho - prefijo_len)

    # Cálculo del recorte global SOLO desde la izquierda
    max_cuerpo = max(Td_shift[h] + 1 + diff[h] + 1 for h in visibles)
    recorte_global = max(0, max_cuerpo - ancho_cuerpo)

    resultado = []
    for h in visibles:
        izq = max(0, Td_shift[h] - recorte_global)
        der = diff[h]

        bh = barra_h_por_fila(h)
        bt = barra_t_por_fila(h)

        cuerpo_minimo_derecha = 1 + der + 1  # barra_h + puntos der + barra_t
        max_izq = max(0, ancho_cuerpo - cuerpo_minimo_derecha)
        izq = min(izq, max_izq)

        cuerpo = "." * izq + bh + "." * der + bt

        if not cuerpo.endswith(("/", "|", "\\")):
            cuerpo = cuerpo + bt

        resultado.append(f"{h:04d}m {cuerpo}")

    return resultado

# ----------------------- Núcleo de procesamiento ----------------------- #

def find_hour_index(times: List[str], target_hour: int) -> Optional[int]:
    for i, ts in enumerate(times):
        try:
            hh = int(ts[11:13])
            if hh == target_hour:
                return i
        except Exception:
            continue
    return None


def procesar_consulta(query: str) -> None:
    tokens = [t.strip() for t in query.split(';') if t.strip() != ""]

    fecha: Optional[date] = None
    hora: Optional[int] = None
    lugar_nombre: Optional[str] = None
    coords: Optional[Tuple[float, float]] = None
    td_custom: Optional[float] = None
    t_custom: Optional[float] = None

    numeric_positions = []

    for idx, tok in enumerate(tokens):
        if fecha is None:
            f = detectar_fecha(tok)
            if f is not None:
                fecha = f
                continue
        if hora is None:
            h = detectar_hora(tok)
            if h is not None:
                hora = h
                continue
        if lugar_nombre is None and coords is None:
            lug = detectar_lugar(tok)
            if lug is not None:
                lugar_nombre, coords = lug[0], lug[1]
                continue
        val = parse_float(tok)
        if val is not None:
            numeric_positions.append((idx, val))

    used_indices = set()

    def try_assign_pair(i1, v1, i2, v2):
        nonlocal coords, td_custom, t_custom
        if coords is None and (-90.0 <= v1 <= 90.0) and (-180.0 <= v2 <= 180.0):
            coords = (v1, v2)
            return 'coords'
        if td_custom is None and t_custom is None:
            td_custom, t_custom = v1, v2
            return 'tdt'
        return None

    numeric_positions.sort(key=lambda x: x[0])
    i = 0
    while i < len(numeric_positions) - 1:
        idx1, v1 = numeric_positions[i]
        idx2, v2 = numeric_positions[i + 1]
        if idx2 == idx1 + 1 and idx1 not in used_indices and idx2 not in used_indices:
            assigned = try_assign_pair(idx1, v1, idx2, v2)
            if assigned:
                used_indices.update({idx1, idx2})
                i += 2
                continue
        i += 1

    missing = []
    if fecha is None:
        missing.append("fecha")
    if hora is None:
        missing.append("horario (formato 24hs: ej. 15hs)")
    if coords is None:
        missing.append("lugar o coordenadas (lat; lon)")

    if missing:
        print("Falta ingresar: " + ", ".join(missing))
        return

    lat, lon = coords

    # ---------------- Llamadas a la API por modelo ----------------
    modelos_data = {}
    elevation_values = []

    for modelo, meta in MODELOS.items():
        data = fetch_model_data(lat, lon, fecha, modelo, meta["vars"])
        if not data:
            continue
        modelos_data[modelo] = data
        if "elevation" in data:
            elevation_values.append(data["elevation"])

    if not modelos_data:
        print("No se pudo obtener datos de Open-Meteo para esa consulta.")
        return

    elevation = float(np.nanmedian(elevation_values)) if elevation_values else float('nan')

    # ---------------- Extraer datos por hora deseada ----------------
    hour_index_by_model = {}
    for modelo, data in modelos_data.items():
        times = data.get("hourly", {}).get("time", [])
        idx = find_hour_index(times, hora)
        if idx is not None:
            hour_index_by_model[modelo] = idx

    if not hour_index_by_model:
        print("No se encontró la hora solicitada en los datos devueltos.")
        return

    # Estructura por altura
    por_altura: Dict[int, Dict[str, List[Tuple[str, float]]]] = {}
    for _, altura_m, var_T, var_RH in LEVELS:
        por_altura[altura_m] = {"T": [], "RH": [], "Td": []}

    for modelo, data in modelos_data.items():
        idx = hour_index_by_model.get(modelo)
        if idx is None:
            continue
        hourly = data.get("hourly", {})
        for _, altura_m, var_T, var_RH in LEVELS:
            T_list = hourly.get(var_T)
            RH_list = hourly.get(var_RH)
            T = None
            RH = None
            if isinstance(T_list, list) and idx < len(T_list):
                T = T_list[idx]
            if isinstance(RH_list, list) and idx < len(RH_list):
                RH = RH_list[idx]
            if T is not None:
                por_altura[altura_m]["T"].append((modelo, float(T)))
            if RH is not None:
                por_altura[altura_m]["RH"].append((modelo, float(RH)))
            if T is not None and RH is not None and RH > 0:
                Td = dewpoint_from_T_RH(float(T), float(RH))
                if Td is not None:
                    por_altura[altura_m]["Td"].append((modelo, float(Td)))

    if td_custom is not None:
        pass  # se aplicará en velocidad térmica
    if t_custom is not None:
        por_altura[2]["T"] = [("custom", float(t_custom))]

    # Promedios y std por altura
    stats_por_altura = {}
    for altura_m, dct in por_altura.items():
        T_vals = [v for _, v in dct["T"]]
        Td_vals = [v for _, v in dct["Td"]]
        T_mean = float(np.nanmedian(T_vals)) if T_vals else float('nan')
        T_std = float(np.nanstd(T_vals, ddof=0)) if T_vals else float('nan')
        Td_mean = float(np.nanmedian(Td_vals)) if Td_vals else float('nan')
        Td_std = float(np.nanstd(Td_vals, ddof=0)) if Td_vals else float('nan')
        stats_por_altura[altura_m] = {
            "T_mean": T_mean,
            "T_std": T_std,
            "Td_mean": Td_mean,
            "Td_std": Td_std,
        }

    # ---------------- Cálculo de velocTermica por modelo ----------------
    def veloc_termica(RocioTermica: float, Rocio: float, Temp: float) -> Optional[float]:
        try:
            num = (1.1 ** abs(RocioTermica - Rocio)) - 1.0
            den = (1.1 ** abs(Temp - Rocio))
            if den <= 0:
                return None
            v = 5.6 * math.sqrt(max(0.0, num / den))
            return v
        except Exception:
            return None

    alturas_ordenadas = [h for h in sorted(por_altura.keys()) if h > elevation]
    if not alturas_ordenadas:
        alturas_ordenadas = []

    v_stats_por_altura = {}
    td2m_por_modelo = {}
    for modelo, val in por_altura[2]["Td"]:
        td2m_por_modelo[modelo] = val

    if td_custom is not None:
        for modelo in modelos_data.keys():
            td2m_por_modelo[modelo] = float(td_custom)

    if not td2m_por_modelo and not math.isnan(stats_por_altura[2]["Td_mean"]):
        mean_td2m = stats_por_altura[2]["Td_mean"]
        for modelo in modelos_data.keys():
            td2m_por_modelo[modelo] = mean_td2m

    for idx_alt, altura_m in enumerate(alturas_ordenadas):
        v_vals = []
        T_por_modelo = {m: v for m, v in por_altura[altura_m]["T"]}
        Td_por_modelo = {m: v for m, v in por_altura[altura_m]["Td"]}

        for modelo in modelos_data.keys():
            Td2m = td2m_por_modelo.get(modelo)
            Td_h = Td_por_modelo.get(modelo)
            T_h = T_por_modelo.get(modelo)

            if Td_h is None and not math.isnan(stats_por_altura[altura_m]["Td_mean"]):
                Td_h = stats_por_altura[altura_m]["Td_mean"]
            if T_h is None and not math.isnan(stats_por_altura[altura_m]["T_mean"]):
                T_h = stats_por_altura[altura_m]["T_mean"]

            if Td2m is None or Td_h is None or T_h is None:
                continue

            if idx_alt == 0:
                RocioTermica = Td2m
            else:
                RocioTermica = Td2m - ((altura_m - elevation) * 0.0018)

            v = veloc_termica(RocioTermica, Td_h, T_h)
            if v is not None:
                v_vals.append(v)

        if v_vals:
            v_mean = float(np.nanmedian(v_vals))
            v_std = float(np.nanstd(v_vals, ddof=0))
        else:
            v_mean = float('nan')
            v_std = float('nan')
        v_stats_por_altura[altura_m] = {"v_mean": v_mean, "v_std": v_std}

    # ---------------------- Salida formateada ---------------------- #
    lugar_str = lugar_nombre if lugar_nombre else f"{lat:.2f},{lon:.2f}"
    cabecera = "m" + " " * 7 + "R;T" + " " * 7 + "m/s"

    print("Prono térmico para:")
    hoy = datetime.now().date()
    if fecha == hoy:
        fecha_etq = "hoy"
    elif fecha == hoy - timedelta(days=1):
        fecha_etq = "ayer"
    elif fecha == hoy + timedelta(days=1):
        fecha_etq = "mañ"
    else:
        fecha_etq = fecha.strftime("%d-%m-%Y")

    print(f"{fecha_etq}; {hora:02d}hs; {lugar_str}; {int(round(elevation))}m")
    print()
    print(cabecera)

    alturas_out = sorted(alturas_ordenadas, reverse=True)

    def fmt_row(altura: int, td: float, t: float, v: Optional[float], vs: Optional[float]) -> str:
        td_str = "" if math.isnan(td) else f"{int(round(td))}"
        t_str = "" if math.isnan(t) else f"{int(round(t))}"
        if v is None or math.isnan(v):
            v_str = ""
        else:
            v_str = f"{v:.1f}"
        if vs is None or math.isnan(vs) or (v is None or math.isnan(v)):
            vs_str = ""
        else:
            vs_str = f"±{vs:.1f}"
        return f"{altura:>4}   {td_str};{t_str:}   {v_str}{vs_str}"

    for h in alturas_out:
        td_mean = stats_por_altura.get(h, {}).get("Td_mean", float('nan'))
        t_mean = stats_por_altura.get(h, {}).get("T_mean", float('nan'))
        v_mean = v_stats_por_altura.get(h, {}).get("v_mean", float('nan'))
        v_std = v_stats_por_altura.get(h, {}).get("v_std", float('nan'))
        print(fmt_row(h, td_mean, t_mean, v_mean, v_std))

    td2m_out = td_custom if td_custom is not None else stats_por_altura[2]["Td_mean"]
    t2m_out = t_custom if t_custom is not None else stats_por_altura[2]["T_mean"]
    print(fmt_row(int(round(elevation)), td2m_out, t2m_out, 0.0, 0.0))

    # Sondeo gráfico
    print()
    sondeo = generar_sondeo(stats_por_altura, elevation)
    if sondeo:
        print("Sondeo promedio:")
        for linea in sondeo:
            print(linea)


# ------------------------------- Main -------------------------------- #
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        consulta = " ".join(sys.argv[1:])
    else:
        consulta = input("Ingrese consulta (ej: 'hoy; 15hs; cuchi'): ")
    try:
        procesar_consulta(consulta)
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
    except Exception as e:
        print("Error inesperado:", str(e))
        # import traceback; traceback.print_exc()

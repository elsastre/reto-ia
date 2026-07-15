"""
Pipeline real - Reto 1 CREA (bases nuevas, joinables por ID_persona dentro del mismo tipo)
==========================================================================================
Hace, de forma INDEPENDIENTE por tipo (estudiantes / docentes):
  1. Limpieza (esquema nuevo de 17 cols)
  2. IVSMEDIA y CONTEXTO -> quintil numerico 1..5
  3. Docentes: colapso a nivel PERSONA-anio (dias son per-persona, NO sumar)
  4. Panel longitudinal 2025<->2026 por ID_persona (validate one_to_one)

REGLAS (verificadas con los datos):
  - NO se cruza estudiante <-> docente por ID_CENTRO (la anonimizacion lo rompio).
    Por eso ID_CENTRO se renombra por tipo, para que nadie lo joinee por error.
  - Dias del docente = per-persona (todas sus filas iguales) -> se toma 'first', no 'sum'.
  - CONTEXTO = vulnerabilidad primaria ; IVSMEDIA = vulnerabilidad media. Disjuntas por nivel.

Salidas (carpeta processed/):
  <tipo>_<anio>_clean.parquet          limpio, grano original (asignacion en docentes)
  docentes_<anio>_persona.parquet      docentes colapsado a 1 fila por persona
  panel_estudiantes.parquet            longitudinal por alumno
  panel_docentes.parquet               longitudinal por docente (persona)
"""

import re
from pathlib import Path
import pandas as pd
import numpy as np

# ======================================================================
# CONFIG
# ======================================================================
SALIDA = Path(r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026\processed")

BASES = [
    {"ruta": r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026\datosUCU2025_estu.xlsx", "tipo": "estudiantes", "anio": 2025},
    {"ruta": r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026\datosUCU2026_estu.xlsx", "tipo": "estudiantes", "anio": 2026},
    {"ruta": r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026\datosUCU2025_doc.xlsx",  "tipo": "docentes",    "anio": 2025},
    {"ruta": r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026\datosUCU2026_doc.xlsx",  "tipo": "docentes",    "anio": 2026},
]

DIAS = ["Dias4", "Dias5", "Dias6"]
DIAS_MAX = {"Dias4": 30, "Dias5": 31, "Dias6": 30}  # abril, mayo, junio


# ======================================================================
# HELPERS
# ======================================================================
def leer(ruta: Path) -> pd.DataFrame:
    """Lee xlsx y cachea a parquet: la 2a corrida es casi instantanea."""
    ruta = Path(ruta)
    cache = ruta.with_suffix(".parquet")
    if cache.exists():
        return pd.read_parquet(cache)
    df = pd.read_excel(ruta)
    try:
        df.to_parquet(cache)   # requiere pyarrow (pip install pyarrow)
    except Exception as e:
        print(f"  (aviso: no pude cachear parquet: {e})")
    return df


def a_quintil(serie: pd.Series) -> pd.Series:
    """Lleva IVSMEDIA/CONTEXTO a entero 1..5. Sirve para:
       - float 2025 (1.0..5.0)
       - texto 2026 'QUINTIL 3'
       - texto 'Quintil Urbano 5'
       Lo no interpretable (ej 'Sin clasificar') queda NaN."""
    def extraer(v):
        if pd.isna(v):
            return np.nan
        m = re.search(r"([1-5])", str(v))
        return int(m.group(1)) if m else np.nan
    return serie.map(extraer).astype("Int64")


def zona_contexto(serie: pd.Series) -> pd.Series:
    """De 'Quintil Urbano 5' saca 'Urbano' / 'Rural'; resto NaN."""
    def z(v):
        s = str(v)
        if "Urbano" in s:
            return "Urbano"
        if "Rural" in s:
            return "Rural"
        return np.nan
    return serie.map(z)


# ======================================================================
# 1) LIMPIEZA (por base)
# ======================================================================
def limpiar(base: dict) -> pd.DataFrame:
    print(f"\n=== {Path(base['ruta']).name} ({base['tipo']} {base['anio']}) ===")
    df = leer(base["ruta"])
    df.columns = df.columns.astype(str).str.strip()
    n = len(df)

    # dias a numerico + chequeo de rango (FLAG, no recorta)
    for col in DIAS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        tope = DIAS_MAX[col]
        fuera = int((df[col] < 0).sum() + (df[col] > tope).sum())
        if fuera:
            print(f"  [RANGO] {col}: {fuera} fuera de [0,{tope}] (FLAG)")

    # texto: trim
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype("string").str.strip()

    # vulnerabilidad -> quintil numerico (dos columnas disjuntas por nivel)
    df["ivsmedia_q"] = a_quintil(df["IVSMEDIA"])       # media (UTU/secundaria)
    df["contexto_q"] = a_quintil(df["CONTEXTO"])       # primaria
    df["contexto_zona"] = zona_contexto(df["CONTEXTO"])
    # SUPUESTO A VERIFICAR: contexto (primaria) e ivsmedia (media) no se pisan.
    # Si es asi, esta union da un unico eje de vulnerabilidad. Confirmar antes de usar.
    df["vuln_q"] = df["contexto_q"].fillna(df["ivsmedia_q"])

    # metrica de uso
    df["dias_totales"] = df[DIAS].sum(axis=1, min_count=1)
    df["accedio"] = (df["dias_totales"] > 0).astype("Int64")

    # BLOQUEO del cruce prohibido: ID_CENTRO no es comparable entre tipos
    df = df.rename(columns={"ID_CENTRO": f"ID_CENTRO_{base['tipo']}"})

    df["tipo"] = base["tipo"]
    df["anio"] = base["anio"]
    print(f"  filas={n} | accedio=1: {int(df['accedio'].sum())} "
          f"({round(100*df['accedio'].mean(),1)}%) | vuln_q nulos: {int(df['vuln_q'].isna().sum())}")
    return df


# ======================================================================
# 2) COLAPSO DOCENTES -> nivel PERSONA-anio  (dias per-persona: 'first', NO 'sum')
# ======================================================================
def colapsar_docentes(df: pd.DataFrame) -> pd.DataFrame:
    cen = f"ID_CENTRO_docentes"
    agg = {
        "Dias4": "first", "Dias5": "first", "Dias6": "first",
        "dias_totales": "first", "accedio": "first",
        "Sexo": "first", "anio": "first",
        cen: "nunique", "MATERIA": "nunique", "dept_nombre": "nunique",
        "vuln_q": "first",
    }
    g = (df.groupby("ID_persona", as_index=False)
           .agg(agg)
           .rename(columns={cen: "n_centros", "MATERIA": "n_materias",
                            "dept_nombre": "n_deptos"}))
    g["n_asignaciones"] = df.groupby("ID_persona").size().values
    print(f"  docentes {int(df['anio'].iloc[0])}: {len(df)} filas-asignacion "
          f"-> {len(g)} personas")
    return g


# ======================================================================
# 3) PANEL LONGITUDINAL 2025<->2026 (validate one_to_one)
# ======================================================================
def panel(d25: pd.DataFrame, d26: pd.DataFrame, cols: list[str], etiqueta: str) -> pd.DataFrame:
    a = d25[["ID_persona"] + cols].add_suffix("_25").rename(columns={"ID_persona_25": "ID_persona"})
    b = d26[["ID_persona"] + cols].add_suffix("_26").rename(columns={"ID_persona_26": "ID_persona"})
    m = a.merge(b, on="ID_persona", how="outer", validate="one_to_one", indicator=True)
    m["estado"] = m["_merge"].map({"left_only": "solo_2025", "right_only": "solo_2026", "both": "ambos"})
    # delta de acceso solo tiene sentido en los que estan en ambos anios
    if "dias_totales_25" in m and "dias_totales_26" in m:
        m["delta_dias"] = m["dias_totales_26"] - m["dias_totales_25"]
    print(f"\n[PANEL {etiqueta}] ambos={int((m.estado=='ambos').sum())} "
          f"solo_2025={int((m.estado=='solo_2025').sum())} "
          f"solo_2026={int((m.estado=='solo_2026').sum())}")
    return m.drop(columns="_merge")


# ======================================================================
# MAIN
# ======================================================================
def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    limpio = {}
    for base in BASES:
        df = limpiar(base)
        df.to_parquet(SALIDA / f"{base['tipo']}_{base['anio']}_clean.parquet")
        limpio[(base["tipo"], base["anio"])] = df

    # --- Estudiantes: ya es 1 fila por persona ---
    est_cols = ["dias_totales", "accedio", "Sexo", "vuln_q", "Rubro", "dept_nombre", "ZONA"]
    panel_est = panel(limpio[("estudiantes", 2025)], limpio[("estudiantes", 2026)],
                      est_cols, "estudiantes")
    panel_est.to_parquet(SALIDA / "panel_estudiantes.parquet")

    # --- Docentes: colapsar a persona y despues panel ---
    doc25 = colapsar_docentes(limpio[("docentes", 2025)])
    doc26 = colapsar_docentes(limpio[("docentes", 2026)])
    doc25.to_parquet(SALIDA / "docentes_2025_persona.parquet")
    doc26.to_parquet(SALIDA / "docentes_2026_persona.parquet")
    doc_cols = ["dias_totales", "accedio", "Sexo", "vuln_q", "n_centros", "n_materias"]
    panel_doc = panel(doc25, doc26, doc_cols, "docentes")
    panel_doc.to_parquet(SALIDA / "panel_docentes.parquet")

    print("\nOK. Salidas en:", SALIDA)


if __name__ == "__main__":
    main()
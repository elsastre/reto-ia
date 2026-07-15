"""
Pipeline real - Reto 1 CREA (bases nuevas, joinables por ID_persona dentro del mismo tipo)
==========================================================================================
Hace, de forma INDEPENDIENTE por tipo (estudiantes / docentes):
  1. Limpieza (esquema nuevo de 17 cols)
  2. IVSMEDIA y CONTEXTO -> quintil numerico 1..5
  3. Persistencia longitudinal por ID_CENTRO_<tipo>: se conservan solo filas
     cuyo centro aparece en 2025 Y 2026 (y, si CRUZAR_TIPOS_PERSISTENCIA,
     tambien en ambos anios del otro tipo). Genera *_persistente.csv.
  4. Docentes: colapso a nivel PERSONA-anio (dias son per-persona, NO sumar)
     -- disponible como funcion; no se ejecuta en main por defecto.
  5. Panel longitudinal 2025<->2026 por ID_persona (validate one_to_one)
     -- disponible como funcion; no se ejecuta en main por defecto.

REGLAS (verificadas con los datos):
  - ID_persona NO es comparable entre estudiante <-> docente.
  - ID_CENTRO se renombra por tipo (ID_CENTRO_estudiantes / ID_CENTRO_docentes)
    para evitar joins accidentales. reportes/analisis_centros.ipynb confirmo
    que, en estos datos, el mismo codigo SI es la misma entidad
    (tipo_centro/Rubro/dept_nombre coinciden al 100% en centros comunes).
    Por eso CRUZAR_TIPOS_PERSISTENCIA puede exigir persistencia del codigo
    en ambos tipos sin mezclar personas.
  - Dias del docente = per-persona (todas sus filas iguales) -> se toma 'first', no 'sum'.
  - CONTEXTO = vulnerabilidad primaria ; IVSMEDIA = vulnerabilidad media. Disjuntas por nivel.

Salidas:
  processed/<tipo>_<anio>_clean.csv              limpio, grano original
  reportes/<tipo>_<anio>_persistente.csv         base longitudinal por centro
  reportes/<tipo>_filas_eliminadas.csv           filas descartadas (auditoria)
  reportes/impacto_persistencia_<tipo>.csv       conteos / % vs df limpio
  reportes/centros_eliminados_<tipo>.csv         detalle por centro eliminado
  reportes/resumen_digestion_fase1.txt           resumen consolidado
  reportes/impacto_persistencia_fase1.csv        impacto de ambos tipos juntos
"""

import re
from pathlib import Path
import pandas as pd
import numpy as np

from compare_datasets_generic import (
    centros_presentes_en_ambos,
    separar_por_persistencia_centro,
    _normalize_text,
)

# ======================================================================
# CONFIG
# ======================================================================
# La carpeta de datos se resuelve automaticamente segun la maquina: se toma
# el primer candidato que exista. Asi el script corre igual en Windows (equipo
# de Matihas) y en Mac (equipo de Gustavo) sin editar rutas a mano.
# "Datos Ceibal 2025-2026 ver final" es la base DEFINITIVA (2025-07-15); las
# carpetas anteriores quedan como fallback por si alguna maquina no la tiene aun.
CANDIDATOS_DATOS = [
    Path.home() / "Downloads" / "Datos Ceibal 2025-2026 ver final",
    Path(r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026 ver final"),
    Path(r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026"),
    Path.home() / "Downloads" / "Datos Ceibal 2025-2025",
    Path.home() / "Downloads" / "Datos Ceibal Reto 1 2026",
]


def _resolver_carpeta_datos() -> Path:
    for c in CANDIDATOS_DATOS:
        if c.exists():
            return c
    raise FileNotFoundError(
        "No encontre ninguna carpeta de datos. Candidatos probados:\n  - "
        + "\n  - ".join(str(c) for c in CANDIDATOS_DATOS)
    )


CARPETA_DATOS = _resolver_carpeta_datos()
# Salida fuera del repo (datos sensibles): subcarpetas junto a los datos.
SALIDA = CARPETA_DATOS / "processed"
REPORTES = CARPETA_DATOS / "reportes"

BASES = [
    {"ruta": CARPETA_DATOS / "datosUCU2025_estu.xlsx", "tipo": "estudiantes", "anio": 2025},
    {"ruta": CARPETA_DATOS / "datosUCU2026_estu.xlsx", "tipo": "estudiantes", "anio": 2026},
    {"ruta": CARPETA_DATOS / "datosUCU2025_doc.xlsx",  "tipo": "docentes",    "anio": 2025},
    {"ruta": CARPETA_DATOS / "datosUCU2026_doc.xlsx",  "tipo": "docentes",    "anio": 2026},
]

DIAS = ["Dias4", "Dias5", "Dias6"]
DIAS_MAX = {"Dias4": 30, "Dias5": 31, "Dias6": 30}  # abril, mayo, junio

# Si True, un centro solo se considera persistente si ademas esta presente en
# ambos anios del OTRO tipo (interseccion simetrica).
# Ver reportes/reporte_digestion_fase1.ipynb.
CRUZAR_TIPOS_PERSISTENCIA = True


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

    # Renombra ID_CENTRO por tipo para evitar joins accidentales persona-persona
    # entre datasets. Los codigos SI pueden compararse entre tipos para
    # persistencia de centro (CRUZAR_TIPOS_PERSISTENCIA / reportes/analisis_centros).
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
# 4) PERSISTENCIA LONGITUDINAL POR CENTRO (base apta para 2025 <-> 2026)
# ======================================================================
def _col_centro(tipo: str) -> str:
    return f"ID_CENTRO_{tipo}"


def _fila_impacto(anio, df_total, df_persist, df_elim, col_centro, centros_ambos) -> dict:
    centros = set(df_total[col_centro].dropna().map(_normalize_text).unique())
    return {
        "tipo": None,  # relleno el caller
        "anio": anio,
        "filas": len(df_total),
        "filas_persistentes": len(df_persist),
        "filas_eliminadas": len(df_elim),
        "%_eliminadas": round(100 * len(df_elim) / len(df_total), 3) if len(df_total) else 0.0,
        "%_persistentes": round(100 * len(df_persist) / len(df_total), 3) if len(df_total) else 0.0,
        "centros": len(centros),
        "centros_desfasados": len(centros - set(centros_ambos)),
    }


def filtrar_persistencia_centro(
    df_25: pd.DataFrame,
    df_26: pd.DataFrame,
    tipo: str,
    cruzar_con: tuple | None = None,
    verbose: bool = True,
) -> dict:
    """Separa cada anio en (persistentes, eliminadas) segun IDs de centro.

    Criterio: un centro se conserva solo si aparece en 2025 Y 2026 del dataset
    principal. Si se pasa `cruzar_con=(otro_25, otro_26, col_centro_otro)`,
    ademas debe aparecer en ambos anios del otro tipo.

    Devuelve un dict con DataFrames NUEVOS y metricas; no modifica los inputs.
    """
    col = _col_centro(tipo)
    centros_ambos = centros_presentes_en_ambos(
        df_25, df_26, col, cruzar_con=cruzar_con
    )

    p25, e25 = separar_por_persistencia_centro(df_25, col, centros_ambos)
    p26, e26 = separar_por_persistencia_centro(df_26, col, centros_ambos)
    eliminadas = pd.concat([e25, e26], ignore_index=True)

    centros_25 = set(df_25[col].dropna().map(_normalize_text).unique())
    centros_26 = set(df_26[col].dropna().map(_normalize_text).unique())
    n_no_conservados = len((centros_25 | centros_26) - centros_ambos)

    filas_impacto = [
        _fila_impacto("2025", df_25, p25, e25, col, centros_ambos),
        _fila_impacto("2026", df_26, p26, e26, col, centros_ambos),
    ]
    for f in filas_impacto:
        f["tipo"] = tipo

    impacto = pd.DataFrame(filas_impacto)
    tot = {
        "tipo": tipo,
        "anio": "total",
        "filas": int(impacto["filas"].sum()),
        "filas_persistentes": int(impacto["filas_persistentes"].sum()),
        "filas_eliminadas": int(impacto["filas_eliminadas"].sum()),
        "%_eliminadas": round(
            100 * impacto["filas_eliminadas"].sum() / impacto["filas"].sum(), 3
        ) if impacto["filas"].sum() else 0.0,
        "%_persistentes": round(
            100 * impacto["filas_persistentes"].sum() / impacto["filas"].sum(), 3
        ) if impacto["filas"].sum() else 0.0,
        "centros": None,
        "centros_desfasados": None,
    }
    impacto = pd.concat([impacto, pd.DataFrame([tot])], ignore_index=True)

    detalle_centros = (
        eliminadas.groupby(["anio", col]).size()
        .reset_index(name="n_filas")
        .sort_values("n_filas", ascending=False)
        .reset_index(drop=True)
        if len(eliminadas) else pd.DataFrame(columns=["anio", col, "n_filas"])
    )

    if verbose:
        print(f"\n[PERSISTENCIA {tipo}] col={col} | cruzar={'si' if cruzar_con else 'no'}")
        print(f"  centros 2025={len(centros_25)} | 2026={len(centros_26)} "
              f"| conservados={len(centros_ambos)} | no conservados={n_no_conservados}")
        print(f"  2025: {len(df_25):,} -> persistentes {len(p25):,} | eliminadas {len(e25):,}")
        print(f"  2026: {len(df_26):,} -> persistentes {len(p26):,} | eliminadas {len(e26):,}")
        print(f"  total eliminadas: {len(eliminadas):,} "
              f"({tot['%_eliminadas']}% del limpio)")

    return {
        "tipo": tipo,
        "col_centro": col,
        "centros_ambos": centros_ambos,
        "n_centros_no_conservados": n_no_conservados,
        "persistente_25": p25,
        "persistente_26": p26,
        "eliminadas_25": e25,
        "eliminadas_26": e26,
        "eliminadas": eliminadas,
        "impacto": impacto,
        "detalle_centros": detalle_centros,
    }


def guardar_persistencia(resultado: dict, carpeta: Path = None) -> Path:
    """Escribe CSVs de persistencia + auditoria en reportes/."""
    carpeta = Path(carpeta) if carpeta is not None else REPORTES
    carpeta.mkdir(parents=True, exist_ok=True)
    tipo = resultado["tipo"]

    resultado["persistente_25"].to_csv(
        carpeta / f"{tipo}_2025_persistente.csv", index=False
    )
    resultado["persistente_26"].to_csv(
        carpeta / f"{tipo}_2026_persistente.csv", index=False
    )
    resultado["eliminadas"].to_csv(
        carpeta / f"{tipo}_filas_eliminadas.csv", index=False
    )
    resultado["impacto"].to_csv(
        carpeta / f"impacto_persistencia_{tipo}.csv", index=False
    )
    resultado["detalle_centros"].to_csv(
        carpeta / f"centros_eliminados_{tipo}.csv", index=False
    )
    return carpeta


def aplicar_persistencia_ambos_tipos(
    limpios: dict,
    cruzar_tipos: bool = None,
    carpeta_reportes: Path = None,
    verbose: bool = True,
) -> dict:
    """Aplica filtrar_persistencia_centro a docentes y estudiantes.

    limpios: dict {(tipo, anio): df} con los CSV limpios en memoria.
    cruzar_tipos: None -> usa CRUZAR_TIPOS_PERSISTENCIA.
    """
    if cruzar_tipos is None:
        cruzar_tipos = CRUZAR_TIPOS_PERSISTENCIA
    carpeta_reportes = Path(carpeta_reportes) if carpeta_reportes else REPORTES

    resultados = {}
    for tipo, otro in (("docentes", "estudiantes"), ("estudiantes", "docentes")):
        d25 = limpios[(tipo, 2025)]
        d26 = limpios[(tipo, 2026)]
        cruzar_con = None
        if cruzar_tipos:
            cruzar_con = (
                limpios[(otro, 2025)],
                limpios[(otro, 2026)],
                _col_centro(otro),
            )
        res = filtrar_persistencia_centro(
            d25, d26, tipo, cruzar_con=cruzar_con, verbose=verbose
        )
        guardar_persistencia(res, carpeta_reportes)
        resultados[tipo] = res

    impacto_fase1 = pd.concat(
        [resultados["docentes"]["impacto"], resultados["estudiantes"]["impacto"]],
        ignore_index=True,
    )
    impacto_fase1.to_csv(
        carpeta_reportes / "impacto_persistencia_fase1.csv", index=False
    )

    lineas = [
        "=== DIGESTION FASE 1 — BASE LONGITUDINAL POR CENTRO (2025 <-> 2026) ===",
        "",
        f"Cruce entre tipos (interseccion de centros persistentes): "
        f"{'activado' if cruzar_tipos else 'desactivado'}",
        "",
    ]
    for tipo in ("docentes", "estudiantes"):
        res = resultados[tipo]
        tot = res["impacto"][res["impacto"]["anio"] == "total"].iloc[0]
        lineas.extend([
            f"--- {tipo.upper()} ---",
            f"Centros conservados: {len(res['centros_ambos'])}",
            f"Centros no conservados: {res['n_centros_no_conservados']}",
            f"Filas eliminadas: {int(tot['filas_eliminadas']):,} de "
            f"{int(tot['filas']):,} ({tot['%_eliminadas']}%)",
            f"Filas persistentes: {int(tot['filas_persistentes']):,} "
            f"({tot['%_persistentes']}% del limpio)",
            "",
        ])
    lineas.append(
        "Todos los centros restantes existen en ambos anios "
        "-> 0 desfasaje de centro entre 2025 y 2026."
    )
    resumen_txt = "\n".join(lineas) + "\n"
    (carpeta_reportes / "resumen_digestion_fase1.txt").write_text(
        resumen_txt, encoding="utf-8"
    )
    # Compat con el resumen previo de solo-docentes
    (carpeta_reportes / "resumen.txt").write_text(resumen_txt, encoding="utf-8")

    if verbose:
        print("\n" + resumen_txt)
        print("Auditoria / persistentes en:", carpeta_reportes)

    return resultados


# ======================================================================
# MAIN
# ======================================================================
def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    REPORTES.mkdir(parents=True, exist_ok=True)
    print("Carpeta de datos:", CARPETA_DATOS)

    # 1) Limpieza -> CSV limpios en processed/
    limpios = {}
    for base in BASES:
        df = limpiar(base)
        salida_csv = SALIDA / f"{base['tipo']}_{base['anio']}_clean.csv"
        df.to_csv(salida_csv, index=False)
        print(f"  -> {salida_csv.name} ({len(df)} filas, {len(df.columns)} cols)")
        limpios[(base["tipo"], base["anio"])] = df

    # 2) Persistencia longitudinal por centro -> reportes/*_persistente.csv
    #    (docentes + estudiantes; criterio identico; cruce configurable)
    aplicar_persistencia_ambos_tipos(limpios)

    # panel() / colapsar_docentes() quedan disponibles pero no se ejecutan aca.
    print("\nOK. Limpios en:", SALIDA)
    print("OK. Persistentes + auditoria en:", REPORTES)


if __name__ == "__main__":
    main()

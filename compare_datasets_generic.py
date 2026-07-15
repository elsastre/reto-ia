"""
Comparación automática de dos datasets sin clave primaria.

No hace falta indicar columnas: la función detecta sola qué columnas son
"categóricas" (texto/objeto, usadas como clave de agrupación) y cuáles son
"numéricas" (cantidades a comparar). Antes de comparar, normaliza los
valores de texto (minúsculas, sin espacios extra, sin acentos) para evitar
falsos desfases por diferencias de formato.
"""

import unicodedata
from pathlib import Path

import pandas as pd


def _normalize_text(value):
    """minúsculas, sin espacios al borde/duplicados, sin acentos."""
    if pd.isna(value):
        return value
    s = str(value).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("utf-8")
    s = " ".join(s.split())
    return s


def compare_datasets(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    name1: str = "dataset_1",
    name2: str = "dataset_2",
    tolerance: float = 0.0,
    normalize: bool = True,
) -> dict:
    """
    Compara automáticamente dos datasets y detecta inconsistencias.

    Detecta solo, sin configuración manual:
      - columnas que existen en un dataset pero no en el otro
      - columnas categóricas (comunes) -> valores/categorías que aparecen
        solo en uno de los dos datasets
      - columnas numéricas (comunes) -> se agrupan por todas las columnas
        categóricas comunes y se comparan las sumas, reportando desfases

    Antes de comparar, si `normalize=True` (default), las columnas de texto
    se normalizan (lower, strip, sin acentos, espacios colapsados) para que
    diferencias de formato no generen falsos desfases.

    Parámetros
    ----------
    df1, df2 : pd.DataFrame
        Datasets a comparar.
    name1, name2 : str
        Etiquetas para identificar cada dataset en el resultado.
    tolerance : float
        Diferencia mínima para considerar que hay desfase numérico
        (útil para ignorar errores de redondeo). Por defecto 0.
    normalize : bool
        Si es True, normaliza texto (lower/strip/sin acentos) antes de
        comparar. Por defecto True.

    Retorna
    -------
    dict con:
        "columnas_solo_en_<name1>" / "columnas_solo_en_<name2>": columnas
            que solo existen en uno de los datasets
        "categorias_desfasadas": dict {columna: {"solo_en_<name1>": [...],
            "solo_en_<name2>": [...]}} con valores categóricos (ya
            normalizados) que no coinciden entre datasets
        "cantidades_desfasadas": DataFrame con combinaciones de categorías
            presentes en ambos datasets pero con cantidades numéricas
            distintas
        "resumen": conteos generales de todo lo anterior
    """
    cols_solo_1 = [c for c in df1.columns if c not in df2.columns]
    cols_solo_2 = [c for c in df2.columns if c not in df1.columns]
    common_cols = [c for c in df1.columns if c in df2.columns]

    numeric_cols = [
        c for c in common_cols
        if pd.api.types.is_numeric_dtype(df1[c]) and pd.api.types.is_numeric_dtype(df2[c])
    ]
    key_cols = [c for c in common_cols if c not in numeric_cols]

    # Trabajamos sobre copias normalizadas, sin tocar los datasets originales
    d1 = df1.copy()
    d2 = df2.copy()
    if normalize:
        for col in key_cols:
            d1[col] = d1[col].map(_normalize_text)
            d2[col] = d2[col].map(_normalize_text)

    # --- 1. Categorías (valores) que no coinciden, columna por columna ---
    categorias_desfasadas = {}
    for col in key_cols:
        v1 = set(d1[col].dropna().unique())
        v2 = set(d2[col].dropna().unique())
        solo1, solo2 = v1 - v2, v2 - v1
        if solo1 or solo2:
            categorias_desfasadas[col] = {
                f"solo_en_{name1}": sorted(solo1, key=str),
                f"solo_en_{name2}": sorted(solo2, key=str),
            }

    # --- 2. Cantidades desfasadas para combinaciones presentes en ambos ---
    cantidades_desfasadas = pd.DataFrame()
    combinaciones_comunes = 0

    if key_cols and numeric_cols:
        g1 = d1.groupby(key_cols, dropna=False)[numeric_cols].sum().reset_index()
        g2 = d2.groupby(key_cols, dropna=False)[numeric_cols].sum().reset_index()

        merged = g1.merge(
            g2, on=key_cols, how="inner", suffixes=(f"_{name1}", f"_{name2}")
        )
        combinaciones_comunes = len(merged)

        filas_desfasadas = []
        for col in numeric_cols:
            c1, c2 = f"{col}_{name1}", f"{col}_{name2}"
            diff = merged[c1] - merged[c2]
            mask = diff.abs() > tolerance
            if mask.any():
                sub = merged.loc[mask, key_cols + [c1, c2]].copy()
                sub.insert(len(key_cols), "columna", col)
                sub["diferencia"] = diff[mask]
                sub = sub.rename(columns={c1: "valor_" + name1, c2: "valor_" + name2})
                filas_desfasadas.append(sub)
        if filas_desfasadas:
            cantidades_desfasadas = pd.concat(filas_desfasadas, ignore_index=True)

    resumen = {
        "columnas_solo_en_" + name1: cols_solo_1,
        "columnas_solo_en_" + name2: cols_solo_2,
        "columnas_categoricas_comparadas": key_cols,
        "columnas_numericas_comparadas": numeric_cols,
        "columnas_con_categorias_desfasadas": list(categorias_desfasadas.keys()),
        "combinaciones_comunes_comparadas": combinaciones_comunes,
        "combinaciones_con_cantidad_desfasada": len(cantidades_desfasadas),
        "filas_totales_" + name1: len(df1),
        "filas_totales_" + name2: len(df2),
    }

    return {
        f"columnas_solo_en_{name1}": cols_solo_1,
        f"columnas_solo_en_{name2}": cols_solo_2,
        "categorias_desfasadas": categorias_desfasadas,
        "cantidades_desfasadas": cantidades_desfasadas,
        "resumen": resumen,
    }


# La función no imprime ni muestra nada por sí sola: solo retorna el dict.
# En el notebook, la vista previa la controlás vos, por ejemplo:
#
#   resultado = compare_datasets(df1, df2, name1="df1", name2="df2")
#   resultado["resumen"]
#   resultado["categorias_desfasadas"]
#   resultado["cantidades_desfasadas"].head()


def reporte_comparacion(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    name1: str = "dataset_1",
    name2: str = "dataset_2",
    tolerance: float = 0.0,
    normalize: bool = True,
    max_items: int = 20,
) -> str:
    """
    Hace lo mismo que compare_datasets(), pero arma un texto legible en
    lugar de un dict con DataFrames. Pensado para leer directo (print) el
    resultado en el notebook.

    Parámetros: iguales a compare_datasets(), más
    max_items : int
        Máximo de valores/filas a listar por sección antes de resumir con
        "... y N más". Por defecto 20.

    Retorna
    -------
    str : reporte en texto plano, listo para imprimir con print(reporte).
    """
    r = compare_datasets(df1, df2, name1, name2, tolerance, normalize)
    resumen = r["resumen"]

    def _lista(items, max_items):
        items = list(items)
        if not items:
            return "  (ninguna)"
        mostrados = items[:max_items]
        texto = "\n".join(f"  - {x}" for x in mostrados)
        restantes = len(items) - len(mostrados)
        if restantes > 0:
            texto += f"\n  ... y {restantes} más"
        return texto

    L = []
    L.append(f"COMPARACIÓN: {name1}  vs  {name2}")
    L.append("=" * 60)
    L.append(f"Filas totales -> {name1}: {resumen['filas_totales_' + name1]} | "
              f"{name2}: {resumen['filas_totales_' + name2]}")
    L.append(f"Columnas categóricas comparadas: {resumen['columnas_categoricas_comparadas']}")
    L.append(f"Columnas numéricas comparadas:   {resumen['columnas_numericas_comparadas']}")

    L.append("")
    L.append(f"1) COLUMNAS QUE NO COINCIDEN")
    L.append("-" * 60)
    L.append(f"Solo en {name1}:")
    L.append(_lista(r[f"columnas_solo_en_{name1}"], max_items))
    L.append(f"Solo en {name2}:")
    L.append(_lista(r[f"columnas_solo_en_{name2}"], max_items))

    L.append("")
    L.append("2) CATEGORÍAS QUE NO COINCIDEN")
    L.append("-" * 60)
    if not r["categorias_desfasadas"]:
        L.append("  (todas las categorías coinciden)")
    else:
        for col, det in r["categorias_desfasadas"].items():
            L.append(f"Columna '{col}':")
            L.append(f"  Solo en {name1}:")
            L.append("  " + _lista(det[f"solo_en_{name1}"], max_items).replace("\n", "\n  "))
            L.append(f"  Solo en {name2}:")
            L.append("  " + _lista(det[f"solo_en_{name2}"], max_items).replace("\n", "\n  "))

    L.append("")
    L.append("RESUMEN")
    L.append("-" * 60)
    L.append(f"  Combinaciones comunes comparadas: {resumen['combinaciones_comunes_comparadas']}")
    L.append(f"  Combinaciones con cantidad desfasada: {resumen['combinaciones_con_cantidad_desfasada']}")
    L.append(f"  Columnas con categorías desfasadas: {resumen['columnas_con_categorias_desfasadas']}")

    return "\n".join(L)


# Uso: print(reporte_comparacion(df1, df2, name1="df1", name2="df2"))


def detectar_duplicados(df: pd.DataFrame, subset=None, keep="first") -> pd.Series:
    """
    Detecta filas duplicadas y devuelve una máscara booleana (Serie con el
    mismo índice que df), lista para usar y modificar el DataFrame.

    Parámetros
    ----------
    subset : list[str] | None
        Columnas a considerar para definir "duplicado". None = todas las
        columnas.
    keep : 'first' | 'last' | False
        - 'first' (default): marca True las copias repetidas después de la
          primera aparición. Sirve para eliminar duplicados quedándote con
          la primera copia:
              mask = detectar_duplicados(df)
              df_limpio = df[~mask]                  # o
              df.drop(df[mask].index, inplace=True)
        - 'last': igual pero conserva la última copia.
        - False: marca True TODAS las copias (incluida la primera), útil
          para revisar los grupos completos antes de decidir qué hacer:
              mask = detectar_duplicados(df, keep=False)
              df[mask].sort_values(subset or df.columns.tolist())

    Retorna
    -------
    pd.Series booleana, mismo índice que df (operable: se puede indexar o
    usar en .drop() directamente).
    """
    return df.duplicated(subset=subset, keep=keep)


def reporte_duplicados(df: pd.DataFrame, subset=None) -> str:
    """
    Informa cuántas filas repetidas hay en el DataFrame. No modifica nada,
    solo da información (usar detectar_duplicados() para obtener la
    máscara operable).

    Parámetros
    ----------
    subset : list[str] | None
        Columnas a considerar para definir "duplicado". None = todas.

    Retorna
    -------
    str: reporte en texto plano, para imprimir con print(reporte).
    """
    total = len(df)
    mask_todas = df.duplicated(subset=subset, keep=False)
    mask_extra = df.duplicated(subset=subset, keep="first")
    n_involucradas = int(mask_todas.sum())
    n_extra = int(mask_extra.sum())
    n_grupos = n_involucradas - n_extra

    L = []
    L.append("DUPLICADOS")
    L.append("=" * 40)
    L.append(f"Filas totales: {total}")
    L.append(f"Columnas consideradas: {'todas' if subset is None else subset}")
    L.append(f"Grupos de valores repetidos: {n_grupos}")
    L.append(f"Filas involucradas en duplicados (incluye la primera copia): {n_involucradas}")
    L.append(f"Filas 'extra' (sobrarían si se deduplica dejando 1 copia por grupo): {n_extra}")
    if total:
        L.append(f"Porcentaje de filas extra sobre el total: {n_extra / total:.1%}")

    return "\n".join(L)


def limpiar_duplicados(datasets: dict, subset=None, keep: str = "first", inplace: bool = True) -> dict:
    """
    Itera dinámicamente sobre un dict {nombre: DataFrame} y usa
    df.duplicated() (pandas) para eliminar las filas repetidas de cada uno.

    Uso típico:
        datasets = {"df1": df1, "df2": df2, "df3": df3}
        resumen = limpiar_duplicados(datasets)
        print(resumen)   # {"df1": 2, "df2": 0, "df3": 5}

    Parámetros
    ----------
    datasets : dict[str, pd.DataFrame]
        Diccionario nombre -> DataFrame. Si lo armaste con las variables
        originales (ej: {"df1": df1}), cada valor es el MISMO objeto que
        df1, no una copia.
    subset : list[str] | None
        Columnas a considerar para definir "duplicado". None = todas.
    keep : 'first' | 'last'
        Qué copia conservar al eliminar duplicados.
    inplace : bool
        True (default): modifica los DataFrames originales in-place. Como
        el dict referencia los mismos objetos, esto también deja limpias
        las variables originales (df1, df2, ...) fuera de la función.
        False: no toca los originales; en vez de eso reemplaza la entrada
        correspondiente en `datasets` por una copia ya limpia.

    Retorna
    -------
    dict {nombre: cantidad_de_filas_duplicadas_eliminadas}
    """
    resumen = {}
    for nombre, df in datasets.items():
        mask = df.duplicated(subset=subset, keep=keep)
        n = int(mask.sum())
        resumen[nombre] = n
        if inplace:
            df.drop(df[mask].index, inplace=True)
        else:
            datasets[nombre] = df[~mask].reset_index(drop=True)
    return resumen


# ======================================================================
# Utilidades de carga / preparación / detección (centralizadas para notebooks)
# ======================================================================
def cargar(ruta) -> pd.DataFrame:
    """Lee un dataset segun su extension: .xlsx/.xls con read_excel, el resto
    (.csv/.txt) con read_csv."""
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(ruta)
    return pd.read_csv(ruta, low_memory=False)


def preparar_para_comparar(a: pd.DataFrame, b: pd.DataFrame, verbose: bool = True):
    """Deja dos datasets listos para compare_datasets / detectar_desfasajes.

    Resuelve dos casos que rompen el merge interno de compare_datasets:
      1. Columnas comunes vacias en uno de los dos datasets -> se excluyen
         (una columna toda-NaN se infiere float64 y no aporta comparacion).
      2. Columnas comunes numericas en uno y texto en el otro -> se pasan a
         texto en ambos para poder compararlas como categorias.

    Devuelve (a, b) como copias nuevas; no modifica los originales.
    """
    a, b = a.copy(), b.copy()
    comunes = [c for c in a.columns if c in b.columns]
    vacias, mixtas = [], []
    for col in comunes:
        if a[col].notna().sum() == 0 or b[col].notna().sum() == 0:
            a = a.drop(columns=col)
            b = b.drop(columns=col)
            vacias.append(col)
            continue
        num_a = pd.api.types.is_numeric_dtype(a[col])
        num_b = pd.api.types.is_numeric_dtype(b[col])
        if num_a != num_b:
            a[col] = a[col].astype("string")
            b[col] = b[col].astype("string")
            mixtas.append(col)
    if verbose:
        print("Columnas vacias en un dataset (excluidas):", vacias or "(ninguna)")
        print("Columnas mixto (num/texto) pasadas a texto:", mixtas or "(ninguna)")
    return a, b


def detectar_desfasajes(df1, df2, name1="df1", name2="df2", tolerance=0.0,
                        normalize=True, con_filas=False) -> dict:
    """Deteccion operable derivada de compare_datasets (que solo reporta).

    Analoga a detectar_duplicados: en vez de texto, devuelve estructuras
    listas para filtrar/actuar. Retorna un dict con:
      - 'categorias': DataFrame largo [columna, valor, solo_en] con cada valor
        categorico que aparece en un solo dataset. Si con_filas=True se agrega
        la columna 'n_filas' (cuantas filas cubre ese valor en su dataset) y se
        ordena por columna y n_filas.
      - 'cantidades': DataFrame de combinaciones cuya suma numerica difiere.
      - 'resumen': el dict 'resumen' de compare_datasets (para no re-computar).
    """
    r = compare_datasets(df1, df2, name1, name2, tolerance, normalize)
    filas = []
    for col, det in r["categorias_desfasadas"].items():
        for valor in det[f"solo_en_{name1}"]:
            filas.append({"columna": col, "valor": valor, "solo_en": name1})
        for valor in det[f"solo_en_{name2}"]:
            filas.append({"columna": col, "valor": valor, "solo_en": name2})
    categorias = pd.DataFrame(filas, columns=["columna", "valor", "solo_en"])

    if con_filas and not categorias.empty:
        # compare_datasets normaliza el texto antes de comparar; para contar
        # filas hay que aplicar la MISMA normalizacion a los valores originales.
        prep = (lambda s: s.map(_normalize_text)) if normalize else (lambda s: s)
        cols = categorias["columna"].unique()
        vc = {
            name1: {c: prep(df1[c]).value_counts() for c in cols},
            name2: {c: prep(df2[c]).value_counts() for c in cols},
        }
        categorias["n_filas"] = categorias.apply(
            lambda x: int(vc[x["solo_en"]][x["columna"]].get(x["valor"], 0)), axis=1
        )
        categorias = (categorias
                      .sort_values(["columna", "n_filas"], ascending=[True, False])
                      .reset_index(drop=True))

    return {"categorias": categorias,
            "cantidades": r["cantidades_desfasadas"],
            "resumen": r["resumen"]}


def limpiar_duplicados_df(df: pd.DataFrame, subset=None, keep: str = "first",
                          verbose: bool = False) -> pd.DataFrame:
    """Limpieza: devuelve un DataFrame NUEVO sin las filas duplicadas.

    Contraparte de detectar_duplicados (que devuelve la mascara): aca se aplica
    esa mascara y se retorna el dataset limpio, sin modificar el original (a
    diferencia de limpiar_duplicados, que opera in-place sobre un dict).
    """
    mask = detectar_duplicados(df, subset=subset, keep=keep)
    limpio = df[~mask].reset_index(drop=True)
    if verbose:
        print(f"  {int(mask.sum())} filas duplicadas eliminadas: {len(df)} -> {len(limpio)}")
    return limpio


def unir_anios(df_2025: pd.DataFrame, df_2026: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Union de filas (concat/UNION) de docentes o estudiantes 2025 + 2026.

    Apila las dos tablas una debajo de la otra en un DataFrame NUEVO, sin
    modificar los originales. Pensada para los datasets limpios del proyecto
    (mismo esquema de columnas, con 'anio' ya presente en cada fila para poder
    distinguir el origen despues de unir).

    Si alguna columna existe en un solo dataset, igual se unen: la que falta
    queda en NaN para las filas del otro año (comportamiento estandar de
    pd.concat con columnas no coincidentes).
    """
    cols_1 = set(df_2025.columns)
    cols_2 = set(df_2026.columns)
    if cols_1 != cols_2:
        solo_2025 = cols_1 - cols_2
        solo_2026 = cols_2 - cols_1
        if verbose:
            print("Columnas solo en 2025:", solo_2025 or "(ninguna)")
            print("Columnas solo en 2026:", solo_2026 or "(ninguna)")

    unido = pd.concat([df_2025, df_2026], ignore_index=True)
    if verbose:
        print(f"Union: {len(df_2025)} (2025) + {len(df_2026)} (2026) -> {len(unido)} filas totales")
    return unido


def detectar_centros_relacionados(
    centros_df: pd.DataFrame,
    otro_2025: pd.DataFrame,
    otro_2026: pd.DataFrame,
    col_valor: str = "valor",
    col_anio: str = "solo_en",
    col_centro_otro: str = "ID_CENTRO_estudiantes",
    label: str = "estudiantes",
    normalize: bool = True,
) -> pd.DataFrame:
    """Para una lista de centros (ej. los desfasados de docentes, columna
    ID_CENTRO_docentes de desfasajes_df), chequea si cada uno aparece tambien
    en el OTRO dataset (estudiantes o docentes) del anio correspondiente.
    Generica en ambas direcciones: docentes->estudiantes o estudiantes->docentes,
    segun que se le pase en otro_2025/otro_2026/col_centro_otro/label.

    Parametros
    ----------
    centros_df : DataFrame con al menos [col_valor, col_anio] -- ej. el
        subconjunto de desfasajes_df con columna == 'ID_CENTRO_docentes'.
    otro_2025, otro_2026 : datasets limpios del OTRO tipo (con col_centro_otro).
    col_valor : columna de centros_df con el codigo de centro (default 'valor').
    col_anio : columna de centros_df con el anio '2025'/'2026' (default 'solo_en').
    col_centro_otro : columna de centro en los datasets del otro tipo.
    label : nombra las columnas de salida (n_filas_<label>, relacionado_con_<label>).
    normalize : normaliza texto (lower/sin acentos) antes de comparar, igual
        que compare_datasets, para evitar falsos negativos por formato.

    Retorna
    -------
    DataFrame NUEVO = centros_df + columnas:
      - n_filas_<label> : filas del otro dataset en ese centro y anio.
      - relacionado_con_<label> : True si n_filas_<label> > 0.
    """
    prep = (lambda s: s.map(_normalize_text)) if normalize else (lambda s: s)
    conteos = {
        "2025": prep(otro_2025[col_centro_otro]).value_counts(),
        "2026": prep(otro_2026[col_centro_otro]).value_counts(),
    }
    out = centros_df.copy()
    out[f"n_filas_{label}"] = out.apply(
        lambda r: int(conteos[str(r[col_anio])].get(r[col_valor], 0)), axis=1
    )
    out[f"relacionado_con_{label}"] = out[f"n_filas_{label}"] > 0
    return out


def detectar_centros_relacionados_estudiantes(centros_df, est_2025, est_2026, **kwargs):
    """Alias de detectar_centros_relacionados con label/col_centro_otro fijos a
    estudiantes, para compatibilidad con notebooks existentes."""
    kwargs.setdefault("col_centro_otro", "ID_CENTRO_estudiantes")
    kwargs.setdefault("label", "estudiantes")
    return detectar_centros_relacionados(centros_df, est_2025, est_2026, **kwargs)


def resumen_por_centro(df: pd.DataFrame, col_centro: str, prefijo: str) -> pd.DataFrame:
    """Resume un dataset a 1 fila por centro (columna 'centro').

    Paso previo obligatorio antes de un full join por centro: ID_CENTRO se
    repite muchas veces por dataset (1 fila por estudiante o por asignacion
    docente), asi que mergear directo sobre esa columna produce un producto
    cartesiano por centro y explota en filas. Acá se agrega primero.

    Calcula, con columnas prefijadas para no chocar entre tablas:
      - <prefijo>_n_filas   : cantidad de filas del dataset en ese centro
      - <prefijo>_n_personas: ID_persona unicos, si la columna existe
      - <prefijo>_<col>_prom: promedio de dias_totales/accedio/vuln_q, si existen
    """
    g = df.groupby(col_centro)
    resumen = pd.DataFrame({f"{prefijo}_n_filas": g.size()})
    if "ID_persona" in df.columns:
        resumen[f"{prefijo}_n_personas"] = g["ID_persona"].nunique()
    for col in ("dias_totales", "accedio", "vuln_q"):
        if col in df.columns:
            resumen[f"{prefijo}_{col}_prom"] = g[col].mean()
    return resumen.reset_index().rename(columns={col_centro: "centro"})


def full_join_por_centro(tablas: dict, verbose: bool = True) -> pd.DataFrame:
    """Full outer join por centro de N tablas, cada una resumida primero.

    tablas: dict {nombre: (df, columna_centro)}. Cada tabla se resume con
    resumen_por_centro (1 fila por centro, columnas prefijadas por nombre) y
    luego se unen todas con un merge 'outer' encadenado sobre 'centro': un
    centro que no exista en alguna tabla queda con NaN en esas columnas.

    OJO (documentado en estructura.py): ID_CENTRO se renombra por tipo porque
    la anonimizacion NO garantiza que el mismo 'centro' en estudiantes y en
    docentes sea el mismo centro fisico. Este join es exploratorio: los NaN
    y los matches entre tipos distintos no implican una correspondencia real.

    Devuelve un DataFrame NUEVO (no modifica las tablas originales).
    """
    resumenes = [resumen_por_centro(df, col, nombre) for nombre, (df, col) in tablas.items()]
    unido = resumenes[0]
    for r in resumenes[1:]:
        unido = unido.merge(r, on="centro", how="outer")

    if verbose:
        print(f"Full join por centro: {len(unido)} centros, {len(unido.columns)} columnas")
        for nombre, (df, col) in tablas.items():
            print(f"  {nombre}: {df[col].nunique()} centros unicos ({col})")

    return unido


def construir_tabla_centros(
    df: pd.DataFrame,
    col_centro: str,
    attrs=("tipo_centro", "Rubro", "dept_nombre"),
    normalize: bool = True,
) -> pd.DataFrame:
    """DataFrame NUEVO con 1 fila por centro: [centro] + attrs (por defecto
    tipo_centro, Rubro, dept_nombre). Paso previo para comparar si un mismo
    codigo de centro representa la MISMA entidad en dos datasets distintos.

    Si el dataset trae mas de una combinacion de attrs para el mismo centro
    (inconsistencia interna), se queda con la primera aparicion.
    """
    cols = [col_centro] + list(attrs)
    tabla = (df[cols]
             .drop_duplicates(subset=[col_centro])
             .rename(columns={col_centro: "centro"})
             .reset_index(drop=True))
    if normalize:
        for c in attrs:
            tabla[c] = tabla[c].map(_normalize_text)
    return tabla


def comparar_entidades_centro(
    centros_a: pd.DataFrame,
    centros_b: pd.DataFrame,
    name_a: str = "a",
    name_b: str = "b",
    attrs=("tipo_centro", "Rubro", "dept_nombre"),
    verbose: bool = True,
) -> pd.DataFrame:
    """Compara dos tablas de centros (salida de construir_tabla_centros) por
    el codigo de centro en comun, e informa (print) los que NO son la misma
    entidad: mismo codigo mas algun atributo (tipo_centro/Rubro/dept_nombre)
    distinto entre name_a y name_b.

    OJO (documentado en estructura.py): ID_CENTRO se renombra por tipo porque
    la anonimizacion no garantiza que el mismo codigo sea el mismo centro
    fisico entre estudiantes y docentes. Esta funcion es justamente para
    CONFIRMAR o DESCARTAR esa hipotesis con los datos: si la lista de
    "distintos" queda vacia (o casi), el codigo de centro es confiable entre
    ambos datasets; si no, la regla de no cruzar por ID_CENTRO sigue vigente.

    Retorna un DataFrame NUEVO con los centros comunes que difieren.
    """
    merged = centros_a.merge(centros_b, on="centro", how="inner",
                             suffixes=(f"_{name_a}", f"_{name_b}"))

    mask_distintos = pd.Series(False, index=merged.index)
    for attr in attrs:
        mask_distintos |= merged[f"{attr}_{name_a}"] != merged[f"{attr}_{name_b}"]
    distintos = merged[mask_distintos].reset_index(drop=True)

    if verbose:
        print(f"Centros comunes comparados ({name_a} vs {name_b}): {len(merged)}")
        print(f"Centros que NO son la misma entidad (algun atributo distinto): {len(distintos)} "
              f"({round(100 * len(distintos) / len(merged), 2) if len(merged) else 0.0}%)")

    return distintos


def limpiar_centros(
    df: pd.DataFrame,
    col_centro: str,
    codigos_a_excluir,
    normalize: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """Limpieza: devuelve un DataFrame NUEVO sin las filas cuyo centro esta
    en codigos_a_excluir. No modifica el original.

    Es la contraparte "limpieza -> df nuevo" de las funciones de deteccion de
    centros (detectar_centros_relacionados, comparar_entidades_centro): esas
    devuelven DataFrames con los centros problematicos (sin relacion con el
    otro tipo, o que no son la misma entidad); esta funcion toma esos codigos
    y elimina las filas correspondientes del dataset original.

    Parametros
    ----------
    df : dataset del que se eliminan filas (ej. doc25, est26).
    col_centro : columna de centro en df (ej. 'ID_CENTRO_docentes').
    codigos_a_excluir : coleccion de codigos de centro a eliminar. Puede ser
        una lista/Serie/set de valores, o directamente la columna 'valor' de
        detectar_centros_relacionados (centros sin relacion) o 'centro' de
        comparar_entidades_centro (centros que no son la misma entidad).
    normalize : normaliza (lower/sin acentos) tanto df[col_centro] como los
        codigos a excluir antes de comparar, igual que el resto del modulo.
    """
    codigos = set(codigos_a_excluir)
    columna = df[col_centro]
    if normalize:
        columna = columna.map(_normalize_text)
        codigos = {_normalize_text(c) for c in codigos}
    mask = columna.isin(codigos)
    limpio = df[~mask].reset_index(drop=True)
    if verbose:
        print(f"  {int(mask.sum())} filas eliminadas (centro problematico): {len(df)} -> {len(limpio)}")
    return limpio


def detectar_centros_huerfanos(
    df: pd.DataFrame,
    col_centro: str,
    otro_df: pd.DataFrame,
    col_centro_otro: str,
    label: str = "otro",
    normalize: bool = True,
) -> pd.DataFrame:
    """Detecta centros huerfanos: codigos presentes en df que no tienen NINGUNA
    fila en otro_df, para TODOS los centros de df (no solo los desfasados entre
    anios). A diferencia de detectar_centros_relacionados (que parte de una
    lista ya filtrada, ej. desfasajes_df), esta funcion arranca de todos los
    valores unicos de col_centro en df -- por eso detecta tambien centros
    "inconsistentes de un anio a otro": los que existen en ambos anios de un
    tipo pero nunca tienen contraparte en el otro tipo.

    Retorna un DataFrame NUEVO [centro, n_filas_<label>, relacionado_con_<label>],
    uno por cada codigo unico de centro en df.
    """
    prep = (lambda s: s.map(_normalize_text)) if normalize else (lambda s: s)
    valores = df[col_centro].dropna().unique()
    valores_prep = pd.Series(valores).map(_normalize_text) if normalize else pd.Series(valores)
    conteo_otro = prep(otro_df[col_centro_otro]).value_counts()

    out = pd.DataFrame({"centro": valores_prep.values})
    out[f"n_filas_{label}"] = out["centro"].map(lambda c: int(conteo_otro.get(c, 0)))
    out[f"relacionado_con_{label}"] = out[f"n_filas_{label}"] > 0
    return out


def pipeline_limpieza_centros(
    df: pd.DataFrame,
    col_centro: str,
    anio: str,
    centros_no_relacionados: pd.DataFrame = None,
    centros_no_misma_entidad: pd.DataFrame = None,
    centros_huerfanos: pd.DataFrame = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """Pipeline: aplica detectar_centros_relacionados + comparar_entidades_centro
    + detectar_centros_huerfanos -> limpiar_centros en un solo paso, devolviendo
    un DataFrame NUEVO.

    Elimina de df, para el anio dado, las filas cuyo centro:
      1. no tiene relacion con el otro tipo de dataset (segun
         centros_no_relacionados, salida de detectar_centros_relacionados
         filtrada a 'relacionado_con_<label>' == False; solo cubre centros
         DESFASADOS, presentes en un solo anio), y/o
      2. no es la misma entidad entre datasets (segun centros_no_misma_entidad,
         salida de comparar_entidades_centro), y/o
      3. es huerfano (segun centros_huerfanos, salida de
         detectar_centros_huerfanos filtrada a 'relacionado_con_<label>' ==
         False; cubre TODOS los centros del anio, incluidos los que existen en
         ambos anios pero nunca tienen contraparte en el otro tipo -- es decir,
         son "inconsistentes de un anio a otro").

    Los tres parametros son independientes y pueden omitirse (None) si no
    aplican. No modifica df; devuelve una copia limpia.
    """
    limpio = df
    if centros_no_relacionados is not None and len(centros_no_relacionados):
        codigos = centros_no_relacionados.loc[
            centros_no_relacionados["solo_en"] == anio, "valor"
        ]
        if len(codigos):
            if verbose:
                print(f"[{anio}] eliminando centros desfasados sin relacion con el otro tipo:")
            limpio = limpiar_centros(limpio, col_centro, codigos, verbose=verbose)

    if centros_no_misma_entidad is not None and len(centros_no_misma_entidad):
        if verbose:
            print(f"[{anio}] eliminando centros que no son la misma entidad:")
        limpio = limpiar_centros(limpio, col_centro, centros_no_misma_entidad["centro"], verbose=verbose)

    if centros_huerfanos is not None and len(centros_huerfanos):
        label_cols = [c for c in centros_huerfanos.columns if c.startswith("relacionado_con_")]
        col_rel = label_cols[0] if label_cols else "relacionado_con_otro"
        codigos = centros_huerfanos.loc[~centros_huerfanos[col_rel], "centro"]
        if len(codigos):
            if verbose:
                print(f"[{anio}] eliminando centros huerfanos (inconsistentes entre anios):")
            limpio = limpiar_centros(limpio, col_centro, codigos, verbose=verbose)

    return limpio


# ======================================================================
# Persistencia longitudinal por centro (para analisis a traves del tiempo)
# ======================================================================
def centros_presentes_en_ambos(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    col_centro: str,
    cruzar_con: tuple = None,
    normalize: bool = True,
) -> set:
    """Conjunto de codigos de centro presentes en AMBOS anios de un dataset
    (ej. docentes 2025 y docentes 2026). Su complemento son los centros
    'desfasados' (que aparecen en un solo anio), que rompen cualquier analisis
    longitudinal.

    Generica para cualquier tipo (docentes, estudiantes, o lo que sea) -- no
    esta atada a un dominio especifico.

    Parametros
    ----------
    df_a, df_b : los dos anios del dataset principal (ej. doc25, doc26).
    col_centro : columna de centro en df_a/df_b.
    cruzar_con : opcional, tupla (otro_a, otro_b, col_centro_otro). Si se pasa,
        ADEMAS de exigir presencia en ambos anios de df_a/df_b, exige que el
        centro tambien este presente en ambos anios del OTRO dataset (ej.
        cruzar_con=(est25, est26, "ID_CENTRO_estudiantes") para exigir que el
        centro tambien sea persistente del lado de estudiantes). None (default)
        = sin cruce, solo persistencia dentro del dataset principal.
    """
    def s(df, col):
        serie = df[col].dropna()
        if normalize:
            serie = serie.map(_normalize_text)
        return set(serie.unique())

    propios = s(df_a, col_centro) & s(df_b, col_centro)

    if cruzar_con is not None:
        otro_a, otro_b, col_centro_otro = cruzar_con
        otros = s(otro_a, col_centro_otro) & s(otro_b, col_centro_otro)
        return propios & otros

    return propios


def separar_por_persistencia_centro(df: pd.DataFrame, col_centro: str,
                                    centros_ambos: set, normalize: bool = True):
    """Divide df en (persistentes, eliminadas) segun si su centro esta presente
    en los dos anios (centros_ambos, de centros_presentes_en_ambos).

    - persistentes: filas cuyo centro existe en 2025 Y 2026 (base longitudinal).
    - eliminadas: filas cuyo centro aparece en un solo anio (desfasadas en el
      tiempo) -> quedan aisladas en su propio DataFrame para auditarlas.

    Devuelve dos DataFrames NUEVOS; no modifica el original.
    """
    col = df[col_centro]
    ambos = set(centros_ambos)
    if normalize:
        col = col.map(_normalize_text)
        ambos = {_normalize_text(c) for c in ambos}
    mask_persistente = col.isin(ambos)
    persistentes = df[mask_persistente].reset_index(drop=True)
    eliminadas = df[~mask_persistente].reset_index(drop=True)
    return persistentes, eliminadas


# ======================================================================
# Metricas / informes exploratorios (centralizados desde notebooks)
# ======================================================================
def pct_desfasajes_categorias(
    desfasajes_df: pd.DataFrame,
    df1: pd.DataFrame,
    df2: pd.DataFrame,
) -> pd.DataFrame:
    """% de categorias desfasadas por columna, en DOS bases:
      - %_valores : sobre el total de valores unicos (union df1+df2)
      - %_filas   : sobre el total de filas (len(df1)+len(df2))

    Espera `desfasajes_df` con columnas [columna, valor, solo_en, n_filas]
    (salida de detectar_desfasajes(..., con_filas=True)["categorias"]).
    """
    if desfasajes_df is None or desfasajes_df.empty:
        return pd.DataFrame(columns=[
            "columna", "valores_desfasados", "valores_unicos_totales", "%_valores",
            "filas_desfasadas", "filas_totales", "%_filas",
        ])

    total_filas = len(df1) + len(df2)
    filas_pct = []
    for col in desfasajes_df["columna"].unique():
        sub = desfasajes_df[desfasajes_df["columna"] == col]
        total_unicos = len(
            set(df1[col].dropna().unique()) | set(df2[col].dropna().unique())
        )
        n_valores = len(sub)
        n_filas_desf = int(sub["n_filas"].sum()) if "n_filas" in sub.columns else 0
        filas_pct.append({
            "columna": col,
            "valores_desfasados": n_valores,
            "valores_unicos_totales": total_unicos,
            "%_valores": round(100 * n_valores / total_unicos, 2) if total_unicos else 0.0,
            "filas_desfasadas": n_filas_desf,
            "filas_totales": total_filas,
            "%_filas": round(100 * n_filas_desf / total_filas, 2) if total_filas else 0.0,
        })
    return pd.DataFrame(filas_pct).sort_values("%_filas", ascending=False).reset_index(drop=True)


def pct_combinaciones_cantidad(desfasajes: dict) -> dict:
    """% de combinaciones con AL MENOS una cantidad desfasada.

    'cantidades' trae una fila POR columna numerica desfasada (misma combinacion
    puede repetirse), asi que se cuentan combinaciones UNICAS.
    """
    resumen = desfasajes["resumen"]
    key_cols = resumen.get("columnas_categoricas_comparadas") or []
    cantidades = desfasajes.get("cantidades")
    if cantidades is None or len(cantidades) == 0 or not key_cols:
        unicas = 0
    else:
        cols_ok = [c for c in key_cols if c in cantidades.columns]
        unicas = cantidades[cols_ok].drop_duplicates().shape[0] if cols_ok else 0

    comunes = resumen.get("combinaciones_comunes_comparadas") or 0
    pct = round(100 * unicas / comunes, 2) if comunes else 0.0
    return {
        "combinaciones_comunes": comunes,
        "filas_cantidad_desfasada": resumen.get("combinaciones_con_cantidad_desfasada", 0),
        "combinaciones_unicas_desfasadas": unicas,
        "%_combinaciones_desfasadas": pct,
    }


def tops_desfasajes(desfasajes_df: pd.DataFrame, top: int = 15) -> dict:
    """Top-N valores desfasados por n_filas, para cada columna.

    Retorna dict {columna: DataFrame con hasta `top` filas}.
    """
    if desfasajes_df is None or desfasajes_df.empty:
        return {}
    out = {}
    for col in sorted(desfasajes_df["columna"].unique()):
        sub = desfasajes_df[desfasajes_df["columna"] == col]
        if "n_filas" in sub.columns:
            sub = sub.sort_values("n_filas", ascending=False)
        out[col] = sub.head(top).reset_index(drop=True)
    return out


def informe_centros_relacionados(
    centros_cruce: pd.DataFrame,
    totales_otro: dict,
    label: str = "estudiantes",
    col_anio: str = "solo_en",
    verbose: bool = True,
) -> dict:
    """Resume centros desfasados relacionados / no relacionados con el otro tipo.

    centros_cruce: salida de detectar_centros_relacionados (+ alias).
    totales_otro: {\"2025\": n_filas, \"2026\": n_filas} del OTRO tipo.
    label: mismo string usado en detectar_centros_relacionados.

    Retorna dict con DataFrames 'relacionados' / 'no_relacionados' y metricas
    por anio. Si verbose=True, imprime el informe legible.
    """
    col_rel = f"relacionado_con_{label}"
    col_n = f"n_filas_{label}"
    relacionados = centros_cruce[centros_cruce[col_rel]].copy()
    no_relacionados = centros_cruce[~centros_cruce[col_rel]].copy()

    metricas = []
    for anio in ("2025", "2026"):
        sub_rel = relacionados[relacionados[col_anio] == anio]
        sub_no = no_relacionados[no_relacionados[col_anio] == anio]
        n_cubiertos = int(sub_rel[col_n].sum()) if len(sub_rel) and col_n in sub_rel else 0
        total = totales_otro.get(anio, 0) or 0
        metricas.append({
            "anio": anio,
            "centros_relacionados": len(sub_rel),
            "centros_no_relacionados": len(sub_no),
            "centros_desfasados": len(sub_rel) + len(sub_no),
            f"filas_{label}_cubiertas": n_cubiertos,
            f"%_filas_{label}": round(100 * n_cubiertos / total, 2) if total else 0.0,
            f"total_{label}": total,
        })

    if verbose:
        print(f"=== Centros desfasados RELACIONADOS con {label} ===\n")
        for m in metricas:
            print(
                f"Año {m['anio']}: {m['centros_relacionados']} centros relacionados, "
                f"cubren {m[f'filas_{label}_cubiertas']:,} filas de {label} "
                f"({m[f'%_filas_{label}']}% del total {label} {m['anio']} = "
                f"{m[f'total_{label}']:,})"
            )
        print(f"\n=== Centros desfasados SIN relación con {label} ===\n")
        for m in metricas:
            print(
                f"Año {m['anio']}: {m['centros_no_relacionados']} centros sin relación "
                f"(de {m['centros_desfasados']} desfasados totales)"
            )

    return {
        "relacionados": relacionados.reset_index(drop=True),
        "no_relacionados": no_relacionados.reset_index(drop=True),
        "metricas": pd.DataFrame(metricas),
    }

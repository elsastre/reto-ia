"""
Comparación automática de dos datasets sin clave primaria.

No hace falta indicar columnas: la función detecta sola qué columnas son
"categóricas" (texto/objeto, usadas como clave de agrupación) y cuáles son
"numéricas" (cantidades a comparar). Antes de comparar, normaliza los
valores de texto (minúsculas, sin espacios extra, sin acentos) para evitar
falsos desfases por diferencias de formato.
"""

import unicodedata

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

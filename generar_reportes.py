"""
Genera reportes de calidad de datos a partir de dos datasets, reutilizando
las funciones de `compare_datasets.py`.

Produce tres reportes en texto plano:
  1. Duplicados en el dataset 1
  2. Duplicados en el dataset 2
  3. Comparación entre ambos datasets (columnas, categorías y cantidades)

Uso como script (línea de comandos)
-----------------------------------
    python generar_reportes.py datos_a.csv datos_b.csv
    python generar_reportes.py a.xlsx b.xlsx --name1 enero --name2 febrero
    python generar_reportes.py a.csv b.csv --salida reporte.txt --tolerance 0.01

Uso como módulo (desde un notebook u otro script)
-------------------------------------------------
    from generar_reportes import generar_reportes
    texto = generar_reportes(df1, df2, name1="df1", name2="df2")
    print(texto)
"""

import argparse

import pandas as pd

from compare_datasets_generic import reporte_comparacion, reporte_duplicados


def _cargar(ruta: str) -> pd.DataFrame:
    """Carga un dataset desde CSV o Excel según la extensión del archivo."""
    ruta_baja = ruta.lower()
    if ruta_baja.endswith((".xlsx", ".xls")):
        return pd.read_excel(ruta)
    if ruta_baja.endswith((".csv", ".txt")):
        return pd.read_csv(ruta)
    raise ValueError(
        f"Extensión no soportada para '{ruta}'. Usá .csv, .txt, .xlsx o .xls."
    )


def generar_reportes(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    name1: str = "dataset_1",
    name2: str = "dataset_2",
    tolerance: float = 0.0,
    normalize: bool = True,
    subset=None,
    max_items: int = 20,
) -> str:
    """
    Arma un único reporte de texto que combina:
      - duplicados en cada dataset (reporte_duplicados)
      - comparación entre ambos datasets (reporte_comparacion)

    Parámetros
    ----------
    df1, df2 : pd.DataFrame
        Datasets a analizar.
    name1, name2 : str
        Etiquetas para identificar cada dataset en el reporte.
    tolerance : float
        Diferencia mínima para reportar desfase numérico (pasa a
        reporte_comparacion). Por defecto 0.
    normalize : bool
        Normaliza texto antes de comparar. Por defecto True.
    subset : list[str] | None
        Columnas a considerar para detectar duplicados. None = todas.
    max_items : int
        Máximo de items a listar por sección en la comparación.

    Retorna
    -------
    str : reporte completo en texto plano, listo para imprimir o guardar.
    """
    bloques = []

    titulo = f" REPORTES DE CALIDAD DE DATOS: {name1} vs {name2} "
    bloques.append(titulo.center(70, "#"))
    bloques.append("")

    bloques.append(f">>> DUPLICADOS EN '{name1}'")
    bloques.append(reporte_duplicados(df1, subset=subset))
    bloques.append("")

    bloques.append(f">>> DUPLICADOS EN '{name2}'")
    bloques.append(reporte_duplicados(df2, subset=subset))
    bloques.append("")

    bloques.append(">>> COMPARACIÓN ENTRE DATASETS")
    bloques.append(
        reporte_comparacion(
            df1, df2,
            name1=name1,
            name2=name2,
            tolerance=tolerance,
            normalize=normalize,
            max_items=max_items,
        )
    )

    return "\n".join(bloques)


def main():
    parser = argparse.ArgumentParser(
        description="Genera reportes de calidad y comparación de dos datasets."
    )
    parser.add_argument("archivo1", help="Ruta al primer dataset (.csv/.xlsx).")
    parser.add_argument("archivo2", help="Ruta al segundo dataset (.csv/.xlsx).")
    parser.add_argument("--name1", default=None, help="Etiqueta del primer dataset.")
    parser.add_argument("--name2", default=None, help="Etiqueta del segundo dataset.")
    parser.add_argument(
        "--tolerance", type=float, default=0.0,
        help="Diferencia mínima para reportar desfase numérico (default 0).",
    )
    parser.add_argument(
        "--no-normalize", action="store_true",
        help="No normalizar texto (acentos/mayúsculas) antes de comparar.",
    )
    parser.add_argument(
        "--max-items", type=int, default=20,
        help="Máximo de items a listar por sección (default 20).",
    )
    parser.add_argument(
        "--salida", default=None,
        help="Si se indica, guarda el reporte en ese archivo además de imprimirlo.",
    )
    args = parser.parse_args()

    df1 = _cargar(args.archivo1)
    df2 = _cargar(args.archivo2)

    # Si no se dan etiquetas, usar el nombre del archivo sin extensión.
    name1 = args.name1 or args.archivo1.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    name2 = args.name2 or args.archivo2.rsplit("/", 1)[-1].rsplit(".", 1)[0]

    reporte = generar_reportes(
        df1, df2,
        name1=name1,
        name2=name2,
        tolerance=args.tolerance,
        normalize=not args.no_normalize,
        max_items=args.max_items,
    )

    print(reporte)

    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as f:
            f.write(reporte)
        print(f"\n[Reporte guardado en: {args.salida}]")


if __name__ == "__main__":
    main()

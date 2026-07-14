"""
Carga y limpieza de las 4 bases de acceso a CREA (Docentes/Estudiantes, 2025/2026).

IMPORTANTE - donde corre esto: este script lo tenés que ejecutar VOS, local,
con tu propio Python (`python limpieza_datos.py`). No lo corre el asistente:
así los datos reales (aunque estén anonimizados) nunca pasan por una
herramienta externa, solo quedan en tu máquina.

Donde quedan los archivos:
    - Originales: en CARPETA_DATOS (tal cual ya los tenías).
    - Limpios: en CARPETA_SALIDA, una subcarpeta DENTRO de la misma carpeta
      de datos, fuera del repo de git. El repo es público -> nunca debe haber
      un dato real bajo control de git (ver .gitignore).

Qué hace, paso a paso (cada paso queda anotado en un log auditable, estilo
"Applied Steps" de Power Query: qué se hizo y cuántas filas afectó):
  1. Carga el .xlsx tal cual.
  2. Valida columnas reales contra el esquema esperado (avisa, no asume).
  3. Convierte Dias4/Dias5/Dias6 a numérico (no numérico -> NaN, reportado).
  4. Calcula dias_totales y accedio (dos métricas de uso candidatas; cuál usar
     para el análisis es decisión tuya, no del script).
  5. Elimina duplicados EXACTOS (idénticos en TODAS las columnas, incluido
     ID_persona) -- son error de carga, se pueden borrar con confianza.
  6. Reporta (sin borrar) filas idénticas en todo MENOS el ID/ID_CENTRO --
     puede ser duplicado real o coincidencia; queda para que decidas vos.
  7. Reporta IvsMedia (dtype + muestra de valores) sin interpretarlo.
  8. Guarda el .xlsx limpio + una hoja "log_limpieza" con el detalle de cada
     paso (son conteos/descripciones, no filas de datos).

Regla dura: ID_persona e ID_CENTRO no se usan para agrupar ni para cruzar
bases entre sí (no son relacionables entre años ni entre docentes/
estudiantes, ver disclaimer del reto).
"""

from pathlib import Path

import pandas as pd

from compare_datasets import reporte_duplicados

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CARPETA_DATOS = Path(r"C:\Users\Matihas\Documents\Facultad\RETO\Datos Ceibal Reto 1 2026")
CARPETA_SALIDA = CARPETA_DATOS / "datos_limpios"  # fuera del repo, a propósito

RUTAS = {
    "docentes_2025": CARPETA_DATOS / "datosUCU2025_doc.xlsx",
    "docentes_2026": CARPETA_DATOS / "datosUCU2026_doc.xlsx",
    "estudiantes_2025": CARPETA_DATOS / "datosUCU2025_estu.xlsx",
    "estudiantes_2026": CARPETA_DATOS / "datosUCU2026_estu.xlsx",
}

COLUMNAS_ESTUDIANTES = [
    "ID_persona", "ID_CENTRO", "Dias6", "Dias5", "Dias4", "Sexo", "Zona",
    "tipo_centro", "Rubro", "dept_nombre", "ciclo", "grado", "grupo",
    "Contexto Sociocultural", "IvsMedia",
]

# Docentes = mismas columnas que estudiantes + "Materia" entre grupo y
# Contexto Sociocultural (estructura confirmada en el enunciado del reto).
COLUMNAS_DOCENTES = (
    COLUMNAS_ESTUDIANTES[:13] + ["Materia"] + COLUMNAS_ESTUDIANTES[13:]
)

ESQUEMAS = {
    "docentes_2025": COLUMNAS_DOCENTES,
    "docentes_2026": COLUMNAS_DOCENTES,
    "estudiantes_2025": COLUMNAS_ESTUDIANTES,
    "estudiantes_2026": COLUMNAS_ESTUDIANTES,
}

DIAS_COLS = ["Dias4", "Dias5", "Dias6"]
ID_COLS = ["ID_persona", "ID_CENTRO"]  # nunca agrupar ni cruzar bases por esto


class Pasos:
    """Registro tipo 'Applied Steps' de Power Query: qué se hizo, cuántas
    filas había antes/después de cada paso. Solo guarda conteos y texto,
    nunca filas de datos."""

    def __init__(self):
        self.registro = []

    def anotar(self, descripcion: str, filas_antes: int, filas_despues: int):
        self.registro.append({
            "paso": len(self.registro) + 1,
            "descripcion": descripcion,
            "filas_antes": filas_antes,
            "filas_despues": filas_despues,
            "filas_afectadas": filas_antes - filas_despues,
        })

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.registro)

    def imprimir(self):
        for p in self.registro:
            print(f"  Paso {p['paso']}: {p['descripcion']} "
                  f"({p['filas_antes']} -> {p['filas_despues']} filas)")


def cargar(nombre: str) -> pd.DataFrame:
    df = pd.read_excel(RUTAS[nombre])
    df.columns = [c.strip() for c in df.columns]
    return df


def validar_esquema(nombre: str, df: pd.DataFrame) -> None:
    esperadas = set(ESQUEMAS[nombre])
    reales = set(df.columns)
    faltan = sorted(esperadas - reales)
    sobran = sorted(reales - esperadas)
    print(f"--- {nombre}: validación de columnas ---")
    print(f"  filas: {len(df)}")
    print(f"  faltan (esperadas y no están): {faltan or '(ninguna)'}")
    print(f"  sobran (no esperadas): {sobran or '(ninguna)'}")


def convertir_dias_a_numerico(nombre: str, df: pd.DataFrame) -> pd.DataFrame:
    for col in DIAS_COLS:
        if col not in df.columns:
            continue
        antes = df[col].copy()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        no_convertidos = antes[df[col].isna() & antes.notna()]
        if len(no_convertidos):
            print(
                f"  [{nombre}] {col}: {len(no_convertidos)} valores no "
                f"numéricos -> NaN. Ejemplos: {list(no_convertidos.unique()[:5])}"
            )
    return df


def agregar_metricas_uso(df: pd.DataFrame) -> pd.DataFrame:
    presentes = [c for c in DIAS_COLS if c in df.columns]
    df["dias_totales"] = df[presentes].sum(axis=1, min_count=1)
    df["accedio"] = df["dias_totales"].fillna(0) > 0
    return df


def revisar_ivsmedia(nombre: str, df: pd.DataFrame) -> None:
    if "IvsMedia" not in df.columns:
        return
    col = df["IvsMedia"]
    print(
        f"  [{nombre}] IvsMedia -> dtype={col.dtype}, nulos={col.isna().sum()}, "
        f"valores únicos (muestra): {list(col.dropna().unique()[:10])}"
    )
    print("  ^ significado sin confirmar todavía: no se usa en ninguna métrica.")


def limpiar_base(nombre: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    pasos = Pasos()

    df = cargar(nombre)
    n0 = len(df)
    pasos.anotar("Carga inicial", n0, n0)

    validar_esquema(nombre, df)

    df = convertir_dias_a_numerico(nombre, df)
    pasos.anotar("Conversión Dias4/Dias5/Dias6 a numérico", n0, len(df))

    df = agregar_metricas_uso(df)
    pasos.anotar("Cálculo de dias_totales y accedio", len(df), len(df))

    n_antes = len(df)
    exactos = df.duplicated(keep="first")
    n_exactos = int(exactos.sum())
    df = df[~exactos].reset_index(drop=True)
    pasos.anotar(f"Eliminación de duplicados EXACTOS ({n_exactos})", n_antes, len(df))

    subset_sin_id = [c for c in df.columns if c not in ID_COLS]
    print(reporte_duplicados(df, subset=subset_sin_id))
    pasos.anotar(
        "Revisión de posibles duplicados sin ID (NO eliminados, ver reporte arriba)",
        len(df), len(df),
    )

    revisar_ivsmedia(nombre, df)

    print(f"  --- log de pasos: {nombre} ---")
    pasos.imprimir()

    return df, pasos.to_dataframe()


def guardar_limpio(nombre: str, df: pd.DataFrame, log: pd.DataFrame) -> Path:
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    ruta_salida = CARPETA_SALIDA / f"{nombre}_limpio.xlsx"
    with pd.ExcelWriter(ruta_salida) as writer:
        df.to_excel(writer, sheet_name="datos", index=False)
        log.to_excel(writer, sheet_name="log_limpieza", index=False)
    print(f"  Guardado: {ruta_salida}")
    return ruta_salida


def main() -> dict:
    resultados = {}
    for nombre in RUTAS:
        df, log = limpiar_base(nombre)
        guardar_limpio(nombre, df, log)
        resultados[nombre] = df
        print()
    return resultados


if __name__ == "__main__":
    datasets = main()

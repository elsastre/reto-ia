# reto-ia

Pipeline y reportes del Reto 1 CREA (Ceibal).

## Estructura

- `estructura.py` — digestión: limpios + persistencia longitudinal por centro
- `compare_datasets_generic.py` — comparación / inconsistencias entre años
- `reportes/` — notebooks (misma altura que `.venv`)
  - `comparacion_inconsistencias.ipynb` — % variables/filas inconsistentes 2025 vs 2026
  - `reporte_fase1.ipynb` — pipeline crudo→limpio→persistente + impacto
  - `analisis_centros.ipynb` — ID_CENTRO entre tipos
  - `hallazgos_estudiantes.ipynb` — exploración de uso
  - `Reportes_exploracion.ipynb` — QA legado
  - `pathsetup.py` — agrega la raíz del repo a `sys.path` (importar al inicio)

Los CSV de datos viven fuera del repo (junto a la carpeta de Downloads / Desktop).

## Uso

```bash
.venv/bin/python estructura.py
```

Abrir notebooks desde `reportes/` (la primera celda hace `import pathsetup`).

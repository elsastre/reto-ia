# Audit — push `newdata` (fase 1 digestión)

| | |
|---|---|
| **Fecha** | 2026-07-15 |
| **Remoto** | `origin/newdata` → `https://github.com/elsastre/reto-ia` |
| **Base previa** | `dd0823d` |

---

## 1. Resumen ejecutivo

Esta entrega cierra la **fase 1 de digestión de datos** y reorganiza el trabajo exploratorio:

1. **Pipeline** (`estructura.py`): limpia las bases y genera datasets **persistentes** (centros presentes en 2025 y 2026).
2. **Inconsistencias** (notebook único): % de variables/valores desfasados entre años y % de filas involucradas.
3. **Notebooks** centralizados en `reportes/` (misma altura que `.venv`), con bootstrap de imports.

**Política:** los agentes operan en modo **copiloto** (`CLAUDE.md` + rule Cursor). No deben acceder a datasets reales. Los notebooks en git van **sin outputs**.

---

## 2. Pipeline — `estructura.py`

### Qué cambió

- Resolución automática de carpeta de datos (prioridad `Datos Ceibal 2025-2026 ver final`, fallback Mac/Windows).
- Salidas fuera del repo, junto a los datos: `processed/` (limpios) y `reportes/` de datos (persistentes + auditoría).
- Persistencia cruzable entre tipos vía `CRUZAR_TIPOS_PERSISTENCIA` (validado conceptualmente en `reportes/analisis_centros.ipynb`).

### Funciones nuevas / etapa de persistencia

| Función | Rol |
|---|---|
| `filtrar_persistencia_centro` | Persistentes vs eliminadas por ID de centro en ambos años |
| `guardar_persistencia` | Escribe CSVs + auditoría |
| `aplicar_persistencia_ambos_tipos` | Docentes y estudiantes |
| `_fila_impacto` | Métricas de impacto |

**`main()`:** (1) limpieza → `*_clean.csv` (2) persistencia → `*_persistente.csv` + auditoría.  
`colapsar_docentes` / `panel` disponibles pero no se ejecutan por defecto.

Artefactos de datos quedan **fuera del git** (carpeta de datos local).

---

## 3. `compare_datasets_generic.py`

Ampliado con centros/persistencia y métricas de inconsistencia:

- `pct_desfasajes_categorias`, `pct_combinaciones_cantidad`, `tops_desfasajes`
- `informe_centros_relacionados`
- helpers de centros: `centros_presentes_en_ambos`, `separar_por_persistencia_centro`, etc.

---

## 4. Notebooks — `reportes/` (repo)

| Notebook | Rol |
|---|---|
| `comparacion_inconsistencias.ipynb` | QA 2025 vs 2026 (ambos tipos) |
| `reporte_digestion_fase1.ipynb` | Impacto del filtro de persistencia |
| `analisis_centros.ipynb` | ID_CENTRO entre tipos |
| `hallazgos_estudiantes.ipynb` | Exploración de uso |
| `Reportes_exploracion.ipynb` | QA legado |
| `pathsetup.py` | Raíz del repo en `sys.path` |

### Eliminados

`comparacion_docentes.ipynb`, `comparacion_estudiantes.ipynb`, `comparacion_docentes_limpio.ipynb` → reemplazados por los notebooks de arriba + `estructura.py`.

Antes de commit: notebooks **sin** `outputs` ni `execution_count`.

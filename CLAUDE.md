# CLAUDE.md — modo copiloto (sin acceso a datos)

Fecha de política: **2026-07-15**.

Los agentes (Cursor, Claude, etc.) trabajan **solo como copiloto de código**.
No deben leer, ejecutar ni inspeccionar datasets reales del Ceibal.

## Prohibido

- Leer o abrir archivos bajo carpetas de datos reales, p. ej.:
  - `**/Datos Ceibal*/**`
  - `~/Downloads/Datos Ceibal*`
  - `C:\Users\*\**\Datos Ceibal*`
  - cualquier `processed/`, `reportes/` **junto a los datos** (fuera de este repo)
- Ejecutar `python estructura.py` / `main()` del pipeline contra datos reales
- Ejecutar notebooks de `reportes/` de forma que carguen xlsx/csv reales
- Imprimir, loguear o commitear muestras de filas, `ID_persona`, `ID_CENTRO_*`, etc.
- Guardar outputs de notebooks en git (siempre *Clear Outputs* antes de commit)

## Permitido (copiloto)

- Editar `.py`, `.md`, notebooks **como código/markdown** (sin correrlos contra datos)
- Refactorizar APIs, tests con fixtures sintéticos, documentación
- Proponer comandos para que un humano los corra en su máquina
- Usar rutas vía `Path.home()` / `CANDIDATOS_DATOS` en código **sin resolverlas ni listar el filesystem de datos**

## Si hace falta probar lógica

Usar DataFrames sintéticos mínimos en memoria o fixtures bajo algo como `tests/fixtures/` (datos inventados, N chico). Nunca copiar extractos de la base real al repo.

## Notebooks

Viven en `reportes/` del **repo**. La primera celda hace `import pathsetup`.
Antes de commit: sin `outputs`, sin `execution_count`, sin paths absolutos de usuario.

## Commits

No incluir `.idea/`, CSV/XLSX reales, ni notebooks con salidas ejecutadas.

# DOCUMENTACION.md — registro para agentes

Archivo destinado EXCLUSIVAMENTE a agentes (no a humanos). Es un log append-only del estado del proyecto: qué se hizo y cuándo. Ante cada cambio de estado de Git, agregá una entrada al final con el formato de abajo. No reescribas ni borres entradas viejas.

## Formato de entrada

## AAAA-MM-DD — <título corto>
- Qué se hizo: <resumen en 1-2 líneas>
- Archivos: <archivos tocados>
- Commit: <hash corto, o "pendiente">
- Notas: <supuestos, pendientes o limitaciones; opcional>

---

## 2026-07-14 — Regla de documentación para agentes
- Qué se hizo: se agregó a AGENTS.md/CLAUDE.md la regla de mantener este DOCUMENTACION.md; se creó este archivo con su formato; se agregó la skill visualize-data.
- Archivos: AGENTS.md, CLAUDE.md, DOCUMENTACION.md, skills/visualize-data.md
- Commit: be5c054 (creación) + este commit que completa el registro
- Notas: leído solo por agentes; log append-only. Un commit no puede contener su propio hash, por eso el registro se completa en el commit siguiente.

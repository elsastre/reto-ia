"""
Visualizaciones - Estudiantes 2025 vs 2026 (Reto 1)
===================================================
Lee las salidas del pipeline (parquet) y guarda PNGs en ./visuales/.
Todo es AGREGADO. Se suprimen grupos con menos de MIN_N personas (privacidad + ruido).

Requiere: pandas, matplotlib, pyarrow.  Correr en la carpeta donde estan los parquet.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ======================================================================
# CONFIG
# ======================================================================
CARPETA = Path(r"C:\Users\Matihas\Desktop\Datos Ceibal 2025-2026\processed")                 # carpeta con los .parquet del pipeline
VISUALES = CARPETA / "visuales"
MIN_N = 10                          # DECISION: umbral minimo por grupo
C25, C26 = "#4C72B0", "#DD8452"     # colores 2025 / 2026

plt.rcParams.update({"figure.dpi": 120, "axes.grid": True,
                     "grid.alpha": .3, "axes.axisbelow": True})


def guardar(fig, nombre):
    ruta = VISUALES / nombre
    fig.tight_layout()
    fig.savefig(ruta, bbox_inches="tight")
    plt.close(fig)
    print("  guardado:", ruta)


def cargar():
    e25 = pd.read_parquet(CARPETA / "estudiantes_2025_clean.parquet")
    e26 = pd.read_parquet(CARPETA / "estudiantes_2026_clean.parquet")
    panel = pd.read_parquet(CARPETA / "panel_estudiantes.parquet")
    print(f"cargado: 2025={len(e25)} filas, 2026={len(e26)} filas, panel={len(panel)}")
    return e25, e26, panel


# ======================================================================
# 1) Matricula vs Acceso (conteos)
# ======================================================================
def fig_matricula_acceso(e25, e26):
    fig, ax = plt.subplots(figsize=(6, 4))
    cats = ["Matriculados\n(filas)", "Accedieron\n(dias>0)"]
    v25 = [len(e25), int(e25["accedio"].sum())]
    v26 = [len(e26), int(e26["accedio"].sum())]
    x = np.arange(len(cats)); w = .38
    ax.bar(x - w/2, v25, w, label="2025", color=C25)
    ax.bar(x + w/2, v26, w, label="2026", color=C26)
    for i, (a, b) in enumerate(zip(v25, v26)):
        ax.text(i - w/2, a, f"{a:,}", ha="center", va="bottom", fontsize=8)
        ax.text(i + w/2, b, f"{b:,}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(cats)
    ax.set_ylabel("Estudiantes"); ax.legend()
    ax.set_title("Matricula vs Acceso — Estudiantes")
    guardar(fig, "01_matricula_vs_acceso.png")


# ======================================================================
# 2) Tasa de acceso (%) por anio
# ======================================================================
def fig_tasa_acceso(e25, e26):
    fig, ax = plt.subplots(figsize=(4.5, 4))
    t = [100*e25["accedio"].mean(), 100*e26["accedio"].mean()]
    ax.bar(["2025", "2026"], t, color=[C25, C26])
    for i, v in enumerate(t):
        ax.text(i, v, f"{v:.1f}%", ha="center", va="bottom")
    ax.set_ylabel("% que accedio al menos 1 dia")
    ax.set_title("Tasa de acceso")
    guardar(fig, "02_tasa_acceso.png")


# ======================================================================
# 3) Distribucion de dias_totales
# ======================================================================
def fig_dist_dias(e25, e26):
    fig, ax = plt.subplots(figsize=(6.5, 4))
    bins = np.arange(0, e25["dias_totales"].max() + 5, 3)
    ax.hist(e25["dias_totales"].dropna(), bins=bins, alpha=.55, label="2025",
            color=C25, density=True)
    ax.hist(e26["dias_totales"].dropna(), bins=bins, alpha=.55, label="2026",
            color=C26, density=True)
    ax.set_xlabel("dias_totales (abr+may+jun)"); ax.set_ylabel("densidad")
    ax.legend(); ax.set_title("Distribucion de dias de acceso")
    guardar(fig, "03_distribucion_dias.png")


# ======================================================================
# 4) Composicion del panel (retencion)
# ======================================================================
def fig_panel_estados(panel):
    fig, ax = plt.subplots(figsize=(5, 4))
    orden = ["solo_2025", "ambos", "solo_2026"]
    vc = panel["estado"].value_counts().reindex(orden).fillna(0)
    ax.bar(["Solo 2025\n(se fue)", "Ambos\n(retenido)", "Solo 2026\n(nuevo)"],
           vc.values, color=["#C44E52", "#55A868", "#8172B3"])
    for i, v in enumerate(vc.values):
        ax.text(i, v, f"{int(v):,}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Estudiantes")
    ax.set_title("Panel longitudinal por estudiante")
    guardar(fig, "04_panel_estados.png")


# ======================================================================
# 5) Tasa de acceso por grupo (vuln_q, Rubro) — con supresion MIN_N
# ======================================================================
def fig_tasa_por(e25, e26, col, nombre, archivo):
    a = e25.groupby(col)["accedio"].agg(["mean", "size"])
    b = e26.groupby(col)["accedio"].agg(["mean", "size"])
    a = a[a["size"] >= MIN_N]; b = b[b["size"] >= MIN_N]
    idx = sorted(set(a.index) & set(b.index), key=lambda x: str(x))
    if not idx:
        print(f"  (sin grupos suficientes para {nombre})"); return
    x = np.arange(len(idx)); w = .38
    fig, ax = plt.subplots(figsize=(max(5, len(idx)*1.1), 4))
    ax.bar(x - w/2, [100*a.loc[i, "mean"] for i in idx], w, label="2025", color=C25)
    ax.bar(x + w/2, [100*b.loc[i, "mean"] for i in idx], w, label="2026", color=C26)
    ax.set_xticks(x); ax.set_xticklabels([str(i) for i in idx], rotation=0)
    ax.set_ylabel("% acceso"); ax.set_xlabel(nombre); ax.legend()
    ax.set_title(f"Tasa de acceso por {nombre}")
    guardar(fig, archivo)


# ======================================================================
# 6) Matriz de retencion de acceso (solo 'ambos')
# ======================================================================
def fig_transicion(panel):
    amb = panel[panel["estado"] == "ambos"]
    if not {"accedio_25", "accedio_26"}.issubset(amb.columns):
        print("  (faltan accedio_25/26 en panel)"); return
    ct = pd.crosstab(amb["accedio_25"], amb["accedio_26"], normalize=True) * 100
    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(ct.values, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["no accede 26", "accede 26"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["no accede 25", "accede 25"])
    for i in range(ct.shape[0]):
        for j in range(ct.shape[1]):
            ax.text(j, i, f"{ct.values[i, j]:.1f}%", ha="center", va="center")
    ax.set_title("Retencion de acceso (mismos estudiantes)")
    fig.colorbar(im, ax=ax, fraction=.046, label="% del total 'ambos'")
    guardar(fig, "06_retencion_acceso.png")


# ======================================================================
def main():
    print("generando visuales...")
    VISUALES.mkdir(parents=True, exist_ok=True)
    e25, e26, panel = cargar()
    fig_matricula_acceso(e25, e26)
    fig_tasa_acceso(e25, e26)
    fig_dist_dias(e25, e26)
    fig_panel_estados(panel)
    fig_tasa_por(e25, e26, "vuln_q", "quintil de vulnerabilidad", "05a_acceso_por_vuln.png")
    fig_tasa_por(e25, e26, "Rubro", "Rubro (subsistema)", "05b_acceso_por_rubro.png")
    fig_transicion(panel)
    print("listo ->", VISUALES.resolve())


if __name__ == "__main__":
    main()
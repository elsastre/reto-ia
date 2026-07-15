"""Bootstrap: agrega la raíz del repo a sys.path.

Los notebooks viven en reportes/; los módulos (estructura, compare_datasets_generic,
etc.) están en la raíz, al lado de .venv. Importar esto al inicio de cada notebook:

    import pathsetup  # noqa: F401
    # o: from pathsetup import ROOT
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

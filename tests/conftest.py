import sys
from pathlib import Path

# Permite rodar `pytest` sem instalar o pacote (`pip install -e .` também funciona).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

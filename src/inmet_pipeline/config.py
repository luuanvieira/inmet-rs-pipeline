"""Configuração central do pipeline, lida de variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    url_base: str
    pasta_raw: Path
    caminho_db: Path
    uf: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            url_base=os.getenv(
                "INMET_URL_BASE",
                "https://portal.inmet.gov.br/uploads/dadoshistoricos",
            ).rstrip("/"),
            pasta_raw=Path(os.getenv("INMET_RAW_DIR", RAIZ_PROJETO / "data" / "raw")),
            caminho_db=Path(
                os.getenv("INMET_DB_PATH", RAIZ_PROJETO / "data" / "warehouse" / "inmet.duckdb")
            ),
            uf=os.getenv("INMET_UF", "RS").upper(),
        )

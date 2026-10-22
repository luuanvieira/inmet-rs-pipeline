"""Localiza os CSVs de uma UF dentro dos ZIPs anuais ou de uma pasta local."""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath


def _eh_csv_da_uf(nome_arquivo: str, uf: str) -> bool:
    # Padrão dos nomes: INMET_S_RS_A801_PORTO ALEGRE_01-01-2023_A_31-12-2023.CSV
    base = PurePosixPath(nome_arquivo).name.upper()
    return base.endswith(".CSV") and f"_{uf.upper()}_" in base


def csvs_do_zip(caminho_zip: Path, uf: str) -> Iterator[tuple[str, bytes]]:
    """Lê os CSVs da UF direto do ZIP, sem extrair o arquivo inteiro para o disco."""
    with zipfile.ZipFile(caminho_zip) as zf:
        for nome in sorted(zf.namelist()):
            if _eh_csv_da_uf(nome, uf):
                yield f"{caminho_zip.name}/{PurePosixPath(nome).name}", zf.read(nome)


def csvs_da_pasta(pasta: Path, uf: str) -> Iterator[tuple[str, bytes]]:
    """Lê CSVs soltos de uma pasta (usado pelos dados de exemplo e pela CI)."""
    for caminho in sorted(pasta.rglob("*")):
        if caminho.is_file() and _eh_csv_da_uf(caminho.name, uf):
            yield caminho.name, caminho.read_bytes()

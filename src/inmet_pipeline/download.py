"""Download dos arquivos anuais do portal de dados históricos do INMET."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import requests

log = logging.getLogger(__name__)

TAMANHO_BLOCO = 1024 * 1024  # 1 MiB
TIMEOUT_S = 60


def zip_valido(caminho: Path) -> bool:
    """Retorna True se o arquivo existe e é um ZIP íntegro."""
    if not caminho.exists():
        return False
    try:
        with zipfile.ZipFile(caminho) as zf:
            return zf.testzip() is None
    except zipfile.BadZipFile:
        return False


def baixar_ano(ano: int, url_base: str, pasta_destino: Path, forcar: bool = False) -> Path:
    """Baixa o ZIP de um ano para `pasta_destino`.

    O download é idempotente: se o arquivo já existe e está íntegro, nada é feito.
    O conteúdo é gravado primeiro em um `.part` e só é renomeado no final, para que
    uma interrupção nunca deixe um ZIP pela metade com o nome definitivo.
    """
    pasta_destino.mkdir(parents=True, exist_ok=True)
    destino = pasta_destino / f"{ano}.zip"

    if not forcar and zip_valido(destino):
        log.info("ano %s já baixado (%s), pulando", ano, destino)
        return destino

    url = f"{url_base}/{ano}.zip"
    parcial = destino.with_suffix(".zip.part")
    log.info("baixando %s", url)

    with requests.get(
        url,
        stream=True,
        timeout=TIMEOUT_S,
        headers={"User-Agent": "inmet-rs-pipeline/0.1 (projeto de estudo)"},
    ) as resp:
        resp.raise_for_status()
        with parcial.open("wb") as f:
            for bloco in resp.iter_content(chunk_size=TAMANHO_BLOCO):
                f.write(bloco)

    if not zip_valido(parcial):
        parcial.unlink(missing_ok=True)
        raise RuntimeError(f"o arquivo baixado de {url} não é um ZIP válido")

    parcial.replace(destino)
    log.info("ano %s salvo em %s (%.1f MB)", ano, destino, destino.stat().st_size / 1e6)
    return destino

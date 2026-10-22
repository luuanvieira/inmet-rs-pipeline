"""Linha de comando do pipeline.

Exemplos:
    python -m inmet_pipeline baixar --anos 2023 2024
    python -m inmet_pipeline ingerir --anos 2023 2024
    python -m inmet_pipeline executar --anos 2020 2021 2022 2023 2024
    python -m inmet_pipeline ingerir --pasta tests/fixtures   # dados de exemplo
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import requests

from .config import Config
from .download import baixar_ano
from .fontes import csvs_da_pasta, csvs_do_zip
from .parser import ErroFormatoINMET, ler_csv_inmet

log = logging.getLogger("inmet_pipeline")


def _fontes(cfg: Config, anos: Iterable[int] | None, pasta: Path | None) -> Iterator[tuple[str, bytes]]:
    if pasta is not None:
        yield from csvs_da_pasta(pasta, cfg.uf)
        return
    for ano in anos or []:
        caminho = cfg.pasta_raw / f"{ano}.zip"
        if not caminho.exists():
            raise FileNotFoundError(f"{caminho} não existe; rode `baixar --anos {ano}` antes")
        yield from csvs_do_zip(caminho, cfg.uf)


def ingerir(cfg: Config, anos: Iterable[int] | None = None, pasta: Path | None = None) -> int:
    # Import tardio: `baixar` funciona mesmo sem o DuckDB instalado.
    from .carga import carregar_arquivo, conectar

    con = conectar(cfg.caminho_db)
    arquivos = linhas = falhas = 0
    try:
        for nome, conteudo in _fontes(cfg, anos, pasta):
            try:
                dados = ler_csv_inmet(conteudo)
            except ErroFormatoINMET as exc:
                falhas += 1
                log.warning("ignorando %s: %s", nome, exc)
                continue
            n = carregar_arquivo(con, nome, dados)
            arquivos += 1
            linhas += n
            log.info("%-70s %7d linhas", nome, n)
    finally:
        con.close()

    log.info("ingestão concluída: %d arquivos, %d linhas, %d falhas", arquivos, linhas, falhas)
    if arquivos == 0:
        log.error("nenhum arquivo da UF %s foi carregado", cfg.uf)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inmet_pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_baixar = sub.add_parser("baixar", help="baixa os ZIPs anuais do INMET")
    p_baixar.add_argument("--anos", type=int, nargs="+", required=True)
    p_baixar.add_argument("--forcar", action="store_true", help="baixa de novo mesmo se já existir")

    p_ingerir = sub.add_parser("ingerir", help="carrega os CSVs na camada bronze")
    origem = p_ingerir.add_mutually_exclusive_group(required=True)
    origem.add_argument("--anos", type=int, nargs="+")
    origem.add_argument("--pasta", type=Path, help="pasta com CSVs soltos")

    p_exec = sub.add_parser("executar", help="baixar + ingerir")
    p_exec.add_argument("--anos", type=int, nargs="+", required=True)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    cfg = Config.from_env()

    try:
        if args.comando in ("baixar", "executar"):
            for ano in args.anos:
                baixar_ano(ano, cfg.url_base, cfg.pasta_raw, forcar=getattr(args, "forcar", False))
            if args.comando == "baixar":
                return 0
            return ingerir(cfg, anos=args.anos)
        return ingerir(cfg, anos=args.anos, pasta=args.pasta)
    except (requests.RequestException, RuntimeError, FileNotFoundError) as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""Carga da camada bronze no DuckDB.

A carga é idempotente por arquivo de origem: reprocessar o mesmo CSV apaga as
linhas que ele gerou antes e insere de novo, dentro de uma única transação.
Assim, rodar o pipeline duas vezes nunca duplica dados.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from .parser import COLUNAS_MEDIDAS, ArquivoINMET

log = logging.getLogger(__name__)

DDL = f"""
create schema if not exists bronze;

create table if not exists bronze.estacoes (
    codigo_estacao varchar primary key,
    nome           varchar,
    uf             varchar,
    regiao         varchar,
    latitude       double,
    longitude      double,
    altitude_m     double,
    data_fundacao  varchar,
    arquivo_origem varchar,
    carregado_em   timestamp
);

create table if not exists bronze.observacoes_horarias (
    codigo_estacao varchar not null,
    ts_utc         timestamp not null,
    {", ".join(f"{c} double" for c in COLUNAS_MEDIDAS)},
    arquivo_origem varchar not null,
    carregado_em   timestamp not null
);

create table if not exists bronze.ingestoes (
    arquivo_origem varchar primary key,
    codigo_estacao varchar,
    linhas         integer,
    carregado_em   timestamp
);
"""


def conectar(caminho_db: Path) -> duckdb.DuckDBPyConnection:
    caminho_db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(caminho_db))
    con.execute(DDL)
    return con


def carregar_arquivo(
    con: duckdb.DuckDBPyConnection, arquivo_origem: str, dados: ArquivoINMET
) -> int:
    """Grava estação + observações de um arquivo. Retorna o número de linhas."""
    obs = dados.observacoes.copy()
    obs["arquivo_origem"] = arquivo_origem
    for coluna in COLUNAS_MEDIDAS:
        obs[coluna] = obs[coluna].astype("float64")  # Float64 (nullable) -> NaN -> NULL
    estacao = pd.DataFrame([{**dados.estacao, "arquivo_origem": arquivo_origem}])
    colunas_obs = ", ".join(["codigo_estacao", "ts_utc", *COLUNAS_MEDIDAS, "arquivo_origem"])
    # NaN do pandas vira NULL de forma explícita, sem depender do comportamento do driver.
    select_obs = ", ".join(
        [
            "codigo_estacao",
            "ts_utc",
            *(f"case when isnan({c}) then null else {c} end" for c in COLUNAS_MEDIDAS),
            "arquivo_origem",
        ]
    )

    con.execute("begin transaction")
    try:
        con.register("obs_df", obs)
        con.register("estacao_df", estacao)

        con.execute(
            "delete from bronze.observacoes_horarias where arquivo_origem = ?", [arquivo_origem]
        )
        con.execute(
            f"""
            insert into bronze.observacoes_horarias ({colunas_obs}, carregado_em)
            select {select_obs}, now() from obs_df
            """
        )
        con.execute(
            """
            insert or replace into bronze.estacoes
            select codigo_estacao, nome, uf, regiao, latitude, longitude, altitude_m,
                   data_fundacao, arquivo_origem, now()
            from estacao_df
            """
        )
        con.execute(
            "insert or replace into bronze.ingestoes values (?, ?, ?, now())",
            [arquivo_origem, dados.estacao["codigo_estacao"], len(obs)],
        )
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    finally:
        con.unregister("obs_df")
        con.unregister("estacao_df")

    return len(obs)

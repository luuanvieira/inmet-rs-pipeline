from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from inmet_pipeline.carga import carregar_arquivo, conectar  # noqa: E402
from inmet_pipeline.parser import ler_csv_inmet  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
PORTO_ALEGRE = FIXTURES / "INMET_S_RS_A801_PORTO ALEGRE_01-01-2024_A_31-12-2024.CSV"


def test_carga_e_idempotente(tmp_path):
    con = conectar(tmp_path / "teste.duckdb")
    dados = ler_csv_inmet(PORTO_ALEGRE.read_bytes())

    carregar_arquivo(con, PORTO_ALEGRE.name, dados)
    carregar_arquivo(con, PORTO_ALEGRE.name, dados)  # reprocessar não pode duplicar

    total = con.execute("select count(*) from bronze.observacoes_horarias").fetchone()[0]
    estacoes = con.execute("select count(*) from bronze.estacoes").fetchone()[0]
    assert total == 12 * 24
    assert estacoes == 1


def test_valores_ausentes_chegam_como_null(tmp_path):
    con = conectar(tmp_path / "teste.duckdb")
    carregar_arquivo(con, PORTO_ALEGRE.name, ler_csv_inmet(PORTO_ALEGRE.read_bytes()))

    nulos, nans = con.execute(
        """
        select count(*) filter (where precipitacao_mm is null),
               count(*) filter (where isnan(precipitacao_mm))
        from bronze.observacoes_horarias
        """
    ).fetchone()
    assert nulos > 0
    assert nans == 0

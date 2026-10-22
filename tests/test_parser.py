from pathlib import Path

import pandas as pd

from inmet_pipeline.parser import ErroFormatoINMET, ler_csv_inmet, normalizar, para_numero

FIXTURES = Path(__file__).parent / "fixtures"
PORTO_ALEGRE = FIXTURES / "INMET_S_RS_A801_PORTO ALEGRE_01-01-2024_A_31-12-2024.CSV"
SANTA_MARIA = FIXTURES / "INMET_S_RS_A803_SANTA MARIA_01-01-2018_A_31-12-2018.CSV"

CABECALHO_MINIMO = (
    "REGIAO:;S\nUF:;RS\nESTACAO:;TESTE\nCODIGO (WMO):;A999\n"
    "LATITUDE:;-30,0\nLONGITUDE:;-51,0\nALTITUDE:;10\nDATA DE FUNDACAO:;01/01/00\n"
    "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
    "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);UMIDADE RELATIVA DO AR, HORARIA (%);\n"
)


def test_normalizar_remove_acentos_e_espacos():
    assert normalizar("  Precipitação   total ") == "PRECIPITACAO TOTAL"


def test_para_numero_trata_formatos_do_inmet():
    assert para_numero("12,4") == 12.4
    assert para_numero(",2") == 0.2
    assert para_numero("-3,5") == -3.5
    assert para_numero("-9999") is None
    assert para_numero("") is None
    assert para_numero("abc") is None


def test_formato_novo_metadados():
    arquivo = ler_csv_inmet(PORTO_ALEGRE.read_bytes())
    assert arquivo.estacao["codigo_estacao"] == "A801"
    assert arquivo.estacao["nome"] == "PORTO ALEGRE"
    assert arquivo.estacao["uf"] == "RS"
    assert arquivo.estacao["latitude"] == -30.05361111
    assert arquivo.estacao["altitude_m"] == 46.97


def test_formato_novo_observacoes():
    obs = ler_csv_inmet(PORTO_ALEGRE.read_bytes()).observacoes
    assert len(obs) == 12 * 24
    assert obs["ts_utc"].iloc[0] == pd.Timestamp("2024-04-25 03:00")
    assert obs["ts_utc"].is_unique
    assert obs["temperatura_c"].notna().all()


def test_formato_antigo_le_data_com_hifen_e_hora_com_dois_pontos():
    arquivo = ler_csv_inmet(SANTA_MARIA.read_bytes())
    assert arquivo.estacao["codigo_estacao"] == "A803"
    assert arquivo.estacao["data_fundacao"] == "2001-12-04"
    assert arquivo.observacoes["ts_utc"].iloc[1] == pd.Timestamp("2018-04-25 04:00")


def test_valor_ausente_vira_nulo():
    csv = CABECALHO_MINIMO + "2024/01/01;0000 UTC;-9999;20,5;;\n"
    obs = ler_csv_inmet(csv).observacoes
    assert pd.isna(obs.loc[0, "precipitacao_mm"])
    assert obs.loc[0, "temperatura_c"] == 20.5
    assert pd.isna(obs.loc[0, "umidade_pct"])


def test_colunas_que_nao_existem_no_arquivo_ficam_nulas():
    csv = CABECALHO_MINIMO + "2024/01/01;1300 UTC;,2;25,0;60;\n"
    obs = ler_csv_inmet(csv).observacoes
    assert obs.loc[0, "precipitacao_mm"] == 0.2
    assert obs["vento_rajada_ms"].isna().all()
    assert obs.loc[0, "ts_utc"] == pd.Timestamp("2024-01-01 13:00")


def test_data_no_formato_dia_mes_ano():
    csv = CABECALHO_MINIMO + "31/12/2023;2300 UTC;0;22,0;70;\n"
    obs = ler_csv_inmet(csv).observacoes
    assert obs.loc[0, "ts_utc"] == pd.Timestamp("2023-12-31 23:00")


def test_arquivo_sem_observacoes():
    obs = ler_csv_inmet(CABECALHO_MINIMO).observacoes
    assert obs.empty
    assert "ts_utc" in obs.columns


def test_arquivo_sem_cabecalho_de_tabela_gera_erro():
    try:
        ler_csv_inmet("REGIAO:;S\nUF:;RS\n")
    except ErroFormatoINMET:
        return
    raise AssertionError("deveria ter levantado ErroFormatoINMET")

"""Leitura dos CSVs de estações automáticas do INMET.

Cada CSV tem um cabeçalho de metadados (8 linhas no formato `CHAVE:;VALOR`)
seguido da tabela de observações horárias, separada por `;`, com vírgula
decimal e `-9999` (ou vazio) para dados ausentes.

O formato mudou ao longo dos anos (nomes de coluna, formato de data e hora,
encoding, `;` sobrando no fim da linha). Por isso as colunas são identificadas
por palavras-chave normalizadas, e não pelo texto exato do cabeçalho.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

VALOR_AUSENTE = -9999.0

# (coluna de destino, trechos que precisam aparecer no cabeçalho normalizado)
REGRAS_COLUNAS: list[tuple[str, tuple[str, ...]]] = [
    ("precipitacao_mm", ("PRECIPITACAO",)),
    ("pressao_mb", ("PRESSAO", "NIVEL DA ESTACAO")),
    ("radiacao_kj_m2", ("RADIACAO",)),
    ("temperatura_c", ("BULBO SECO",)),
    ("orvalho_c", ("PONTO DE ORVALHO",)),
    ("temperatura_max_c", ("TEMPERATURA MAXIMA",)),
    ("temperatura_min_c", ("TEMPERATURA MINIMA",)),
    ("umidade_pct", ("UMIDADE RELATIVA DO AR",)),
    ("vento_direcao_graus", ("VENTO", "DIRE")),
    ("vento_rajada_ms", ("RAJADA",)),
    ("vento_velocidade_ms", ("VENTO", "VELOCIDADE")),
]

COLUNAS_MEDIDAS = [destino for destino, _ in REGRAS_COLUNAS]
COLUNAS_SAIDA = ["codigo_estacao", "ts_utc", *COLUNAS_MEDIDAS]

# chave do metadado normalizada -> nome do campo
CHAVES_METADADOS = {
    "REGIAO": "regiao",
    "UF": "uf",
    "ESTACAO": "nome",
    "CODIGO": "codigo_estacao",
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",
    "ALTITUDE": "altitude_m",
    "DATA DE FUNDACAO": "data_fundacao",
}


class ErroFormatoINMET(ValueError):
    """O arquivo não segue o formato esperado de CSV do INMET."""


@dataclass
class ArquivoINMET:
    estacao: dict
    observacoes: pd.DataFrame


def normalizar(texto: str) -> str:
    """Remove acentos, converte para maiúsculas e colapsa espaços."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def decodificar(conteudo: bytes) -> str:
    """Os arquivos antigos vêm em latin-1 e alguns recentes em UTF-8."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return conteudo.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ErroFormatoINMET("não foi possível decodificar o arquivo")  # pragma: no cover


def para_numero(valor: str | None) -> float | None:
    """Converte '12,4', ',2' ou '-9999' em float (ou None para ausente)."""
    if valor is None:
        return None
    texto = valor.strip().replace(",", ".")
    if texto == "":
        return None
    try:
        numero = float(texto)
    except ValueError:
        return None
    return None if numero == VALOR_AUSENTE else numero


def _ler_metadados(linhas: list[str]) -> tuple[dict, int]:
    """Lê o bloco `CHAVE:;VALOR` e retorna (metadados, índice da linha de cabeçalho)."""
    metadados: dict = {}
    for i, linha in enumerate(linhas):
        partes = linha.split(";")
        chave = normalizar(partes[0])
        if chave.startswith("DATA") and not chave.endswith(":") and len(partes) > 3:
            return metadados, i
        chave = chave.rstrip(":").strip()
        valor = partes[1].strip() if len(partes) > 1 else ""
        for prefixo, campo in CHAVES_METADADOS.items():
            if chave.startswith(prefixo):
                metadados[campo] = valor
                break
    raise ErroFormatoINMET("cabeçalho da tabela de observações não encontrado")


def _mapear_colunas(cabecalho: list[str]) -> tuple[int, int, dict[str, int]]:
    normalizado = [normalizar(c) for c in cabecalho]
    idx_data = next((i for i, c in enumerate(normalizado) if c.startswith("DATA")), None)
    idx_hora = next((i for i, c in enumerate(normalizado) if c.startswith("HORA")), None)
    if idx_data is None or idx_hora is None:
        raise ErroFormatoINMET("colunas de data/hora não encontradas")

    medidas: dict[str, int] = {}
    for destino, trechos in REGRAS_COLUNAS:
        for i, coluna in enumerate(normalizado):
            if i in medidas.values():
                continue
            if all(t in coluna for t in trechos):
                medidas[destino] = i
                break
    return idx_data, idx_hora, medidas


def _parse_timestamp(datas: pd.Series, horas: pd.Series) -> pd.Series:
    # Datas aparecem como 2023/01/01, 2018-01-01 ou 01/01/2023 dependendo do ano.
    datas = datas.str.strip().str.replace("-", "/", regex=False)
    dia_primeiro = datas.str.match(r"^\d{2}/\d{2}/\d{4}$")
    data = pd.to_datetime(datas.where(~dia_primeiro), format="%Y/%m/%d", errors="coerce")
    data = data.fillna(pd.to_datetime(datas.where(dia_primeiro), format="%d/%m/%Y", errors="coerce"))

    # Horas aparecem como "0000 UTC", "00:00" ou "0".
    digitos = horas.str.replace(r"\D", "", regex=True).str.zfill(4)
    hora = pd.to_numeric(digitos.str[:2], errors="coerce")
    minuto = pd.to_numeric(digitos.str[2:4], errors="coerce")
    return data + pd.to_timedelta(hora, unit="h") + pd.to_timedelta(minuto, unit="m")


def ler_csv_inmet(conteudo: bytes | str) -> ArquivoINMET:
    """Converte o conteúdo bruto de um CSV do INMET em metadados + observações tipadas."""
    texto = decodificar(conteudo) if isinstance(conteudo, bytes) else conteudo
    linhas = texto.splitlines()
    metadados, idx_cabecalho = _ler_metadados(linhas)

    codigo = metadados.get("codigo_estacao", "").strip().upper()
    if not codigo:
        raise ErroFormatoINMET("código da estação ausente no cabeçalho")

    estacao = {
        "codigo_estacao": codigo,
        "nome": metadados.get("nome", "").strip(),
        "uf": metadados.get("uf", "").strip().upper(),
        "regiao": metadados.get("regiao", "").strip().upper(),
        "latitude": para_numero(metadados.get("latitude")),
        "longitude": para_numero(metadados.get("longitude")),
        "altitude_m": para_numero(metadados.get("altitude_m")),
        "data_fundacao": metadados.get("data_fundacao", "").strip() or None,
    }

    leitor = csv.reader(io.StringIO("\n".join(linhas[idx_cabecalho:])), delimiter=";")
    cabecalho = next(leitor)
    idx_data, idx_hora, medidas = _mapear_colunas(cabecalho)
    registros = [r for r in leitor if len(r) > max(idx_data, idx_hora) and r[idx_data].strip()]

    if not registros:
        vazio = pd.DataFrame(columns=COLUNAS_SAIDA)
        vazio["ts_utc"] = pd.to_datetime(vazio["ts_utc"])
        return ArquivoINMET(estacao=estacao, observacoes=vazio)

    bruto = pd.DataFrame(registros)
    obs = pd.DataFrame({"codigo_estacao": codigo}, index=bruto.index)
    obs["ts_utc"] = _parse_timestamp(bruto[idx_data].astype(str), bruto[idx_hora].astype(str))

    for coluna in COLUNAS_MEDIDAS:
        if coluna in medidas:
            serie = bruto[medidas[coluna]].astype(str).str.strip().str.replace(",", ".", regex=False)
            valores = pd.to_numeric(serie, errors="coerce")
            obs[coluna] = valores.mask(valores == VALOR_AUSENTE)
        else:
            obs[coluna] = pd.NA
        obs[coluna] = obs[coluna].astype("Float64")

    obs = obs.dropna(subset=["ts_utc"]).reset_index(drop=True)
    return ArquivoINMET(estacao=estacao, observacoes=obs[COLUNAS_SAIDA])

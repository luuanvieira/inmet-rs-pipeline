"""Gera CSVs de exemplo no formato do INMET para testes e para a CI.

Os dados são sintéticos (gerados com semente fixa), mas reproduzem as
particularidades dos arquivos reais: cabeçalho de metadados, encoding latin-1,
vírgula decimal (inclusive ",2" sem zero), -9999 para ausente, ";" no fim da
linha e os dois formatos de data/hora (antes e depois de 2019).

Uso:
    python scripts/gerar_dados_exemplo.py tests/fixtures
"""

from __future__ import annotations

import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

COLUNAS = [
    "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)",
    "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB)",
    "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB)",
    "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB)",
    "RADIACAO GLOBAL (Kj/m²)",
    "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)",
    "TEMPERATURA DO PONTO DE ORVALHO (°C)",
    "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)",
    "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)",
    "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C)",
    "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C)",
    "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%)",
    "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%)",
    "UMIDADE RELATIVA DO AR, HORARIA (%)",
    "VENTO, DIREÇÃO HORARIA (gr) (° (gr))",
    "VENTO, RAJADA MAXIMA (m/s)",
    "VENTO, VELOCIDADE HORARIA (m/s)",
]


def fmt(valor: float | None) -> str:
    """Formata no estilo INMET: vírgula decimal e sem o zero à esquerda (",2")."""
    if valor is None:
        return "-9999"
    texto = f"{valor:.1f}".replace(".", ",")
    if texto.startswith("0,"):
        texto = texto[1:]
    elif texto.startswith("-0,"):
        texto = "-" + texto[2:]
    return texto


def chuva_do_dia(dia: datetime, dias_fortes: set[str]) -> float:
    if dia.strftime("%m-%d") in dias_fortes:
        return 6.0  # mm/h em média nesses dias (>100 mm no dia)
    return 0.15


def linhas_observacoes(inicio: datetime, dias: int, rng: random.Random, formato_novo: bool,
                       dias_fortes: set[str], invalidos: set[int]) -> list[str]:
    linhas = []
    for h in range(dias * 24):
        ts = inicio + timedelta(hours=h)
        local = ts - timedelta(hours=3)
        ciclo = math.sin((local.hour - 9) / 24 * 2 * math.pi)
        temp = 19 + 5 * ciclo + rng.uniform(-1, 1)
        chuva = max(0.0, rng.expovariate(1 / chuva_do_dia(local, dias_fortes)) - 0.05)
        umid = min(100.0, 75 - 15 * ciclo + chuva * 2 + rng.uniform(-3, 3))
        valores: list[float | None] = [
            round(chuva, 1),
            round(1012 + rng.uniform(-4, 4), 1),
            round(1013 + rng.uniform(-4, 4), 1),
            round(1011 + rng.uniform(-4, 4), 1),
            max(0.0, round(2500 * ciclo + rng.uniform(-50, 50), 1)) if ciclo > 0 else None,
            round(temp, 1),
            round(temp - 3, 1),
            round(temp + 0.6, 1),
            round(temp - 0.6, 1),
            round(temp - 2.5, 1),
            round(temp - 3.5, 1),
            round(min(100, umid + 3), 1),
            round(umid - 3, 1),
            round(umid, 1),
            float(rng.randrange(0, 360)),
            round(3 + rng.uniform(0, 6), 1),
            round(1 + rng.uniform(0, 3), 1),
        ]
        if h in invalidos:
            valores[5] = 99.9  # leitura de sensor com defeito, deve ser descartada no silver
        if h % 37 == 5:
            valores[0] = None  # falha pontual do pluviômetro
        if formato_novo:
            data, hora = ts.strftime("%Y/%m/%d"), ts.strftime("%H%M UTC")
        else:
            data, hora = ts.strftime("%Y-%m-%d"), ts.strftime("%H:%M")
        linhas.append(";".join([data, hora, *(fmt(v) for v in valores)]) + ";")
    return linhas


def escrever(pasta: Path, nome_arquivo: str, metadados: list[tuple[str, str]],
             cabecalho_data: tuple[str, str], linhas: list[str]) -> None:
    conteudo = [f"{k};{v}" for k, v in metadados]
    conteudo.append(";".join([*cabecalho_data, *COLUNAS]) + ";")
    conteudo.extend(linhas)
    (pasta / nome_arquivo).write_bytes(("\r\n".join(conteudo) + "\r\n").encode("latin-1"))


def main(destino: str) -> None:
    pasta = Path(destino)
    pasta.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    # Formato novo (2019+): Porto Alegre, com o período das enchentes de maio/2024.
    escrever(
        pasta,
        "INMET_S_RS_A801_PORTO ALEGRE_01-01-2024_A_31-12-2024.CSV",
        [("REGIAO:", "S"), ("UF:", "RS"), ("ESTACAO:", "PORTO ALEGRE"),
         ("CODIGO (WMO):", "A801"), ("LATITUDE:", "-30,05361111"),
         ("LONGITUDE:", "-51,17472221"), ("ALTITUDE:", "46,97"),
         ("DATA DE FUNDACAO:", "22/09/00")],
        ("Data", "Hora UTC"),
        linhas_observacoes(datetime(2024, 4, 25, 3), 12, rng, True,
                           dias_fortes={"04-30", "05-01", "05-02"}, invalidos={50}),
    )

    # Formato antigo (até 2018): Santa Maria.
    escrever(
        pasta,
        "INMET_S_RS_A803_SANTA MARIA_01-01-2018_A_31-12-2018.CSV",
        [("REGIAO:", "S"), ("UF:", "RS"), ("ESTACAO:", "SANTA MARIA"),
         ("CODIGO (WMO):", "A803"), ("LATITUDE:", "-29,72499999"),
         ("LONGITUDE:", "-53,72055555"), ("ALTITUDE:", "103,1"),
         ("DATA DE FUNDAÇÃO (YYYY-MM-DD):", "2001-12-04")],
        ("DATA (YYYY-MM-DD)", "HORA (UTC)"),
        linhas_observacoes(datetime(2018, 4, 25, 3), 12, rng, False,
                           dias_fortes={"05-01"}, invalidos=set()),
    )

    # Outra UF, para garantir que o filtro por estado funciona.
    escrever(
        pasta,
        "INMET_S_SC_A806_FLORIANOPOLIS_01-01-2024_A_31-12-2024.CSV",
        [("REGIAO:", "S"), ("UF:", "SC"), ("ESTACAO:", "FLORIANOPOLIS"),
         ("CODIGO (WMO):", "A806"), ("LATITUDE:", "-27,6"), ("LONGITUDE:", "-48,6"),
         ("ALTITUDE:", "1,8"), ("DATA DE FUNDACAO:", "01/01/03")],
        ("Data", "Hora UTC"),
        linhas_observacoes(datetime(2024, 4, 25, 3), 2, rng, True, set(), set()),
    )
    print(f"dados de exemplo gerados em {pasta}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures")

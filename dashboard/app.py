"""Dashboard do clima no RS a partir da camada gold.

Rodar:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_DB = Path(os.getenv("INMET_DB_PATH", RAIZ / "data" / "warehouse" / "inmet.duckdb"))

st.set_page_config(page_title="Chuva e temperatura no RS", page_icon="🌧️", layout="wide")


@st.cache_resource
def conexao() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(CAMINHO_DB), read_only=True)


@st.cache_data(ttl=600)
def consultar(sql: str, params: tuple = ()) -> pd.DataFrame:
    return conexao().execute(sql, list(params)).df()


if not CAMINHO_DB.exists():
    st.error(
        f"Banco não encontrado em `{CAMINHO_DB}`. Rode `make pipeline` (dados reais) "
        "ou `make demo` (dados de exemplo) antes de abrir o dashboard."
    )
    st.stop()

estacoes = consultar(
    "select codigo_estacao, nome, latitude, longitude, primeiro_dia, ultimo_dia, "
    "pct_dias_chuva_validos from gold.dim_estacoes order by nome"
)
if estacoes.empty:
    st.warning("Nenhuma estação carregada ainda.")
    st.stop()

# --- Filtros -----------------------------------------------------------------
st.sidebar.header("Filtros")
rotulos = {f"{r.nome.title()} ({r.codigo_estacao})": r.codigo_estacao for r in estacoes.itertuples()}
padrao = next((i for i, c in enumerate(rotulos.values()) if c == "A801"), 0)  # Porto Alegre
rotulo = st.sidebar.selectbox("Estação", list(rotulos), index=padrao)
codigo = rotulos[rotulo]

# Só meses com pelo menos um dia de chuva válido. O INMET publica em UTC: as
# primeiras horas de 1º de janeiro caem em 31/12 do ano anterior no horário
# local, criando um "mês" com 3 horas de dado que não deve aparecer.
anos = consultar(
    """
    select distinct year(mes) as ano from gold.fct_clima_mensal
    where codigo_estacao = ? and dias_validos > 0
    order by 1
    """,
    (codigo,),
)["ano"].tolist()
if not anos:
    st.warning("Esta estação ainda não tem dias com dados suficientes.")
    st.stop()
ano_ini, ano_fim = (
    st.sidebar.select_slider("Período", options=anos, value=(anos[0], anos[-1]))
    if len(anos) > 1
    else (anos[0], anos[0])
)

st.sidebar.caption(
    "Fonte: INMET, estações automáticas. Chuva diária só é calculada para dias com "
    "horas válidas suficientes; veja o README do projeto."
)

# --- Cabeçalho e indicadores -------------------------------------------------
st.title("🌧️ Chuva e temperatura no Rio Grande do Sul")
st.caption(f"Estação {rotulo} · {ano_ini}–{ano_fim}")

diario = consultar(
    """
    select * from gold.fct_clima_diario
    where codigo_estacao = ? and year(data_local) between ? and ?
    order by data_local
    """,
    (codigo, ano_ini, ano_fim),
)
mensal = consultar(
    """
    select * from gold.fct_clima_mensal
    where codigo_estacao = ? and year(mes) between ? and ? and dias_validos > 0
    order by mes
    """,
    (codigo, ano_ini, ano_fim),
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Chuva no período", f"{diario['chuva_mm'].sum():,.0f} mm".replace(",", "."))
maior_chuva = diario["chuva_mm"].max()
c2.metric("Maior chuva em um dia", f"{maior_chuva:.1f} mm" if pd.notna(maior_chuva) else "–")
c3.metric("Dias de chuva extrema", int(diario["dia_chuva_extrema"].fillna(False).sum()))
c4.metric("Temperatura média", f"{diario['temperatura_media_c'].mean():.1f} °C")

# --- Chuva mensal x média histórica ------------------------------------------
st.subheader("Chuva mensal comparada à média histórica da estação")
if mensal.empty:
    st.info("Sem meses no período selecionado.")
else:
    # Eixo categórico (um rótulo por mês): com eixo de tempo contínuo, as barras
    # ficam finas como linhas e os rótulos viram dias da semana em inglês.
    mensal["mes_rotulo"] = pd.to_datetime(mensal["mes"]).dt.strftime("%m/%Y")
    base = alt.Chart(mensal).encode(
        # ordem explícita: "12/2023" antes de "01/2024", e não em ordem alfabética
        x=alt.X("mes_rotulo:O", sort=mensal["mes_rotulo"].tolist(), title=None, axis=alt.Axis(labelAngle=0))
    )
    barras = base.mark_bar(opacity=0.8).encode(
        y=alt.Y("chuva_total_mm:Q", title="Chuva (mm)"),
        color=alt.condition("datum.anomalia_chuva_pct > 100", alt.value("#c0392b"), alt.value("#2e86c1")),
        tooltip=[
            alt.Tooltip("mes_rotulo:O", title="Mês"),
            alt.Tooltip("chuva_total_mm:Q", title="Chuva (mm)"),
            alt.Tooltip("chuva_media_historica_mm:Q", title="Média histórica (mm)"),
            alt.Tooltip("anomalia_chuva_pct:Q", title="Anomalia (%)"),
            alt.Tooltip("dias_validos:Q", title="Dias com dado"),
        ],
    )
    media = base.mark_line(color="#555", strokeDash=[4, 3]).encode(y="chuva_media_historica_mm:Q")
    st.altair_chart(barras + media, use_container_width=True)
    st.caption("Vermelho: mês com mais que o dobro da média histórica. Linha tracejada: média do mesmo mês nos outros anos.")

# --- Série diária --------------------------------------------------------------
st.subheader("Chuva diária e acumulado de 5 dias")
if not diario.empty:
    serie = diario[["data_local", "chuva_mm", "chuva_acumulada_5d_mm"]].melt(
        "data_local", var_name="medida", value_name="mm"
    )
    serie["medida"] = serie["medida"].map(
        {"chuva_mm": "Chuva do dia", "chuva_acumulada_5d_mm": "Acumulado 5 dias"}
    )
    st.altair_chart(
        alt.Chart(serie)
        .mark_line()
        .encode(
            x=alt.X("data_local:T", title=None, axis=alt.Axis(format="%d/%m/%Y")),
            y=alt.Y("mm:Q", title="mm"),
            color=alt.Color("medida:N", title=None),
            tooltip=[alt.Tooltip("data_local:T", title="Dia", format="%d/%m/%Y"), "medida:N", "mm:Q"],
        ),
        use_container_width=True,
    )

# --- Eventos extremos em todo o estado ----------------------------------------
st.subheader("Dias de chuva extrema em todas as estações")
eventos = consultar(
    """
    select data_local as dia, estacao, chuva_mm, chuva_acumulada_5d_mm, latitude, longitude
    from gold.fct_eventos_chuva_extrema
    where year(data_local) between ? and ?
    order by chuva_mm desc
    limit 200
    """,
    (ano_ini, ano_fim),
)
col_mapa, col_tabela = st.columns([1, 1])
with col_mapa:
    if not eventos.empty:
        st.map(eventos.rename(columns={"latitude": "lat", "longitude": "lon"}), size="chuva_mm")
with col_tabela:
    st.dataframe(
        eventos.drop(columns=["latitude", "longitude"]).head(30),
        hide_index=True,
        use_container_width=True,
        column_config={
            "dia": st.column_config.DateColumn("Dia", format="DD/MM/YYYY"),
            "estacao": "Estação",
            "chuva_mm": st.column_config.NumberColumn("Chuva (mm)", format="%.1f"),
            "chuva_acumulada_5d_mm": st.column_config.NumberColumn("Acum. 5 dias (mm)", format="%.1f"),
        },
    )

# --- Qualidade dos dados -----------------------------------------------------
with st.expander("Qualidade dos dados por estação"):
    st.dataframe(
        estacoes.drop(columns=["latitude", "longitude"]),
        hide_index=True,
        use_container_width=True,
        column_config={
            "codigo_estacao": "Código",
            "nome": "Estação",
            "primeiro_dia": st.column_config.DateColumn("Primeiro dia", format="DD/MM/YYYY"),
            "ultimo_dia": st.column_config.DateColumn("Último dia", format="DD/MM/YYYY"),
            "pct_dias_chuva_validos": st.column_config.ProgressColumn(
                "% dias com chuva válida", min_value=0, max_value=100, format="%.0f%%"),
        },
    )

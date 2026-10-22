-- Camada silver: uma linha por estação/hora, valores implausíveis descartados
-- e horário convertido para o fuso local.

with fonte as (
    select * from {{ source('bronze', 'observacoes_horarias') }}
),

-- O mesmo horário pode aparecer em mais de um arquivo (ex.: reprocessamento
-- ou correção publicada pelo INMET). Fica a carga mais recente.
deduplicado as (
    select *
    from fonte
    qualify row_number() over (
        partition by codigo_estacao, ts_utc
        order by carregado_em desc, arquivo_origem desc
    ) = 1
),

convertido as (
    select
        codigo_estacao,
        ts_utc,
        ts_utc + to_hours({{ var('offset_utc_horas') }}) as ts_local,

        {{ valor_plausivel('precipitacao_mm', 'precipitacao_mm') }}   as precipitacao_mm,
        {{ valor_plausivel('temperatura_c', 'temperatura_c') }}       as temperatura_c,
        {{ valor_plausivel('temperatura_max_c', 'temperatura_c') }}   as temperatura_max_c,
        {{ valor_plausivel('temperatura_min_c', 'temperatura_c') }}   as temperatura_min_c,
        {{ valor_plausivel('orvalho_c', 'temperatura_c') }}           as orvalho_c,
        {{ valor_plausivel('umidade_pct', 'umidade_pct') }}           as umidade_pct,
        {{ valor_plausivel('pressao_mb', 'pressao_mb') }}             as pressao_mb,
        {{ valor_plausivel('vento_velocidade_ms', 'vento_ms') }}      as vento_velocidade_ms,
        {{ valor_plausivel('vento_rajada_ms', 'vento_ms') }}          as vento_rajada_ms,
        case when radiacao_kj_m2 >= 0 then radiacao_kj_m2 end         as radiacao_kj_m2,

        (
            {{ fora_da_faixa('precipitacao_mm', 'precipitacao_mm') }}
            or {{ fora_da_faixa('temperatura_c', 'temperatura_c') }}
            or {{ fora_da_faixa('umidade_pct', 'umidade_pct') }}
            or {{ fora_da_faixa('pressao_mb', 'pressao_mb') }}
            or {{ fora_da_faixa('vento_velocidade_ms', 'vento_ms') }}
        ) as teve_valor_descartado,

        arquivo_origem
    from deduplicado
)

select
    *,
    cast(ts_local as date) as data_local
from convertido

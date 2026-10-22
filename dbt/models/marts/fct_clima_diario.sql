-- Camada gold: uma linha por estação e dia (horário local).

with horas as (
    select * from {{ ref('stg_observacoes_horarias') }}
),

diario as (
    select
        codigo_estacao,
        data_local,
        count(*)                                  as horas_registradas,
        count(precipitacao_mm)                    as horas_chuva_validas,
        count(temperatura_c)                      as horas_temperatura_validas,

        -- Só soma a chuva do dia se houver horas válidas suficientes; caso contrário
        -- o total ficaria subestimado e pareceria um dia seco.
        case
            when count(precipitacao_mm) >= {{ var('min_horas_validas_dia') }}
            then round(sum(precipitacao_mm), 1)
        end                                       as chuva_mm,
        round(max(precipitacao_mm), 1)            as chuva_max_hora_mm,

        round(avg(temperatura_c), 1)              as temperatura_media_c,
        round(max(coalesce(temperatura_max_c, temperatura_c)), 1) as temperatura_max_c,
        round(min(coalesce(temperatura_min_c, temperatura_c)), 1) as temperatura_min_c,
        round(avg(umidade_pct), 1)                as umidade_media_pct,
        round(max(vento_rajada_ms), 1)            as rajada_max_ms,
        count(*) filter (where teve_valor_descartado) as horas_com_valor_descartado
    from horas
    group by codigo_estacao, data_local
)

select
    *,
    -- Acumulado dos últimos 5 dias (inclusive): chuva persistente é o que mais
    -- se relaciona com cheias, mais do que um único dia isolado.
    round(sum(chuva_mm) over (
        partition by codigo_estacao
        order by data_local
        range between interval 4 days preceding and current row
    ), 1) as chuva_acumulada_5d_mm,
    chuva_mm >= {{ var('limiar_chuva_extrema_mm') }} as dia_chuva_extrema
from diario

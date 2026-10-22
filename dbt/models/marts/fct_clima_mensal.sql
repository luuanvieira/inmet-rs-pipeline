-- Camada gold: uma linha por estação e mês, com comparação contra a média
-- histórica da própria estação para o mesmo mês do ano.

with diario as (
    select * from {{ ref('fct_clima_diario') }}
),

mensal as (
    select
        codigo_estacao,
        cast(date_trunc('month', data_local) as date) as mes,
        count(chuva_mm)                                as dias_validos,
        round(sum(chuva_mm), 1)                        as chuva_total_mm,
        round(max(chuva_mm), 1)                        as chuva_max_dia_mm,
        count(*) filter (where dia_chuva_extrema)      as dias_chuva_extrema,
        round(avg(temperatura_media_c), 1)             as temperatura_media_c,
        round(max(temperatura_max_c), 1)               as temperatura_max_c,
        round(min(temperatura_min_c), 1)               as temperatura_min_c
    from diario
    group by 1, 2
),

com_flag as (
    select
        *,
        dias_validos >= {{ var('min_dias_validos_mes') }} as mes_completo
    from mensal
)

select
    *,
    -- Média histórica considerando só meses completos (meses com falha de
    -- equipamento puxariam a média para baixo).
    round(avg(case when mes_completo then chuva_total_mm end) over (
        partition by codigo_estacao, month(mes)
    ), 1) as chuva_media_historica_mm,
    count(case when mes_completo then 1 end) over (
        partition by codigo_estacao, month(mes)
    ) as anos_na_media,
    case
        when mes_completo then round(
            100.0 * (chuva_total_mm / nullif(avg(case when mes_completo then chuva_total_mm end) over (
                partition by codigo_estacao, month(mes)
            ), 0) - 1),
            1
        )
    end as anomalia_chuva_pct
from com_flag

-- Primeiro e último dia consideram só dias com horas suficientes de dado. Sem
-- esse filtro, o primeiro dia de quase toda estação seria 31/12 do ano anterior:
-- as 3 primeiras horas UTC de 1º de janeiro caem nesse dia no horário local.
with cobertura as (
    select
        codigo_estacao,
        min(data_local) filter (where horas_registradas >= {{ var('min_horas_validas_dia') }}) as primeiro_dia,
        max(data_local) filter (where horas_registradas >= {{ var('min_horas_validas_dia') }}) as ultimo_dia,
        count(*) filter (where horas_registradas >= {{ var('min_horas_validas_dia') }})        as dias_com_registro,
        count(chuva_mm)                  as dias_chuva_validos
    from {{ ref('fct_clima_diario') }}
    group by 1
)

select
    e.codigo_estacao,
    e.nome,
    e.uf,
    e.latitude,
    e.longitude,
    e.altitude_m,
    c.primeiro_dia,
    c.ultimo_dia,
    coalesce(c.dias_com_registro, 0) as dias_com_registro,
    round(100.0 * c.dias_chuva_validos / nullif(c.dias_com_registro, 0), 1) as pct_dias_chuva_validos
from {{ ref('stg_estacoes') }} as e
left join cobertura as c using (codigo_estacao)

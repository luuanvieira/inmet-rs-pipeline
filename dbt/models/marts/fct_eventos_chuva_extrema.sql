-- Camada gold: dias com chuva acima do limiar, prontos para o dashboard.

select
    d.data_local,
    d.codigo_estacao,
    e.nome as estacao,
    e.latitude,
    e.longitude,
    d.chuva_mm,
    d.chuva_max_hora_mm,
    d.chuva_acumulada_5d_mm,
    rank() over (partition by year(d.data_local) order by d.chuva_mm desc) as ranking_no_ano
from {{ ref('fct_clima_diario') }} as d
join {{ ref('dim_estacoes') }} as e using (codigo_estacao)
where d.dia_chuva_extrema

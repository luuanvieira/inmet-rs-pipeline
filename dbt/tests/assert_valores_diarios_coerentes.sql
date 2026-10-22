-- Regras de coerência física do resumo diário. Qualquer linha retornada é uma falha.
select *
from {{ ref('fct_clima_diario') }}
where chuva_mm < 0
   or temperatura_max_c < temperatura_min_c
   or umidade_media_pct not between 0 and 100
   or horas_registradas > 24
   or chuva_acumulada_5d_mm < chuva_mm

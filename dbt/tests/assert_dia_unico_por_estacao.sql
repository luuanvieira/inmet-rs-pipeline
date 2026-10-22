select codigo_estacao, data_local, count(*) as ocorrencias
from {{ ref('fct_clima_diario') }}
group by 1, 2
having count(*) > 1

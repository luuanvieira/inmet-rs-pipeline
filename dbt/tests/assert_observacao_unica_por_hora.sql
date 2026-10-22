-- Depois da deduplicação, cada estação deve ter no máximo uma linha por hora.
select codigo_estacao, ts_utc, count(*) as ocorrencias
from {{ ref('stg_observacoes_horarias') }}
group by 1, 2
having count(*) > 1

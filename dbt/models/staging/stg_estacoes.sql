select
    codigo_estacao,
    nome,
    uf,
    latitude,
    longitude,
    altitude_m
from {{ source('bronze', 'estacoes') }}

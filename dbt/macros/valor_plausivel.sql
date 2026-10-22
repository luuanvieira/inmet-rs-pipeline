{# Mantém o valor se estiver dentro dos limites físicos configurados em vars.limites; senão, NULL. #}
{% macro valor_plausivel(coluna, limite) -%}
    {%- set faixa = var('limites')[limite] -%}
    case when {{ coluna }} between {{ faixa[0] }} and {{ faixa[1] }} then {{ coluna }} end
{%- endmacro %}

{# TRUE quando havia leitura, mas ela estava fora dos limites (útil para medir a qualidade do dado). #}
{% macro fora_da_faixa(coluna, limite) -%}
    {%- set faixa = var('limites')[limite] -%}
    ({{ coluna }} is not null and {{ coluna }} not between {{ faixa[0] }} and {{ faixa[1] }})
{%- endmacro %}

{#
  Por padrão o dbt concatena o schema do profile com o customizado (main_silver).
  Aqui usamos o nome customizado direto, para ter os schemas bronze/silver/gold.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

{#- SQL that DuckDB and PostgreSQL write differently lives here, and only here.
    Every model calls these macros, so the models themselves are identical on
    both databases (docs/adr/0010). -#}

{#- NHS England has published dates as 01/07/2022 and as 2022-07-01. -#}
{% macro parse_nhs_date(column) -%}
    {{ return(adapter.dispatch('parse_nhs_date')(column)) }}
{%- endmacro %}

{% macro duckdb__parse_nhs_date(column) -%}
    cast(coalesce(try_strptime(trim({{ column }}), '%d/%m/%Y'), try_strptime(trim({{ column }}), '%Y-%m-%d')) as date)
{%- endmacro %}

{% macro postgres__parse_nhs_date(column) -%}
    case
        when trim({{ column }}) ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' then to_date(trim({{ column }}), 'DD/MM/YYYY')
        when trim({{ column }}) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then to_date(trim({{ column }}), 'YYYY-MM-DD')
    end
{%- endmacro %}

{#- A number, or null for suppressed and other non numeric values. -#}
{% macro safe_to_numeric(column) -%}
    {{ return(adapter.dispatch('safe_to_numeric')(column)) }}
{%- endmacro %}

{% macro duckdb__safe_to_numeric(column) -%}
    try_cast(trim({{ column }}) as double)
{%- endmacro %}

{% macro postgres__safe_to_numeric(column) -%}
    case
        when trim({{ column }}) ~ '^[-+]?([0-9]+[.]?[0-9]*|[.][0-9]+)([eE][-+]?[0-9]+)?$'
        then cast(trim({{ column }}) as double precision)
    end
{%- endmacro %}

{#- The many published geography labels mapped onto six stable levels (docs/adr/0004). -#}
{% macro canonical_geo_level(label) -%}
    case
        when lower({{ label }}) like '%sub icb%' then 'Sub ICB'
        when lower({{ label }}) like '%icb%' then 'ICB'
        when lower({{ label }}) like '%commissioning region%' then 'Commissioning Region'
        when lower({{ label }}) like '%local authority%' then 'Local Authority'
        when lower({{ label }}) like '%provider%' then 'Provider'
        when lower({{ label }}) = 'england' then 'England'
        else {{ label }}
    end
{%- endmacro %}

{#- Codes such as UNKNOWN are catch alls, not real places. -#}
{% macro is_real_code(column) -%}
    upper(coalesce({{ column }}, '')) not in ('UNKNOWN', 'INVALID', 'MISSING', 'NONE', '')
{%- endmacro %}

{#- Number of months a reporting window covers, counting both ends. -#}
{% macro window_months(start_column, end_column) -%}
    cast(
        (extract(year from {{ end_column }}) - extract(year from {{ start_column }})) * 12
        + extract(month from {{ end_column }}) - extract(month from {{ start_column }}) + 1
    as integer)
{%- endmacro %}

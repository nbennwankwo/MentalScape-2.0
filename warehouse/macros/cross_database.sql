{#- SQL that DuckDB and PostgreSQL write differently lives here, and only here.
    Every model calls these macros, so the models themselves are identical on
    both databases (docs/adr/0010). -#}

{#- True when a column matches a regular expression. -#}
{% macro regex_match(column, pattern) -%}
    {{ return(adapter.dispatch('regex_match')(column, pattern)) }}
{%- endmacro %}

{% macro duckdb__regex_match(column, pattern) -%}
    regexp_matches({{ column }}, '{{ pattern }}')
{%- endmacro %}

{% macro postgres__regex_match(column, pattern) -%}
    ({{ column }} ~ '{{ pattern }}')
{%- endmacro %}

{#- NHS England has published dates in five styles (docs/data/mhsds_change_log.md).
        01/07/2022  most files
        1/4/2024    End of Year Final files for 2024-25
        01/06/24    End of Year Final file for June 2024
        2023-06-01  some 2023-24 rows and the 2025-26 final files
        01-04-2025  End of Year Final file for April 2025
    Each style is matched exactly and split into day, month and year, so a
    date is never silently misread, for example 24 as the year 24 AD.
    Anything else stays null and the not_null test fails. -#}
{% macro parse_nhs_date(column) -%}
    {%- set value = "trim(" ~ column ~ ")" -%}
    case
        when {{ regex_match(value, '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$') }} then make_date(
            cast(split_part({{ value }}, '/', 3) as integer),
            cast(split_part({{ value }}, '/', 2) as integer),
            cast(split_part({{ value }}, '/', 1) as integer))
        when {{ regex_match(value, '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{2}$') }} then make_date(
            2000 + cast(split_part({{ value }}, '/', 3) as integer),
            cast(split_part({{ value }}, '/', 2) as integer),
            cast(split_part({{ value }}, '/', 1) as integer))
        when {{ regex_match(value, '^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$') }} then make_date(
            cast(split_part({{ value }}, '-', 1) as integer),
            cast(split_part({{ value }}, '-', 2) as integer),
            cast(split_part({{ value }}, '-', 3) as integer))
        when {{ regex_match(value, '^[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}$') }} then make_date(
            cast(split_part({{ value }}, '-', 3) as integer),
            cast(split_part({{ value }}, '-', 2) as integer),
            cast(split_part({{ value }}, '-', 1) as integer))
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
        -- In 2022-23 the national ethnicity split had no geography in its label.
        when lower({{ label }}) = 'ethnicity (white british/non-white british)' then 'England'
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

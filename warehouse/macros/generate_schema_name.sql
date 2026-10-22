{#- Use the schema names in dbt_project.yml as they are, so tables land in
    staging, intermediate, marts and reference rather than main_staging. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}

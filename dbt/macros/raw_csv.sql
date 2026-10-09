{% macro raw_csv(folder_var, file_name) %}
    {#
        Reads one raw CSV with plain DuckDB. Every column comes in as text
        (all_varchar), so DuckDB never guesses a type. Each staging model
        then casts the columns it needs, on purpose.

        folder_var : name of a var in dbt_project.yml holding the folder path
        file_name  : the CSV file inside that folder
    #}
    read_csv('{{ var(folder_var) }}/{{ file_name }}', header = true, all_varchar = true)
{% endmacro %}

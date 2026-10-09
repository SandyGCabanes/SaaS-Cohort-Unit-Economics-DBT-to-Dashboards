{% macro export_to_csv(file_name) %}
    {#
        Runs as a post-hook, after {{ this }} is fully materialized.
        Writes the finished table straight to a CSV in the export_dir folder
        (see the export_dir var in dbt_project.yml). In this dev setup that's
        ./target/ - in production point export_dir at a mounted path and pick
        the file up from there for the manual upload to S3 / Azure Data Lake / GCS.
    #}
    copy (select * from {{ this }}) to '{{ var("export_dir") }}/{{ file_name }}' (header, delimiter ',')
{% endmacro %}

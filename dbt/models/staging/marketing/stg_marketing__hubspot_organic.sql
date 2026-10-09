with source as (

    select * from {{ raw_csv('raw_marketing_dir', 'hubspot_organic_downloads.csv') }}

),

renamed as (

    select
        customer_id,
        'Organic'                                       as channel,
        hubspot_contact_id,
        recent_conversion_event,
        lifecycle_stage,
        plan_tier                                       as hubspot_plan_tier,
        cast(organic_acquisition_cost_usd as double)    as acquisition_cost_usd,
        cast(signup_timestamp as timestamp)             as signup_timestamp

    from source

)

select * from renamed

with source as (

    select * from {{ raw_csv('raw_marketing_dir', 'google_ads.csv') }}

),

renamed as (

    select
        customer_id,
        'Ads'                           as channel,
        'google'                        as ad_platform,
        campaign_name,
        ad_group                        as ad_set_id,
        cast(null as varchar)           as placement,
        cast(impressions as integer)    as impressions,
        cast(clicks as integer)         as clicks,
        cast(spend_usd as double)       as acquisition_cost_usd,
        cast(conversion_date as date)   as conversion_date

    from source

)

select * from renamed

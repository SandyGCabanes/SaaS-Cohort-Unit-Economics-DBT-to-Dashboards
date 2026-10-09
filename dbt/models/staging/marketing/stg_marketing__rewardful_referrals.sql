with source as (

    select * from {{ raw_csv('raw_marketing_dir', 'rewardful_referrals.csv') }}

),

renamed as (

    select
        customer_id,
        'Referral'                                  as channel,
        referral_id,
        affiliate_id,
        referral_link_used,
        cast(commission_amount_usd as double)       as acquisition_cost_usd,
        cast(conversion_timestamp as timestamp)     as conversion_timestamp

    from source

)

select * from renamed

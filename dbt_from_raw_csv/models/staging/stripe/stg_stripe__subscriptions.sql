with source as (

    select * from {{ raw_csv('raw_stripe_dir', 'stripe_subscriptions.csv') }}

),

renamed as (

    select
        id                                      as subscription_id,
        customer_id                             as stripe_customer_id,
        plan_tier,
        status                                  as subscription_status,
        cast(created as date)                   as subscription_created_date,
        -- active subscriptions have a blank canceled_at
        cast(nullif(canceled_at, '') as date)   as subscription_canceled_date

    from source

)

select * from renamed

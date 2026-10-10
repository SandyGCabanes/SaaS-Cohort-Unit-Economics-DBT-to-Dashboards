with source as (

    select * from {{ raw_csv('raw_stripe_dir', 'stripe_customers.csv') }}

),

renamed as (

    select
        id                          as stripe_customer_id,
        email                       as customer_email,
        name                        as customer_name,
        source_customer_id          as customer_id,
        cast(created as date)       as customer_created_date

    from source

)

select * from renamed

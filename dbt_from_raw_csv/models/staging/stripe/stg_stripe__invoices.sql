with source as (

    select * from {{ raw_csv('raw_stripe_dir', 'stripe_invoices.csv') }}

),

renamed as (

    select
        id                                  as invoice_id,
        customer_id                         as stripe_customer_id,
        subscription_id,
        cast(amount_paid as bigint) / 100.0 as amount_paid_dollars,
        currency,
        status                              as invoice_status,
        cast(invoice_date as date)          as invoice_date,
        cast(period_start as date)          as period_start,
        cast(period_end as date)            as period_end,
        strftime(cast(period_start as date), '%Y-%m') as billing_month

    from source

)

select * from renamed

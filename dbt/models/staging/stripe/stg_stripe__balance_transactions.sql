with source as (

    select * from {{ raw_csv('raw_stripe_dir', 'stripe_balance_transactions.csv') }}

),

renamed as (

    select
        id                                  as balance_transaction_id,
        source                              as invoice_id,
        type                                as transaction_type,
        cast(amount as bigint) / 100.0      as gross_amount_dollars,
        cast(fee as bigint) / 100.0         as fee_dollars,
        cast(net as bigint) / 100.0         as net_amount_dollars,
        cast(created as date)               as transaction_date

    from source

)

select * from renamed

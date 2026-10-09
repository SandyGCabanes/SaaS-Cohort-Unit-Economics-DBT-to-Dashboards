with source as (

    select * from {{ raw_csv('raw_stripe_dir', 'stripe_invoice_line_items.csv') }}

),

renamed as (

    select
        id                          as invoice_line_item_id,
        invoice_id,
        subscription_id,
        cast(amount as double)      as line_amount_dollars,
        description                 as line_description

    from source

)

select * from renamed

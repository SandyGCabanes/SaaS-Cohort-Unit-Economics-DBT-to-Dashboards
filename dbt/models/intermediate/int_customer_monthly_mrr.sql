with invoices as (

    select * from {{ ref('stg_stripe__invoices') }}

),

customers as (

    select * from {{ ref('stg_stripe__customers') }}

),

joined as (

    select
        customers.customer_id,
        invoices.billing_month         as calendar_month,
        invoices.amount_paid_dollars
    from invoices
    inner join customers
        on invoices.stripe_customer_id = customers.stripe_customer_id
    where invoices.invoice_status = 'paid'

),

monthly as (

    -- guard against >1 paid invoice landing in the same billing month
    select
        customer_id,
        calendar_month,
        sum(amount_paid_dollars) as mrr
    from joined
    group by 1, 2

),

with_cohort as (

    -- cohort_month = the customer's first paid invoice month, a real business
    -- event. This is the system of record for cohort.
    select
        *,
        min(calendar_month) over (partition by customer_id) as cohort_month
    from monthly

),

with_cohort_year as (

    -- cohort_year = the calendar year of cohort_month, as an integer (e.g. 2022).
    -- cohort_month is a 'YYYY-MM' string, so the first 4 characters are the year.
    select
        *,
        cast(substr(cohort_month, 1, 4) as integer) as cohort_year
    from with_cohort

)

select * from with_cohort_year

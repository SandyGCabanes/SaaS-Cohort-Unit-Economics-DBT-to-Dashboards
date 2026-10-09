{{
  config(
    post_hook="{{ export_to_csv('customer_month_panel.csv') }}"
  )
}}

with acquisition as (

    select * from {{ ref('int_customer_acquisition') }}

),

monthly_mrr as (

    select * from {{ ref('int_customer_monthly_mrr') }}

),

joined as (

    select
        monthly_mrr.customer_id,
        acquisition.channel,
        acquisition.plan_tier,
        monthly_mrr.cohort_year,
        monthly_mrr.cohort_month,
        monthly_mrr.calendar_month,
        acquisition.customer_cac,
        monthly_mrr.mrr
    from monthly_mrr
    inner join acquisition
        on monthly_mrr.customer_id = acquisition.customer_id

),

with_lifetime as (

    select
        *,
        date_diff(
            'month',
            strptime(cohort_month || '-01', '%Y-%m-%d'),
            strptime(calendar_month || '-01', '%Y-%m-%d')
        ) as lifetime_month
    from joined

),

with_observation_window as (

    -- The last calendar month that appears anywhere in the billing data. A cohort
    -- has been "observed" from its first paid month up to this month.
    select
        *,
        max(calendar_month) over () as last_calendar_month
    from with_lifetime

),

with_clv as (

    -- CLV is capped at the first clv_horizon_months lifetime months (0 to 23 for 24).
    -- Revenue after that is left out, so every customer is measured over the same
    -- window. A customer whose cohort has not yet lived 24 months gets the revenue
    -- earned so far, and is_mature_24m = false marks that figure as partial.
    -- strptime(cohort_month || '01', '%Y-%m-%d') concatenate then convert month-level string to full date object
    -- CAC is a one-time charge and is not touched here.
    select
        *,
        true as is_active,
        sum(case when lifetime_month < {{ var('clv_horizon_months') }} then mrr else 0 end)
            over (partition by customer_id) as customer_clv_24m,
        -- months observed = first paid month through the last data month, inclusive
        date_diff(
            'month',
            strptime(cohort_month || '-01', '%Y-%m-%d'), 
            strptime(last_calendar_month || '-01', '%Y-%m-%d')
        ) + 1 >= {{ var('clv_horizon_months') }} as is_mature_24m
    from with_observation_window

),

final as (

    select
        customer_id,
        channel,
        plan_tier,
        cohort_year,
        cohort_month,
        calendar_month,
        lifetime_month,
        is_active,
        round(mrr, 2)                as mrr,
        round(customer_clv_24m, 2)   as customer_clv_24m,
        round(customer_cac, 2)       as customer_cac,
        round(customer_clv_24m / nullif(customer_cac, 0), 4) as unit_clv_cac_ratio_24m,
        is_mature_24m
    from with_clv

)

select * from final
order by customer_id, calendar_month

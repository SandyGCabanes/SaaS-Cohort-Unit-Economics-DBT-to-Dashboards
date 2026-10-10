{{
  config(
    post_hook="{{ export_to_csv('cost_per_customer.csv') }}"
  )
}}

with acquisition as (

    select * from {{ ref('int_customer_acquisition') }}

),

customer_cohorts as (

    -- cohort_month lives on the revenue side now (first paid invoice month),
    -- not on the acquisition side - see int_customer_monthly_mrr.
    select distinct
        customer_id,
        cohort_year,
        cohort_month
    from {{ ref('int_customer_monthly_mrr') }}

),

with_cohort as (

    select
        acquisition.customer_id,
        acquisition.channel,
        acquisition.plan_tier,
        acquisition.customer_cac,
        customer_cohorts.cohort_year,
        customer_cohorts.cohort_month
    from acquisition
    inner join customer_cohorts
        on acquisition.customer_id = customer_cohorts.customer_id

),

segment as (

    select
        cohort_year,
        cohort_month,
        channel,
        plan_tier,
        count(distinct customer_id)  as new_customers,
        avg(customer_cac)            as cac_per_customer_dollars,
        sum(customer_cac)            as total_acquisition_cost_dollars
    from with_cohort
    group by 1, 2, 3, 4

),

with_share as (

    select
        *,
        new_customers / sum(new_customers) over (partition by cohort_month) as segment_mix_share_percentage
    from segment

),

final as (

    select
        cohort_year,
        cohort_month,
        channel,
        plan_tier,
        new_customers,
        round(segment_mix_share_percentage, 4)     as segment_mix_share_percentage,
        round(cac_per_customer_dollars, 2)          as cac_per_customer_dollars,
        round(total_acquisition_cost_dollars, 2)    as total_acquisition_cost_dollars
    from with_share

)

select * from final
order by cohort_year, cohort_month, channel, plan_tier

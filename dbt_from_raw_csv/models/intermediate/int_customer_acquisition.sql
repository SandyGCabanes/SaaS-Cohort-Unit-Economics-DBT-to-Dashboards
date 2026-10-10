-- One row per customer: the channel they were acquired through and their
-- acquisition cost (CAC), from the marketing sources. Plan tier comes from
-- Stripe's own subscription record (joined via stg_stripe__customers), not
-- from parsing the customer_id - Stripe customer IDs are opaque in
-- production and never carry business meaning like plan or cohort.

with ads as (

    select customer_id, channel, acquisition_cost_usd
    from {{ ref('stg_marketing__facebook_ads') }}

    union all

    select customer_id, channel, acquisition_cost_usd
    from {{ ref('stg_marketing__google_ads') }}

),

organic as (

    select customer_id, channel, acquisition_cost_usd
    from {{ ref('stg_marketing__hubspot_organic') }}

),

referral as (

    select customer_id, channel, acquisition_cost_usd
    from {{ ref('stg_marketing__rewardful_referrals') }}

),

unioned as (

    select * from ads
    union all
    select * from organic
    union all
    select * from referral

),

customers as (

    select * from {{ ref('stg_stripe__customers') }}

),

subscriptions as (

    select * from {{ ref('stg_stripe__subscriptions') }}

),

with_plan_tier as (

    select
        unioned.customer_id,
        unioned.channel,
        unioned.acquisition_cost_usd   as customer_cac,
        subscriptions.plan_tier
    from unioned
    inner join customers
        on unioned.customer_id = customers.customer_id
    inner join subscriptions
        on customers.stripe_customer_id = subscriptions.stripe_customer_id

)

select * from with_plan_tier

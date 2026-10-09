-- customer_clv_24m must equal the MRR earned in lifetime months 0 to 23, no more.
-- Any row returned is a failure (a difference of more than 2 cents).
select
    customer_id,
    max(customer_clv_24m)                                                   as reported_clv,
    sum(case when lifetime_month < {{ var('clv_horizon_months') }} then mrr else 0 end) as recomputed_clv
from {{ ref('customer_month_panel') }}
group by customer_id
having abs(max(customer_clv_24m)
         - sum(case when lifetime_month < {{ var('clv_horizon_months') }} then mrr else 0 end)) > 0.02

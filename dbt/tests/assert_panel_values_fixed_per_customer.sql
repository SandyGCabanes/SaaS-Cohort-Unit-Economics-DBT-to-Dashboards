-- Every customer must carry one CLV, one CAC, one ratio and one maturity flag
-- across all of their month rows. Any row returned is a failure.
select customer_id
from {{ ref('customer_month_panel') }}
group by customer_id
having count(distinct customer_clv_24m) > 1
    or count(distinct customer_cac) > 1
    or count(distinct unit_clv_cac_ratio_24m) > 1
    or count(distinct is_mature_24m) > 1

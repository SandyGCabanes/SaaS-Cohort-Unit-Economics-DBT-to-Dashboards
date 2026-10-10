```mermaid
graph LR
    %% Source tables
    fb["stg_marketing__facebook_ads"]
    ga["stg_marketing__google_ads"]
    ho["stg_marketing__hubspot_organic"]
    rf["stg_marketing__rewardful_referrals"]
    sc["stg_stripe__customers"]
    ss["stg_stripe__subscriptions"]

    %% CTEs
    ads["CTE<br>ads<br/>(UNION ALL)"]
    organic["CTE<br>organic"]
    referral["CTE<br>referral"]
    unioned["CTE<br>unioned<br/>(UNION ALL)"]
    customers["CTE<br>customers"]
    subscriptions["CTE<br>subscriptions"]
    wpt["CTE<br>with_plan_tier<br/>(INNER JOIN ×2)"]

    %% Output
    out["Model Output<br/>customer_id, channel,<br/>customer_cac, plan_tier"]

    %% Edges
    fb --> ads
    ga --> ads
    ho --> organic
    rf --> referral
    sc --> customers
    ss --> subscriptions

    ads --> unioned
    organic --> unioned
    referral --> unioned
    customers --> wpt
    subscriptions --> wpt
    unioned --> wpt

    wpt --> out  
``` 


## Column-level lineage

| Output Column | Source Table(s) | Source Column | Transformation |
|---|---|---|---|
| `customer_id` | `stg_marketing__facebook_ads`, `stg_marketing__google_ads`, `stg_marketing__hubspot_organic`, `stg_marketing__rewardful_referrals` | `customer_id` | Direct (pass-through via UNION ALL) |
| `channel` | same 4 marketing tables | `channel` | Direct |
| `customer_cac` | same 4 marketing tables | `acquisition_cost_usd` | Renamed (alias) |
| `plan_tier` | `stg_stripe__subscriptions` | `plan_tier` | Direct (via join through `stg_stripe__customers.stripe_customer_id`) |

## Join key lineage (filter/indirect)

| Join | Key Columns | Role |
|---|---|---|
| `unioned` ⋈ `customers` | `customer_id` | INNER JOIN — rows without a matching Stripe customer are dropped |
| `customers` ⋈ `subscriptions` | `customers.stripe_customer_id` = `subscriptions.stripe_customer_id` | INNER JOIN — rows without an active subscription are dropped |

The two `stripe_customer_id` columns act as **filter lineage**: they don't appear in the output but determine which rows survive.

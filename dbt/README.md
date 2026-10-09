# dbt_from_raw_csv

## Situation
Two raw systems feed the SaaS reporting layer: Stripe (billing) and four marketing
channel exports (Facebook Ads, Google Ads, HubSpot organic, Rewardful referrals).
This project reads their CSV extracts directly, transforms them into two marts,
then exports each mart to CSV for hand-off:
- `customer_month_panel` (customer x month grain, MRR, 24-month CLV, CAC)
- `cost_per_customer` (cohort_month x channel x plan_tier grain, CAC and mix)

It replaces `dbt_from_raw_duckdb`. That version needed two hand-built `.duckdb`
files before dbt could start. This one does not.

## Raw data
The raw CSVs live in two folders. A folder stands in for a bucket (S3 / GCS / Azure).

| Folder (var in `dbt_project.yml`) | Files |
|---|---|
| `raw/stripe_outputs` (`raw_stripe_dir`) | `stripe_customers`, `stripe_subscriptions`, `stripe_invoices`, `stripe_invoice_line_items`, `stripe_balance_transactions` |
| `raw/marketing_outputs` (`raw_marketing_dir`) | `facebook_ads`, `google_ads`, `hubspot_organic_downloads`, `rewardful_referrals` |

This zip ships the four marketing files in full and a 49-customer excerpt of each
Stripe file, so `dbt build` runs out of the box on a small sample.
To run on the real data, copy the full Stripe CSVs over the excerpts in
`raw/stripe_outputs/`. No code changes.

## How the CSVs are read
`macros/raw_csv.sql` wraps DuckDB's `read_csv`. Every column is read as text, so
DuckDB never guesses a type. Each staging model then casts the columns it uses.
Examples: `cast(amount_paid as bigint) / 100.0`, `cast(nullif(canceled_at, '') as date)`.

## Storage of CSV outputs
Each mart exports itself to `exports/` through a `post_hook` (`macros/export_to_csv.sql`):
```
exports/customer_month_panel.csv
exports/cost_per_customer.csv
```
`exports/` is not touched by `dbt clean`. In the story, a person (or an orchestrator
in a real company) moves these two files to the bucket that `dbt_to_exports` reads.
The bucket itself is simulated by a local folder.

## Structure
```
models/staging/         1:1 cleanup of each raw CSV (rename, cast, standardize)
models/intermediate/    Business-logic joins/unions (built as tables)
models/marts/           Final deliverables, each with a post_hook CSV export
macros/raw_csv.sql      Reads a raw CSV as text
macros/export_to_csv.sql  Writes a finished table to CSV
```

## Key logic (unchanged from dbt_from_raw_duckdb)
- `int_customer_acquisition`: one row per customer. Channel and CAC come from the four marketing sources. Plan tier comes from the Stripe subscription.
- `int_customer_monthly_mrr`: one row per customer per paid month. `cohort_month` is the first paid month. `cohort_year` is its first 4 characters, as an integer.
- `customer_month_panel`: joins the two. `customer_clv_24m` is MRR from lifetime months 0 to 23 only, repeated on each month row. See "24-month CLV cap" below.
- `cost_per_customer`: groups by `cohort_month, channel, plan_tier`.

## 24-month CLV cap
Customer lifetime value is limited to the first 24 months of each customer's life, so
every customer is measured over the same window.

- `customer_clv_24m`: MRR summed over lifetime months 0 to 23. Later months are left out.
- `customer_cac`: unchanged. CAC is a one-time charge from the marketing files.
- `unit_clv_cac_ratio_24m`: `customer_clv_24m / customer_cac`.
- `is_mature_24m`: true when the customer's cohort has 24 full months of data, counted from the
  first paid month to the last month in the billing data. It does not depend on whether the customer stayed.
- A customer whose cohort is younger than 24 months gets the revenue earned so far, and
  `is_mature_24m` is false. Filter on that flag for unit economics.
- The horizon is the `clv_horizon_months` var in `dbt_project.yml`. Keep it in sync with
  `CLV_HORIZON_MONTHS` in `saas_kpi_engine.py`.
- Replaced columns: `customer_clv` is now `customer_clv_24m`; `unit_clv_to_cac_ratio` is now `unit_clv_cac_ratio_24m`.
- `cost_per_customer` is unchanged.

## Checks run while building (on the shipped sample)
Done with a separate script, not with dbt:
- All 49 sample Stripe customers match exactly one marketing row.
- No marketing `customer_id` appears twice (64,941 rows across the four files).
- All 2,326 sample invoices are `paid`, with no customer billed twice in one month. The panel should therefore have 2,326 rows from the sample.
- 25 subscriptions are active (blank `canceled_at`) and 24 are canceled.

## Checks on the 24-month CLV cap
`dbt build` passes on the shipped sample (46 of 46). Two data tests guard the cap:
`assert_clv_24m_is_capped` and `assert_panel_values_fixed_per_customer`.
The panel was also matched against saas_dataset_v9 samples: 100 of 100 rows from the first-100 sample
and 3,817 of 3,817 rows from the random 100-customer sample (83 mature, 17 immature customers),
with no mismatches in any column.

## Setup note
Create an empty `exports/` folder before the first run. The export hook does not create it.
If `dbt` fails with a `KeyError` on a macro file, delete the `target/` folder and run again.

## Running locally
```
dbt build
```
Run it from this folder. `profiles.yml` sits here, so set `DBT_PROFILES_DIR` to this folder.

# Change: 24-month CLV cap

`customer_month_panel` now caps customer lifetime value at 24 months.

| Item | Before | After |
|---|---|---|
| CLV column | `customer_clv`, all months to the end of the data | `customer_clv_24m`, lifetime months 0 to 23 only |
| Ratio column | `unit_clv_to_cac_ratio` | `unit_clv_cac_ratio_24m` |
| New column | none | `is_mature_24m` |
| `customer_cac` | one-time charge | unchanged |
| `cost_per_customer` | | unchanged |
| New var | none | `clv_horizon_months: 24` |
| New tests | none | 3 not_null, 2 data tests |

Downstream (if adding): `dbt_to_exports` reads the old column names in `stg_revenue.sql`, `sources.yml`  and `reindexed_panel_audit_mrr.sql`. Need to update those three files before the next run.

---

# dbt_from_raw_csv vs dbt_from_raw_duckdb

| Item | dbt_from_raw_duckdb | dbt_from_raw_csv |
|---|---|---|
| Raw input | two hand-built `.duckdb` files, attached in `profiles.yml` | nine raw CSVs, read directly |
| `_sources.yml` | declares attached DuckDB sources | removed. Raw files are listed in `_staging.yml` |
| Reading raw data | `source()` | new macro `raw_csv` (all text, then explicit casts) |
| `profiles.yml` | two `attach:` blocks | no attach |
| Subscriptions table name | `stripe_subscrptions` (typo) | `stripe_subscriptions` |
| Intermediate models | views | tables, so the large invoice CSV is read once |
| Tests | 8 on the marts | adds unique / not_null / relationships on staging and unique `customer_id` on `int_customer_acquisition` |
| Marts, export macro | unchanged | unchanged |



**What changed from the old project **

- The two `.duckdb` files and the `attach:` blocks in `profiles.yml` are gone.
- The staging models now read the CSVs through a small new macro, `raw_csv`. It reads every column as text, and each staging model casts what it needs.
- `cast(nullif(canceled_at, '') as date)` stays as it was. Works for the  active customers with a blank `canceled_at`.
- The marts, the export macro, and the business logic are unchanged.
- The subscriptions typo is fixed, so the file is `stripe_subscriptions.csv`.
- The intermediate models are now tables. Otherwise the 122 MB invoices file would be read once per model that uses it. 
- Added `unique`, `not_null`, and `relationships` tests on staging, plus a `unique` test on `customer_id` in `int_customer_acquisition`.


**How to use it**

Copy the full Stripe CSVs in `raw/stripe_outputs/`, then run `dbt build`. The two output CSVs land in `exports/`. After that, compare `customer_month_panel.csv` to the original `saas_dataset_*.csv`. 

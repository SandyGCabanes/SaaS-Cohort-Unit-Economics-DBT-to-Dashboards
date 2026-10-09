"""
Disaggregate customer_month_panel.csv into Stripe-like raw object tables:
stripe_customers, stripe_subscriptions, stripe_invoices,
stripe_invoice_line_items, stripe_balance_transactions.

Follows the ERD in erd_stripe_to_panel.txt. The approach (per the "helper
table first" design decision): build one wide table at the panel's own
grain (one row per customer per active calendar_month) with every
back-calculated field added as its own column, validate it, THEN slice
that single table into the five narrower Stripe tables. This keeps every
derivation in one place instead of re-deriving things independently
inside each table-builder function.

Design decisions baked into this script (documented here so they're easy
to revisit):

1. ONE subscription per customer for the whole panel. No mid-life plan-
   tier changes are modeled - plan_tier is treated as constant per
   customer, matching how the panel already stores it (see
   int_customer_attributes.sql's identical assumption on the dbt side).

2. BILLING DAY OF MONTH is fabricated once per customer (stable, seeded on
   customer_id) and reused for every invoice for that customer. Real
   Stripe subscriptions bill on the same day each cycle; using a fresh
   random day per month would be less realistic than picking one day and
   keeping it fixed.

3. SUBSCRIPTION STATUS ('active' vs 'canceled') is inferred relative to
   the MAX calendar_month present in whatever file you feed this script:
   a customer whose last active row is NOT the file's max month is
   'canceled'; a customer whose last active row IS the file's max month
   is 'active' (open-ended / right-censored - we don't know what happens
   after the data ends). This means re-running on a fuller multi-year
   file can and should change some customers from 'active' to 'canceled'
   once their true final month is observed. That's expected, not a bug.

4. NAME/EMAIL on stripe_customers are placeholders (Customer <n> /
   customer<n>@example.com) - the source panel never had real names or
   emails to reverse-engineer, so these are fabricated only to satisfy
   Stripe's table shape, not reconstructed from anything.

5. BALANCE TRANSACTION FEES use the standard Stripe US card rate
   (2.9% + $0.30) as a realistic approximation, not because that value
   was reverse-engineered from the panel (the panel has no fee data).

Usage:
    python disaggregate_panel_to_stripe_sources.py            # newest saas_dataset_*.csv
    python disaggregate_panel_to_stripe_sources.py my_panel.csv   # or name a file

Outputs:
    helper_dfs/stripe_backcalc_helper.csv   (the wide intermediate table)
    stripe_outputs/stripe_customers.csv
    stripe_outputs/stripe_subscriptions.csv
    stripe_outputs/stripe_invoices.csv
    stripe_outputs/stripe_invoice_line_items.csv
    stripe_outputs/stripe_balance_transactions.csv
"""

import os
import sys
import glob
import time
from contextlib import contextmanager
import calendar
import hashlib
from datetime import date

import numpy as np
import pandas as pd

# ==========================================
# FIXED SETTINGS
# ==========================================

HELPER_DIR = "helper_dfs"
OUTPUT_DIR = "stripe_outputs"

STRIPE_PCT_FEE = 0.029   # 2.9%
STRIPE_FIXED_FEE_CENTS = 30  # $0.30


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def find_latest_csv(pattern: str, search_dir: str = ".") -> str:
    """
    Returns the path of the newest CSV in search_dir matching a glob pattern,
    e.g. "saas_dataset_*.csv". "Newest" means most recently modified.
    If several files match, prints which one was picked and which were skipped.
    """
    matches = glob.glob(os.path.join(search_dir, pattern))
    if not matches:
        raise FileNotFoundError(
            f"No file matching '{pattern}' found in '{os.path.abspath(search_dir)}'. "
            "Run the generator first, or pass a file path as the first argument."
        )
    matches.sort(key=os.path.getmtime, reverse=True)
    if len(matches) > 1:
        print(f"Found {len(matches)} files matching '{pattern}'. Using the newest: '{matches[0]}'")
        for skipped in matches[1:]:
            print(f"   skipped: '{skipped}'")
    return matches[0]

@contextmanager
def timed_step(label: str):
    """Prints the step name when it starts and how long it took when it ends."""
    print(f" -> {label}", flush=True)
    start = time.perf_counter()
    yield
    print(f"    [{label}] done in {time.perf_counter() - start:.1f}s", flush=True)


def export_dataframe(df: pd.DataFrame, directory: str, file_name: str) -> None:
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, file_name)
    start = time.perf_counter()
    df.to_csv(file_path, index=False)
    print(f" [Export] -> '{file_path}' ({len(df):,} rows, {time.perf_counter() - start:.1f}s)", flush=True)


def stable_billing_day(customer_id: str) -> int:
    """
    Deterministic, stable day-of-month (1-28) for a given customer_id.
    Capped at 28 so it's always a valid day regardless of which month
    it's applied to (avoids Feb 30th type problems).
    """
    digest = hashlib.sha256(customer_id.encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) % 28) + 1


def month_str_to_date(month_str: str, day: int = 1) -> date:
    """'YYYY-MM' -> date, clamping day to the last valid day of that month."""
    year, month = map(int, str(month_str).split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def month_end(month_str: str) -> date:
    year, month = map(int, str(month_str).split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def map_unique_keys(df: pd.DataFrame, key_columns: list, func) -> np.ndarray:
    """
    Works out func(*keys) once for each DISTINCT combination of key_columns,
    then copies the answer to every row with that combination.
    Same values as calling func row by row, but the work is done once per
    distinct key (for example 84 months) instead of once per row (1.4M rows).
    Returns values in the same row order as df.
    """
    distinct = df[key_columns].drop_duplicates().reset_index(drop=True)
    distinct["_value"] = [func(*keys) for keys in distinct.itertuples(index=False, name=None)]
    return df[key_columns].merge(distinct, on=key_columns, how="left")["_value"].to_numpy()


# ==========================================
# STEP 1: BUILD THE WIDE BACK-CALC HELPER TABLE
# ==========================================
def build_backcalc_helper(panel_df: pd.DataFrame) -> pd.DataFrame:
    """
    Builds the single wide table every Stripe table is sliced from.
    Same grain as the input panel: one row per customer per active
    calendar_month.
    """
    df = panel_df.copy()
    df["cohort_month"] = df["cohort_month"].astype(str)
    df["calendar_month"] = df["calendar_month"].astype(str)
    df = df.sort_values(["customer_id", "calendar_month"]).reset_index(drop=True)

    # --- Stable per-customer billing day (design decision #2) ---
    billing_day_map = {
        cust_id: stable_billing_day(cust_id) for cust_id in df["customer_id"].unique()
    }
    df["billing_day_of_month"] = df["customer_id"].map(billing_day_map)

    # --- Back-calc #1: subscription start date (from cohort_month + billing day) ---
    df["subscription_start_date"] = map_unique_keys(
        df, ["cohort_month", "billing_day_of_month"], month_str_to_date
    )

    # --- Back-calc #2: invoice period + invoice date (from calendar_month + billing day) ---
    df["invoice_period_start"] = map_unique_keys(df, ["calendar_month"], month_str_to_date)
    df["invoice_period_end"] = map_unique_keys(df, ["calendar_month"], month_end)
    df["invoice_date"] = map_unique_keys(
        df, ["calendar_month", "billing_day_of_month"], month_str_to_date
    )

    # --- Validation: recompute lifetime_month from the two back-calculated dates ---
    # Each distinct (cohort, billing day, calendar month) combination is worked out once,
    # using the same two back-calculated dates as before.
    df["lifetime_month_recalculated"] = map_unique_keys(
        df,
        ["cohort_month", "billing_day_of_month", "calendar_month"],
        lambda cohort, day, cal: months_between(
            month_str_to_date(cohort, day), month_str_to_date(cal, 1)
        ),
    )
    mismatches = df[df["lifetime_month_recalculated"] != df["lifetime_month"]]
    if not mismatches.empty:
        print(
            f" [Validation warning] {len(mismatches):,} row(s) where the recalculated "
            "lifetime_month doesn't match the panel's own lifetime_month column. "
            "Inspect helper_dfs/stripe_backcalc_helper.csv (rows where "
            "lifetime_month != lifetime_month_recalculated) before trusting the output."
        )

    # --- Invoice presence per month: every row here IS an active, invoiced month.
    # (The panel only stores active months - churned months are simply absent,
    # not zero-filled - so this is always True for every row that exists. Kept
    # as an explicit column because Stripe would never store a row for a month
    # with no invoice either.)
    df["invoice_present_this_month"] = True

    # --- Cumulative MRR to date, per customer ---
    df["cumulative_mrr_to_date"] = df.groupby("customer_id")["mrr"].cumsum()

    # --- Subscription status: is this row the customer's last observed month,
    # and is that also the file's overall max month? (design decision #3)
    dataset_max_month = df["calendar_month"].max()
    last_month_per_customer = df.groupby("customer_id")["calendar_month"].transform("max")
    df["is_last_active_month_for_customer"] = df["calendar_month"] == last_month_per_customer
    df["is_dataset_max_month"] = df["calendar_month"] == dataset_max_month

    customer_status = (
        df.groupby("customer_id")["calendar_month"]
        .max()
        .apply(lambda m: "active" if m == dataset_max_month else "canceled")
    )
    df["subscription_status"] = df["customer_id"].map(customer_status)

    # --- Amount paid, in cents (Stripe convention) ---
    df["amount_paid_cents"] = (df["mrr"] * 100).round().astype(int)

    print(f" Dataset max month used for status inference: {dataset_max_month}")
    print(f" Subscription status breakdown:\n{customer_status.value_counts().to_string()}")
    return df


# ==========================================
# STEP 2: ASSIGN STABLE STRIPE-STYLE IDS
# ==========================================
def assign_ids(helper_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds cus_/sub_/in_/il_/txn_ id columns to the helper table. IDs are
    sequential (not random) so they stay stable across reruns and are easy
    to trace back to a given customer while debugging.
    """
    df = helper_df.copy()

    unique_customers = sorted(df["customer_id"].unique())
    customer_index = {cust_id: i + 1 for i, cust_id in enumerate(unique_customers)}
    df["customer_index"] = df["customer_id"].map(customer_index)
    customer_number_text = df["customer_index"].astype(str).str.zfill(6)
    df["stripe_customer_id"] = "cus_" + customer_number_text
    df["stripe_subscription_id"] = "sub_" + customer_number_text

    # Invoice sequence number within each customer (1, 2, 3... in calendar_month order)
    df["invoice_seq"] = df.groupby("customer_id").cumcount() + 1
    df["stripe_invoice_id"] = (
        "in_" + customer_number_text + "_" + df["invoice_seq"].astype(str).str.zfill(3)
    )
    df["stripe_invoice_line_item_id"] = df["stripe_invoice_id"].str.replace("in_", "il_", n=1)
    df["stripe_balance_transaction_id"] = df["stripe_invoice_id"].str.replace("in_", "txn_", n=1)

    return df


# ==========================================
# STEP 3: SLICE INTO THE FIVE STRIPE TABLES
# ==========================================
def build_stripe_customers(df: pd.DataFrame) -> pd.DataFrame:
    one_row_per_customer = df.drop_duplicates(subset="customer_id", keep="first").copy()
    customers = pd.DataFrame(
        {
            "id": one_row_per_customer["stripe_customer_id"],
            "email": one_row_per_customer["customer_index"].apply(
                lambda i: f"customer{i:06d}@example.com"
            ),
            "name": one_row_per_customer["customer_index"].apply(lambda i: f"Customer {i:06d}"),
            "created": one_row_per_customer["subscription_start_date"],
            # Carried through for convenience when tracing back to the source panel -
            # a real Stripe export would not have this column.
            "source_customer_id": one_row_per_customer["customer_id"],
        }
    ).sort_values("id")
    return customers


def build_stripe_subscriptions(df: pd.DataFrame) -> pd.DataFrame:
    one_row_per_customer = df.drop_duplicates(subset="customer_id", keep="first").copy()
    last_period_end = df.groupby("customer_id")["invoice_period_end"].max()
    one_row_per_customer["last_invoice_period_end"] = one_row_per_customer["customer_id"].map(
        last_period_end
    )

    subscriptions = pd.DataFrame(
        {
            "id": one_row_per_customer["stripe_subscription_id"],
            "customer_id": one_row_per_customer["stripe_customer_id"],
            "plan_tier": one_row_per_customer["plan_tier"],
            "status": one_row_per_customer["subscription_status"],
            "created": one_row_per_customer["subscription_start_date"],
            "canceled_at": one_row_per_customer.apply(
                lambda r: r["last_invoice_period_end"]
                if r["subscription_status"] == "canceled"
                else pd.NaT,
                axis=1,
            ),
        }
    ).sort_values("id")
    return subscriptions


def build_stripe_invoices(df: pd.DataFrame) -> pd.DataFrame:
    invoices = pd.DataFrame(
        {
            "id": df["stripe_invoice_id"],
            "customer_id": df["stripe_customer_id"],
            "subscription_id": df["stripe_subscription_id"],
            "amount_paid": df["amount_paid_cents"],
            "currency": "usd",
            "status": "paid",
            "invoice_date": df["invoice_date"],
            "period_start": df["invoice_period_start"],
            "period_end": df["invoice_period_end"],
        }
    ).sort_values(["customer_id", "invoice_date"])
    return invoices


def build_stripe_invoice_line_items(df: pd.DataFrame) -> pd.DataFrame:
    line_items = pd.DataFrame(
        {
            "id": df["stripe_invoice_line_item_id"],
            "invoice_id": df["stripe_invoice_id"],
            "subscription_id": df["stripe_subscription_id"],
            "amount": df["mrr"],
            "description": df.apply(
                lambda r: f"{r['plan_tier']} plan - {r['calendar_month']}", axis=1
            ),
        }
    ).sort_values("id")
    return line_items


def build_stripe_balance_transactions(invoices_df: pd.DataFrame) -> pd.DataFrame:
    fee_cents = (invoices_df["amount_paid"] * STRIPE_PCT_FEE).round().astype(int) + STRIPE_FIXED_FEE_CENTS
    balance_transactions = pd.DataFrame(
        {
            "id": invoices_df["id"].str.replace("in_", "txn_", n=1),
            "source": invoices_df["id"],
            "type": "charge",
            "amount": invoices_df["amount_paid"],
            "fee": fee_cents,
            "net": invoices_df["amount_paid"] - fee_cents,
            "created": invoices_df["invoice_date"],
        }
    ).sort_values("id")
    return balance_transactions


# ==========================================
# ORCHESTRATION
# ==========================================
def main() -> None:
    run_start = time.perf_counter()
    # Optional first argument overrides. Otherwise pick up the newest saas_dataset_*.csv.
    panel_csv_path = sys.argv[1] if len(sys.argv) > 1 else find_latest_csv("saas_dataset_*.csv")

    print(f"Loading source-of-truth panel data from: '{panel_csv_path}'...")
    if not os.path.exists(panel_csv_path):
        raise FileNotFoundError(f"Source panel file not found: {panel_csv_path}")
    with timed_step("read panel csv"):
        panel_df = pd.read_csv(panel_csv_path)
    print(f"Loaded {len(panel_df):,} panel rows, {panel_df['customer_id'].nunique():,} unique customers.")

    print("\nBuilding Stripe-style helper table...")
    with timed_step("backcalc helper"):
        helper_df = build_backcalc_helper(panel_df)
    with timed_step("IDs assigned"):
        helper_df = assign_ids(helper_df)
    # Single helper export, with IDs attached (the earlier ID-less export was overwritten anyway)
    print(f" -> exporting helper table to: '{HELPER_DIR}/'...")
    export_dataframe(helper_df, HELPER_DIR, "stripe_backcalc_helper.csv")

    print("\nBuilding Stripe-style tables...")
    with timed_step("customers"):
        customers_df = build_stripe_customers(helper_df)
    with timed_step("subscriptions"):
        subscriptions_df = build_stripe_subscriptions(helper_df)
    with timed_step("invoices"):
        invoices_df = build_stripe_invoices(helper_df)
    with timed_step("invoice line items"):
        line_items_df = build_stripe_invoice_line_items(helper_df)
    with timed_step("balance transactions"):
        balance_transactions_df = build_stripe_balance_transactions(invoices_df)

    print(f"\nExporting final Stripe-style tables to: '{OUTPUT_DIR}/'...")
    export_dataframe(customers_df, OUTPUT_DIR, "stripe_customers.csv")
    export_dataframe(subscriptions_df, OUTPUT_DIR, "stripe_subscriptions.csv")
    export_dataframe(invoices_df, OUTPUT_DIR, "stripe_invoices.csv")
    export_dataframe(line_items_df, OUTPUT_DIR, "stripe_invoice_line_items.csv")
    export_dataframe(balance_transactions_df, OUTPUT_DIR, "stripe_balance_transactions.csv")
    print(f"\nExecution complete. Total run time: {time.perf_counter() - run_start:.1f}s")


if __name__ == "__main__":
    main()

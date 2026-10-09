"""
Disaggregate customer_month_panel.csv into realistic per-platform marketing
source tables: google_ads.csv, facebook_ads.csv, hubspot_organic_downloads.csv,
rewardful_referrals.csv.

This treats customer_month_panel.csv as source of truth.  The customer_id, 
channel, plan_tier, cohort_month, customer_cac are read from it, 
deduplicated to one row per customer, and works backwards
to produce what each acquisition channel's raw export would plausibly look
like, matching real-world platform schemas (see erd_stripe_to_panel.txt /
real_life_sources_of_saas_dataset.txt for the reasoning, and
weighted_generation.txt for the realism benchmarks applied below).

Usage:
    python disaggregate_cac_to_marketing_sources.py            # newest saas_dataset_*.csv
    python disaggregate_cac_to_marketing_sources.py my_panel.csv   # or name a file

Outputs:
    helper_dfs/unique_customers.csv
    helper_dfs/paid_customers.csv
    helper_dfs/google_customers.csv
    helper_dfs/facebook_customers.csv
    helper_dfs/organic_customers.csv
    helper_dfs/referral_customers.csv
    marketing_outputs/google_ads.csv
    marketing_outputs/facebook_ads.csv
    marketing_outputs/hubspot_organic_downloads.csv
    marketing_outputs/rewardful_referrals.csv
"""

import os
import sys
import glob
import time
from contextlib import contextmanager
import random
import calendar
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ==========================================
# CONFIGURATION CONSTANTS & BENCHMARKS
# ==========================================
OUTPUT_DIR = "marketing_outputs"
HELPER_DIR = "helper_dfs"

DEFAULT_CLICK_THROUGH_RATE = 0.035
DEFAULT_CONVERSION_RATE = 0.02

# Google Ads CTR benchmarks by intent quality (see weighted_generation.txt)
GOOGLE_CTR_BENCHMARKS = {
    "ag_search_brand": 0.150,        # 15.0% - high intent, matches brand
    "ag_search_competitor": 0.018,   # 1.8%  - low relevance, conquesting
}

RANDOM_SEED = 42  # set to None for non-reproducible runs


# ==========================================
# HELPER & DATA LOADING FUNCTIONS
# ==========================================
@contextmanager
def timed_step(label: str):
    """Prints the step name when it starts and how long it took when it ends."""
    print(f" -> {label}", flush=True)
    start = time.perf_counter()
    yield
    print(f"    [{label}] done in {time.perf_counter() - start:.1f}s", flush=True)


def export_helper_dataframe(df: pd.DataFrame, file_name: str) -> None:
    """Exports an intermediate helper DataFrame into helper_dfs/."""
    os.makedirs(HELPER_DIR, exist_ok=True)
    file_path = os.path.join(HELPER_DIR, file_name)
    start = time.perf_counter()
    df.to_csv(file_path, index=False)
    print(f" [Helper DF Export] -> '{file_path}' ({len(df):,} rows, {time.perf_counter() - start:.1f}s)", flush=True)


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


def load_unique_customers_from_panel(panel_csv_path: str) -> pd.DataFrame:
    """
    Loads customer_month_panel.csv and extracts a deduplicated one-row-per-
    customer table of static acquisition dimensions: cohort_month, channel,
    customer_cac, plan_tier. This is the only read of the panel file -
    everything downstream is derived from this, never from a re-simulation.
    """
    print(f"Loading source-of-truth panel data from: '{panel_csv_path}'...")
    if not os.path.exists(panel_csv_path):
        raise FileNotFoundError(f"Source panel file not found: {panel_csv_path}")

    with timed_step("read panel csv"):
        df = pd.read_csv(panel_csv_path)

    required = {"customer_id", "cohort_month", "channel", "customer_cac"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"customer_month_panel.csv is missing required column(s): {sorted(missing)}. "
            "Disaggregation needs customer_id, cohort_month, channel, and customer_cac "
            "to already be present in the panel."
        )

    agg_dict = {
        "cohort_month": ("cohort_month", "first"),
        "channel": ("channel", "first"),
        "customer_cac": ("customer_cac", "first"),
    }
    if "plan_tier" in df.columns:
        agg_dict["plan_tier"] = ("plan_tier", "first")

    with timed_step("one row per customer"):
        unique_customers = df.groupby("customer_id").agg(**agg_dict).reset_index()

    if "plan_tier" not in unique_customers.columns:
        unique_customers["plan_tier"] = np.random.choice(
            ["Basic", "Pro", "Enterprise"], size=len(unique_customers), p=[0.60, 0.30, 0.10]
        )

    print(f"Successfully extracted {len(unique_customers):,} unique customers.")
    export_helper_dataframe(unique_customers, "unique_customers.csv")
    return unique_customers


def assign_organic_conversion_event(plan_tier: str) -> str:
    """
    Assigns a top-of-funnel conversion event conditioned on plan tier.
    Enterprise buyers skew heavily toward high-intent pricing/demo touches;
    self-serve Basic customers skew toward top-of-funnel content.
    """
    events = ["Viewed Pricing", "Downloaded SaaS Model", "Blog Subscription"]

    if plan_tier == "Enterprise":
        weights = [0.80, 0.15, 0.05]
    elif plan_tier == "Pro":
        weights = [0.65, 0.25, 0.10]
    else:  # Basic / Self-Serve
        weights = [0.55, 0.30, 0.15]

    return np.random.choice(events, p=weights)


def generate_conversion_date(cohort_month_str: str) -> datetime:
    """Generates a realistic conversion timestamp within the customer's cohort month."""
    year, month = map(int, str(cohort_month_str).split("-"))
    days_in_month = calendar.monthrange(year, month)[1]

    random_day = random.randint(1, days_in_month)
    random_second = random.randint(0, 86399)
    return datetime(year, month, 1) + timedelta(days=random_day - 1, seconds=random_second)


# ==========================================
# PLATFORM-SPECIFIC GENERATOR FUNCTIONS
# ==========================================
def generate_google_ads_table(google_customers_df: pd.DataFrame) -> pd.DataFrame:
    """Generates raw attribution records for Google Ads conversions."""
    records = []

    for _, row in google_customers_df.iterrows():
        cust_id = row["customer_id"]
        cohort_month = str(row["cohort_month"])
        cac = float(row["customer_cac"])

        event_date = generate_conversion_date(cohort_month)
        date_str = event_date.strftime("%Y-%m-%d")

        # 85% brand / 15% competitor conquesting - see weighted_generation.txt
        ad_group = np.random.choice(["ag_search_brand", "ag_search_competitor"], p=[0.85, 0.15])

        base_ctr = GOOGLE_CTR_BENCHMARKS.get(ad_group, DEFAULT_CLICK_THROUGH_RATE)
        noise = np.random.uniform(0.90, 1.10)
        adjusted_ctr = max(0.001, base_ctr * noise)

        clicks = max(1, int(np.random.poisson(1 / DEFAULT_CONVERSION_RATE)))
        impressions = int(clicks / adjusted_ctr)
        spend = round(cac, 2)

        records.append(
            {
                "google_campaign_id": f"cmp_g_{cohort_month.replace('-', '')}_search",
                "campaign_name": f"google_search_{cohort_month}",
                "ad_group": ad_group,
                "customer_id": cust_id,
                "impressions": impressions,
                "clicks": clicks,
                "spend_usd": spend,
                "conversion_date": date_str,
            }
        )

    return pd.DataFrame(records)


def generate_facebook_ads_table(facebook_customers_df: pd.DataFrame) -> pd.DataFrame:
    """Generates raw attribution records for Facebook/Meta Ads conversions."""
    records = []

    for _, row in facebook_customers_df.iterrows():
        cust_id = row["customer_id"]
        cohort_month = str(row["cohort_month"])
        cac = float(row["customer_cac"])

        event_date = generate_conversion_date(cohort_month)
        date_str = event_date.strftime("%Y-%m-%d")

        ad_set_id = np.random.choice(["lookalike_1pct", "broad_b2b_tech"], p=[0.70, 0.30])
        placement = np.random.choice(["instagram_feed", "facebook_stories"], p=[0.65, 0.35])

        is_lookalike = ad_set_id == "lookalike_1pct"
        fb_ctr = DEFAULT_CLICK_THROUGH_RATE * (1.4 if is_lookalike else 0.8)

        clicks = max(1, int(np.random.poisson(1 / DEFAULT_CONVERSION_RATE)))
        impressions = int(clicks / fb_ctr)
        spend = round(cac, 2)

        records.append(
            {
                "campaign_name": f"fb_retargeting_{cohort_month}",
                "ad_set_id": ad_set_id,
                "placement": placement,
                "customer_id": cust_id,
                "impressions": impressions,
                "clicks": clicks,
                "spend_usd": spend,
                "conversion_date": date_str,
            }
        )

    return pd.DataFrame(records)


def generate_hubspot_table(organic_customers_df: pd.DataFrame) -> pd.DataFrame:
    """Generates raw attribution records for HubSpot organic acquisitions."""
    records = []

    for _, row in organic_customers_df.iterrows():
        cust_id = row["customer_id"]
        cohort_month = str(row["cohort_month"])
        cac = float(row["customer_cac"])
        plan_tier = str(row["plan_tier"])

        event_date = generate_conversion_date(cohort_month)
        timestamp_str = event_date.strftime("%Y-%m-%d %H:%M:%S")

        recent_event = assign_organic_conversion_event(plan_tier)

        records.append(
            {
                "hubspot_contact_id": f"hs_cnt_{cust_id.split('_')[-1]}",
                "customer_id": cust_id,
                "recent_conversion_event": recent_event,
                "lifecycle_stage": "Customer",
                "plan_tier": plan_tier,
                "organic_acquisition_cost_usd": round(cac, 2),
                "signup_timestamp": timestamp_str,
            }
        )

    return pd.DataFrame(records)


def generate_rewardful_table(referral_customers_df: pd.DataFrame) -> pd.DataFrame:
    """Generates raw attribution records for Rewardful affiliate/referral acquisitions."""
    records = []

    for _, row in referral_customers_df.iterrows():
        cust_id = row["customer_id"]
        cohort_month = str(row["cohort_month"])
        cac = float(row["customer_cac"])

        event_date = generate_conversion_date(cohort_month)
        timestamp_str = event_date.strftime("%Y-%m-%d %H:%M:%S")

        affiliate_id = f"aff_{random.randint(100, 999)}"
        records.append(
            {
                "referral_id": f"ref_{cust_id.split('_')[-1]}",
                "customer_id": cust_id,
                "affiliate_id": affiliate_id,
                "referral_link_used": f"https://myapp.com?via={affiliate_id}",
                "commission_amount_usd": round(cac, 2),
                "conversion_timestamp": timestamp_str,
            }
        )

    return pd.DataFrame(records)


# ==========================================
# ORCHESTRATION & EXPORT
# ==========================================
def generate_attribution_tables(customers_df: pd.DataFrame):
    """
    Segments customers into channel/platform subsets, exports intermediate
    helper DataFrames to helper_dfs/, and orchestrates platform table
    generation.
    """
    print("\nSegmenting customer subsets and exporting intermediate helper DataFrames...")

    customers_df = customers_df.copy()
    customers_df["channel_clean"] = customers_df["channel"].astype(str).str.lower().str.strip()

    # 1. Paid Ads: filter, then route to Google vs Facebook
    paid_channels = ["ads", "paid_ads", "paid search", "paid social"]
    paid_mask = customers_df["channel_clean"].isin(paid_channels)
    paid_df = customers_df[paid_mask].copy()

    if not paid_df.empty:
        paid_df["ad_platform"] = np.random.choice(["Google", "Facebook"], size=len(paid_df), p=[0.60, 0.40])
        google_customers = paid_df[paid_df["ad_platform"] == "Google"].copy()
        facebook_customers = paid_df[paid_df["ad_platform"] == "Facebook"].copy()
    else:
        google_customers = pd.DataFrame(columns=customers_df.columns)
        facebook_customers = pd.DataFrame(columns=customers_df.columns)

    # 2. Organic / SEO -> HubSpot
    organic_channels = ["organic", "seo", "content"]
    organic_customers = customers_df[customers_df["channel_clean"].isin(organic_channels)].copy()

    # 3. Referral / Affiliate -> Rewardful
    referral_channels = ["referral", "affiliate"]
    referral_customers = customers_df[customers_df["channel_clean"].isin(referral_channels)].copy()

    unmatched = customers_df[
        ~customers_df["channel_clean"].isin(paid_channels + organic_channels + referral_channels)
    ]
    if not unmatched.empty:
        unmatched_channels = sorted(unmatched["channel"].unique().tolist())
        print(
            f" [Warning] {len(unmatched):,} customers have channel values not mapped to any "
            f"platform and will be excluded from every output table: {unmatched_channels}"
        )

    export_helper_dataframe(paid_df, "paid_customers.csv")
    export_helper_dataframe(google_customers, "google_customers.csv")
    export_helper_dataframe(facebook_customers, "facebook_customers.csv")
    export_helper_dataframe(organic_customers, "organic_customers.csv")
    export_helper_dataframe(referral_customers, "referral_customers.csv")

    with timed_step(f"google ads table ({len(google_customers):,} customers)"):
        google_df = generate_google_ads_table(google_customers)
    with timed_step(f"facebook ads table ({len(facebook_customers):,} customers)"):
        facebook_df = generate_facebook_ads_table(facebook_customers)
    with timed_step(f"hubspot table ({len(organic_customers):,} customers)"):
        hubspot_df = generate_hubspot_table(organic_customers)
    with timed_step(f"rewardful table ({len(referral_customers):,} customers)"):
        rewardful_df = generate_rewardful_table(referral_customers)

    return google_df, facebook_df, hubspot_df, rewardful_df


def export_tables_to_csv(
    google_df: pd.DataFrame, facebook_df: pd.DataFrame, hubspot_df: pd.DataFrame, rewardful_df: pd.DataFrame
) -> None:
    """Exports all final platform attribution DataFrames to marketing_outputs/."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\nExporting final marketing attribution tables to: '{OUTPUT_DIR}/'...")

    if not google_df.empty:
        start = time.perf_counter()
        google_df.to_csv(os.path.join(OUTPUT_DIR, "google_ads.csv"), index=False)
        print(f" -> google_ads.csv ({len(google_df):,} rows, {time.perf_counter() - start:.1f}s)", flush=True)
    if not facebook_df.empty:
        start = time.perf_counter()
        facebook_df.to_csv(os.path.join(OUTPUT_DIR, "facebook_ads.csv"), index=False)
        print(f" -> facebook_ads.csv ({len(facebook_df):,} rows, {time.perf_counter() - start:.1f}s)", flush=True)
    if not hubspot_df.empty:
        start = time.perf_counter()
        hubspot_df.to_csv(os.path.join(OUTPUT_DIR, "hubspot_organic_downloads.csv"), index=False)
        print(f" -> hubspot_organic_downloads.csv ({len(hubspot_df):,} rows, {time.perf_counter() - start:.1f}s)", flush=True)
    if not rewardful_df.empty:
        start = time.perf_counter()
        rewardful_df.to_csv(os.path.join(OUTPUT_DIR, "rewardful_referrals.csv"), index=False)
        print(f" -> rewardful_referrals.csv ({len(rewardful_df):,} rows, {time.perf_counter() - start:.1f}s)", flush=True)

    print("\nExecution complete. Helper DataFrames (helper_dfs/) and final raw tables (marketing_outputs/) saved.")


def main() -> None:
    run_start = time.perf_counter()
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

    # Optional first argument overrides. Otherwise pick up the newest saas_dataset_*.csv.
    panel_csv_path = sys.argv[1] if len(sys.argv) > 1 else find_latest_csv("saas_dataset_*.csv")

    unique_customers_df = load_unique_customers_from_panel(panel_csv_path)
    google_df, facebook_df, hubspot_df, rewardful_df = generate_attribution_tables(unique_customers_df)
    export_tables_to_csv(google_df, facebook_df, hubspot_df, rewardful_df)
    print(f"Total run time: {time.perf_counter() - run_start:.1f}s")


if __name__ == "__main__":
    main()

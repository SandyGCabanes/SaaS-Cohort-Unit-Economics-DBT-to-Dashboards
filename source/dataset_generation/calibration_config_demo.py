"""
calibration_config_demo.py

DEMO ONLY
---------
These are dummy filler values. They exist so saas_generation_v9_demo.py can
run end to end. Curves are flat. Every channel and every plan tier behaves
about the same. The output does not resemble the final curves, prices or
ratios used in the repo.

Contact the author if you need a demo of the actual code.

Notes for readers
-----------------
- Every name below is imported by saas_generation_v9_demo.py.
- Channel mix shares and plan mix shares each add up to 1.0.
- Retention and expansion anchors are kept simple on purpose.
"""

# --- Reproducibility & cohort calendar defaults ---------------------------
SEED = 7
DEFAULT_START_MONTH = "2022-01"
DEFAULT_NUM_MONTHS = 36

# --- CLV horizon -------------------------------------------------------------
CLV_HORIZON_MONTHS = 24

# --- Growth/trend tapering ---------------------------------------------------
GROWTH_CAP_MONTHS = 24

# --- Baseline signup volume and trends ---------------------------------------
BASE_SIGNUPS = 30
SIGNUP_GROWTH = 0.0
SIGNUP_NOISE = 0.05

# --- Cohort-level retention noise ---------------------------------------------
COHORT_RET_NOISE = 1.0

# --- Customer-level revenue noise and contraction -----------------------------
MRR_NOISE = 0.05
CONTRACTION_PROB = 0.02
CONTRACTION_RANGE = (0.10, 0.20)

# --- CAC noise -----------------------------------------------------------------
CAC_NOISE = 0.03

# --- Channel configuration (identical dummy values for all three) ---------------
CHANNELS = {
    "Ads": {
        "retention_anchors": {0: 1.00, 1: 0.92, 12: 0.90, 83: 0.90},
        "base_cac": 50.0,
        "cac_trend": 0.00,
        "mix_start": 0.34,
        "mix_end": 0.34,
        "expansion_scaler": 1.00,
    },
    "Organic": {
        "retention_anchors": {0: 1.00, 1: 0.92, 12: 0.90, 83: 0.90},
        "base_cac": 50.0,
        "cac_trend": 0.00,
        "mix_start": 0.33,
        "mix_end": 0.33,
        "expansion_scaler": 1.00,
    },
    "Referral": {
        "retention_anchors": {0: 1.00, 1: 0.92, 12: 0.90, 83: 0.90},
        "base_cac": 50.0,
        "cac_trend": 0.00,
        "mix_start": 0.33,
        "mix_end": 0.33,
        "expansion_scaler": 1.00,
    },
}

# --- Plan tier configuration (dummy prices, no expansion) -----------------------
PLANS = {
    "Basic": {
        "base_arpu": 10.0,
        "retention_modifier": 0.0,
        "mix_start": 0.34,
        "mix_end": 0.34,
        "expansion_anchors": {0: 1.00, 83: 1.00},
        "cac_mult": 1.0,
    },
    "Pro": {
        "base_arpu": 30.0,
        "retention_modifier": 0.0,
        "mix_start": 0.33,
        "mix_end": 0.33,
        "expansion_anchors": {0: 1.00, 83: 1.00},
        "cac_mult": 1.0,
    },
    "Enterprise": {
        "base_arpu": 100.0,
        "retention_modifier": 0.0,
        "mix_start": 0.33,
        "mix_end": 0.33,
        "expansion_anchors": {0: 1.00, 83: 1.00},
        "cac_mult": 1.0,
    },
}

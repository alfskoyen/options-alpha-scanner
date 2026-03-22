"""
data.py
────────────────────────────────────────────────────────────────────────
Data loader for the Options Screening Dashboard.

How it works
────────────
1. Your scan pipeline (scan_loop.py / Jupyter) runs against Alpha Vantage
   and saves a dated CSV to the data/ directory:
       data/option_scores_YYYY_MM_DD.csv

2. load_data() picks up the most recent CSV automatically.

3. prep_data() adds any derived columns needed by the dashboard.

To connect a live feed or database later, replace load_data() only.
Everything downstream reads from the prepared DataFrame.

Usage:
    from data import load_data, prep_data, get_scan_meta
    df   = prep_data(load_data())
    meta = get_scan_meta(df)
"""

import os
import glob
import pandas as pd
import numpy as np


# ── CONFIG ────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# ── LOADER ───────────────────────────────────────────────────────
def load_data(path: str = None) -> pd.DataFrame:
    """
    Load the most recent scan CSV from the data/ directory.

    Parameters
    ----------
    path : optional explicit file path — overrides auto-discovery

    Returns
    -------
    pd.DataFrame — raw scan output, unmodified

    Raises
    ------
    FileNotFoundError if no CSV found in data/
    """
    if path:
        print(f"Loading: {path}")
        return pd.read_csv(path)

    pattern = os.path.join(DATA_DIR, "option_scores_*.csv")
    files   = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No scan CSV found in {DATA_DIR}/\n"
            f"Expected files matching: option_scores_YYYY_MM_DD.csv\n"
            f"Run your scan pipeline first to generate the data file."
        )

    latest = files[-1]
    print(f"Loading: {os.path.basename(latest)}")
    return pd.read_csv(latest)


# ── PREP ─────────────────────────────────────────────────────────
def prep_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all derived columns and cleaning needed by the dashboard.
    Called once at app startup — result passed to all chart modules.

    Derived columns added:
      quadrant_short     : Q1 / Q2 / Q3 / Q4 extracted from full label
      scan_date          : formatted date string
      *_display          : 99th-percentile clipped versions of extreme
                           vol columns for cleaner chart scaling
    """
    out = df.copy()

    # ── Quadrant short key ────────────────────────────────────────
    if "quadrant" in out.columns:
        out["quadrant_short"] = out["quadrant"].str[:2].where(
            out["quadrant"].notna(), ""
        )

    # ── Scan date ─────────────────────────────────────────────────
    if "date" in out.columns:
        out["scan_date"] = pd.to_datetime(
            out["date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")

    # ── Clip extreme outliers for display ─────────────────────────
    # Leveraged ETFs (AGQ, SOXL, TECS etc.) have extreme vol values
    # that compress chart scales. Clipped versions used in charts only
    # — original columns preserved for scoring/filtering.
    clip_cols = [
        "HV_20", "HV_30", "HV_60",
        "avg_spike_pct_60", "max_spike_pct_60",
        "relative_vol_spy", "relative_vol_qqq",
    ]
    for col in clip_cols:
        if col in out.columns:
            p99 = out[col].quantile(0.99)
            out[f"{col}_display"] = out[col].clip(upper=p99)

    return out


# ── METADATA ─────────────────────────────────────────────────────
def get_scan_meta(df: pd.DataFrame) -> dict:
    """
    Return metadata about the loaded scan for the app header.

    Returns
    -------
    dict:
      date        : scan date string
      n_symbols   : total symbol count
      q_counts    : { Q1: n, Q2: n, Q3: n, Q4: n }
      top_symbol  : symbol with highest premium_score
    """
    meta = {
        "date":       df["scan_date"].iloc[0] if "scan_date" in df.columns else "—",
        "n_symbols":  len(df),
        "q_counts":   {},
        "top_symbol": "—",
    }

    if "quadrant_short" in df.columns:
        meta["q_counts"] = df["quadrant_short"].value_counts().to_dict()

    if "premium_score" in df.columns:
        top = df.nlargest(1, "premium_score")
        if not top.empty:
            meta["top_symbol"] = top["symbol"].iloc[0]

    return meta

"""
score_universe.py
------------------
The scoring methodology is a blend of two risk scores across two axes:
Premium and Risk. 

  PREMIUM — how much premium is available, efficiency-weighted
  RISK    — how dangerous/expensive the vol environment is

Also computes Term Structure metrics per symbol:
  - premium_slope, iv_slope, slope_divergence
  - percentile ranks vs universe for each

Quadrant assignment (median split):
  Q1 High Premium / Low Risk  <- target
  Q2 High Premium / High Risk
  Q3 Low Premium  / Low Risk
  Q4 Low Premium  / High Risk
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()


### --- Parameters: Weights -----------------------------------------------

# DTE weights for premium score — shorter term to experiation = higher weight (theta focus)
DTE_WEIGHTS = {
    '14':       0.50,
    '30':       0.30,
    'over60_1': 0.15,
    'over60_2': 0.05,
}

STRIKE_WEIGHTS = {
    'atm':      0.20,
    'slight':   0.40,
    'moderate': 0.30,
    'far':      0.15,
}

# Risk component weights
RISK_WEIGHTS = {
    'iv_hv_ratio': 0.2,
    'hv_30':       0.25,
    'spike_wt_score': 0.4,
    'slope':       0.15,
}

# Term Structure weights — ATM anchored, small Slight contribution
TERM_STRUCTURE_WEIGHTS = {
    'atm':    0.80,
    'slight': 0.20,
}

# Premium Efficiency Signal thresholds
# ratio >= RATIO_RICH_THRESHOLD     -> "Rich"    (IV trading above realized vol)
# prem_per_iv >= PREM_EFF_THRESHOLD -> "Efficient" (collecting enough vs theoretical move)
RATIO_RICH_THRESHOLD = 1.20   # IV/HV ratio above this = Rich
PREM_EFF_THRESHOLD   = 0.60   # prem_per_iv_primary above this = Efficient


### --- Normalization helpers ---------------------------------

def pct_rank(series):
    return series.rank(pct=True)

### --------------------------------------------------------------
### --- Premium Score Builder ------------------------------------

def compute_premium_score(df):
    """
    Weighted composite premium score across DTE windows and delta/strike buckets.
    Two sub-scores combined:
      1. Raw premium score    — strike bucket / weighted avg_premium_pct per DTE, DTE-weighted sum
      2. Efficiency score     — prem_per_iv_primary weighted across DTE windows
                                (how much premium relative to what IV implies)
    Final = 0.60 * raw_score + 0.40 * efficiency_score, standardized.
    """
    dte_list = ['14', '30', 'over60_1', 'over60_2']
    buckets  = list(STRIKE_WEIGHTS.keys())

    # -- raw premium composite ------------------------------------------------
    raw_scores = pd.Series(0.0, index=df.index)
    for dte, dt_weight in DTE_WEIGHTS.items():
        wp = pd.Series(0.0, index=df.index)
        for strike_bucket, st_weight in STRIKE_WEIGHTS.items():
            col = 'premium_{}_{}'.format(strike_bucket, dte)  ## create prem. column per strike / dta buckets
            if col in df.columns:
                wp += df[col].fillna(0) * st_weight  ## weighed score is premium * strike weight
        raw_scores += wp * dt_weight                 ## raw score is weighted strike * dte weight

    # -- efficiency composite (prem_per_iv_primary) ---------------------------
    eff = pd.Series(0.0, index=df.index)
    for dte, dw in DTE_WEIGHTS.items():
        col = 'prem_per_iv_primary_{}'.format(dte)
        if col in df.columns:
            eff += df[col].fillna(0) * dw

    # -- standardize each component -------------------------------------------
    scaler = StandardScaler()

    raw_scaled = scaler.fit_transform(raw_scores.values.reshape(-1, 1)).flatten()
    eff_scaled = scaler.fit_transform(eff.values.reshape(-1, 1)).flatten()

    # -- combine --------------------------------------------------------------
    combined = 0.60 * raw_scaled + 0.40 * eff_scaled

    # -- standardize final combined score -------------------------------------
    final = scaler.fit_transform(pd.Series(combined).values.reshape(-1, 1)).flatten()

    return pd.Series(final, index=df.index).round(4)


### ---------------------------------------------------------------
### --- Risk Score Builder-----------------------------------------

def compute_risk_score(df):
    """
    Composite risk score — higher = more risk = penalizes premium score.
    Components:
      iv_hv_ratio     : asymmetric distance from IV/HV fair value (1.0)
                        IV < HV penalized 2x harder than IV > HV
      hv_30           : absolute realized vol level (HV_30 only)
      spike_wt_score  : combined freq x magnitude, weighted 0.4*spike_30 + 0.6*spike_60
      slope           : term structure slope of IV/HV ratios across DTE windows
                        negative slope (near > far) = short term stress = higher risk
                        positive slope (far > near) = small risk signal
    """
    # -- iv_hv_ratio component ------------------------------------------------
    ratio_cols = [c for c in df.columns if c.startswith('ratio_')]  ## hit each iv/hv ratio col. across DTE
    avg_ratio  = df[ratio_cols].mean(axis=1).fillna(1.0)  ## Avg. DTE window ratios into 1
    iv_hv_risk = np.where(
        avg_ratio < 1.0,
        (1.0 - avg_ratio) * 2.0,   # IV < HV — penalize harder
        (avg_ratio - 1.0) * 0.5    # IV > HV — softer penalty
    )

    # -- spike —> weighted blend of 30 and 60 day windows ------------
    spike_30_combined = df['spike_ratio_30'].fillna(0) * np.log1p(df['max_spike_pct_30'].fillna(0))
    spike_60_combined = df['spike_ratio_60'].fillna(0) * np.log1p(df['max_spike_pct_60'].fillna(0))
    spike_blended     = 0.7 * spike_30_combined + 0.3 * spike_60_combined

    # -- IV slope component ------------------------------------------------------
    # negative slope = near IV > far IV = short term stress = higher risk
    # positive slope = far IV > near IV = small risk signal
    raw_slope = df['ratio_14'].fillna(1.0) - df['ratio_over60_1'].fillna(1.0)
    slope_risk = np.where(
        raw_slope > 0,
        raw_slope * 2.0,    # negative slope (near > far) — penalize harder
        raw_slope.abs() * 0.3   # positive slope (far > near) — small signal
    )

    # -- assemble risk features ----------------------------------------------------
    features = pd.DataFrame({
        'iv_hv_ratio': iv_hv_risk,
        'hv_30':       df['HV_30'].fillna(0),
        'spike_wt_score': spike_blended,
        'slope':       slope_risk,
    }, index=df.index)

    # -- standardize and weight -----------------------------------------------
    scaler    = StandardScaler()
    scaled    = scaler.fit_transform(features)
    scaled_df = pd.DataFrame(scaled, columns=features.columns, index=df.index)

    risk = (
        scaled_df['iv_hv_ratio'] * RISK_WEIGHTS['iv_hv_ratio'] +
        scaled_df['hv_30']       * RISK_WEIGHTS['hv_30']       +
        scaled_df['spike_wt_score'] * RISK_WEIGHTS['spike_wt_score'] +
        scaled_df['slope']       * RISK_WEIGHTS['slope']
    )

    return risk.round(4)


### =============================================================================
### --- Term Structure ---

Term_Struc_X = [14, 30, 63, 91]   # nominal DTE x-axis for term structure regression

def term_slope(x, y):
    """
    Linear regression slope for term structure.
    Runs on available points if at least 3 of 4 DTE windows present.
    Returns np.nan if fewer than 3 points available.
    """
    pairs = [(xi, yi) for xi, yi in zip(x, y) if not np.isnan(yi)]  ## Build tuple with x, y points submitted 
    if len(pairs) < 3:
        return np.nan
    xs, ys = zip(*pairs)
    s, _, _, _, _ = stats.linregress(xs, ys)

    return s

def compute_term_structure(df):
    """
    Linear regression slope of weighted premium and ATM IV across all 4 DTE
    windows, using actual DTE values as x-axis.

    Metrics per symbol:
      premium_slope     — how fast bucket-weighted premium grows with DTE
      iv_slope          — how fast ATM IV grows with DTE
      slope_divergence  — premium_slope - iv_slope
                          positive = premium outpacing IV (opportunity signal)

    All three ranked as percentiles vs universe.
    """

    dte_labels = ['14', '30', 'over60_1', 'over60_2']   # separate from x-axis list
    records    = []

    for _, row in df.iterrows():
        premium_y = []
        iv_y      = []

        for strike_cat, act_days in zip(['14', '30', 'over60_1', 'over60_2'], Term_Struc_X):
    
            weighted_prem = sum(
                row.get('premium_{}_{}'.format(b, strike_cat), 0) * bw
                for b, bw in TERM_STRUCTURE_WEIGHTS.items()
            )
            premium_y.append(weighted_prem)
            iv_y.append(row.get('atm_iv_{}'.format(strike_cat), np.nan))

        prem_slope = term_slope(Term_Struc_X, premium_y) ## Run term slope method, push standard Xs
        iv_slope   = term_slope(Term_Struc_X, iv_y)
        div        = prem_slope - iv_slope if not (np.isnan(prem_slope) or np.isnan(iv_slope)) else np.nan

        records.append({
            'symbol':           row['symbol'],
            'premium_slope':    round(prem_slope, 6) if not np.isnan(prem_slope) else np.nan,
            'iv_slope':         round(iv_slope,   6) if not np.isnan(iv_slope)   else np.nan,
            'slope_divergence': round(div,         6) if not np.isnan(div)        else np.nan,
            'wp_14':            round(premium_y[0], 4),
            'wp_30':            round(premium_y[1], 4),
            'wp_over60_1':      round(premium_y[2], 4),
            'wp_over60_2':      round(premium_y[3], 4),
        })

    ts = pd.DataFrame(records)
    ts['premium_slope_pct'] = pct_rank(ts['premium_slope']).round(3)
    ts['iv_slope_pct']      = pct_rank(ts['iv_slope']).round(3)
    ts['slope_div_pct']     = pct_rank(ts['slope_divergence']).round(3)

    return ts


# =============================================================================
# --- Quadrant Assignment ------------------------------------------


def assign_quadrant(premium_score, risk_score):
    pm = premium_score.median()
    rm = risk_score.median()

    conditions = [
        (premium_score >= pm) & (risk_score <  rm),
        (premium_score >= pm) & (risk_score >= rm),
        (premium_score <  pm) & (risk_score <  rm),
        (premium_score <  pm) & (risk_score >= rm),
    ]

    labels = [
        'Q1 High Premium / Low Risk',
        'Q2 High Premium / High Risk',
        'Q3 Low Premium  / Low Risk',
        'Q4 Low Premium  / High Risk',
    ]
    return np.select(conditions, labels, default='Unclassified')


# =============================================================================
# --- Premium Efficiency Signal (Per IV)-------------------------------------

def _prem_efficiency_signal(ratio, prem_per_iv):
    """
    Combine IV/HV ratio and premium efficiency into a single categorical signal.
 
    Four outcomes:
      Rich + Efficient  — IV rich vs history AND collecting well vs theoretical move
      Rich + Thin       — IV rich but premium not materializing (AGQ pattern)
      Cheap + Efficient — IV cheap vs history but collecting efficiently (opportunity)
      Cheap + Thin      — IV cheap and premium thin, nothing to collect
    """
    if pd.isna(ratio) or pd.isna(prem_per_iv):
        return None
    rich      = ratio     >= RATIO_RICH_THRESHOLD
    efficient = prem_per_iv >= PREM_EFF_THRESHOLD
    if rich  and efficient:  return 'Rich + Efficient'
    if rich  and not efficient: return 'Rich + Thin'
    if not rich and efficient:  return 'Cheap + Efficient'
    return                              'Cheap + Thin'
 

# =============================================================================
# --- Master Scorer - Score Universe ---------->

def score_universe(master_df):
    df = master_df.copy()

    df['premium_score'] = compute_premium_score(df)
    df['risk_score']    = compute_risk_score(df)
    df['quadrant']      = assign_quadrant(df['premium_score'], df['risk_score'])

    # -- Call Term Structure ------------------------------------------------------- 
    ts = compute_term_structure(df)  ## Run term structure and slope divergence

    # -- Merge all to single DF -----------------------------------------------
    df = df.merge(ts, on='symbol', how='left')

    ## -- Determine premium efficiency signal per DTE window (assign) -----------------------------
    for dte in ['14', '30', 'over60_1', 'over60_2']:
        ratio_col  = 'ratio_{}'.format(dte)
        prem_col   = 'prem_per_iv_primary_{}'.format(dte)
        signal_col = 'prem_efficiency_signal_{}'.format(dte)  ## naming of new metric
        if ratio_col in df.columns and prem_col in df.columns:
            df[signal_col] = df.apply(
                lambda r: _prem_efficiency_signal(r[ratio_col], r[prem_col]), axis=1
            )

    # -- Spike -> universe-relative spike signal ---------------------------------------
    # blended score: spike ratio is count of spikes over expected count. 
    # spike_blended score is a mix of frequency × log(magnitude) across 30 and 60 day windows
    spike_score_30 = df['spike_ratio_30'].fillna(0) * np.log1p(df['max_spike_pct_30'].fillna(0))
    spike_score_60 = df['spike_ratio_60'].fillna(0) * np.log1p(df['max_spike_pct_60'].fillna(0))
    spike_blended  = 0.7 * spike_score_30 + 0.3 * spike_score_60

    spike_pct = pct_rank(spike_blended)  ## Ranked perspective on Spikes across Universe

    def spike_signal_universe(pct):
        if pct >= 0.90: return 'Extreme'    # top 10% of universe
        if pct >= 0.75: return 'Elevated'   # top 25%
        if pct >= 0.50: return 'Moderate'   # top 50%
        return                 'Normal'     # bottom 50%

    df['spike_score_universe']  = spike_blended.round(4)  ## blended freq. / mag. score
    df['spike_pct_universe']    = spike_pct.round(3)      ## ranked pct value across universe
    df['spike_signal_universe'] = spike_pct.apply(spike_signal_universe)

    # -- HV and relative vol percentile ranks ---------------------------------
    df['HV_30_pct']            = pct_rank(df['HV_30'].fillna(0)).round(3)
    df['relative_vol_spy_pct'] = pct_rank(df['relative_vol_spy'].fillna(1.0)).round(3)
    df['relative_vol_qqq_pct'] = pct_rank(df['relative_vol_qqq'].fillna(1.0)).round(3)

    # -- sort: Q1 first, then premium score descending within quadrant
    q_order = {
        'Q1 High Premium / Low Risk':  0,
        'Q2 High Premium / High Risk': 1,
        'Q3 Low Premium  / Low Risk':  2,
        'Q4 Low Premium  / High Risk': 3,
    }
    df['_q'] = df['quadrant'].map(q_order)
    df = df.sort_values(['_q', 'premium_score'], ascending=[True, False])
    df = df.drop(columns=['_q']).reset_index(drop=True)

    # -- reorder columns — symbol, date, scores first, then everything else
    priority_cols = ['symbol', 'date', 'premium_score', 'risk_score', 'quadrant']
    remaining     = [c for c in df.columns if c not in priority_cols]
    df_final = df[priority_cols + remaining]

    return df_final


# =============================================================================
# Summary View
# =============================================================================

# def score_summary(scored_df):
#     """
#     Clean summary — key columns only for quick review.
#     """
#     cols = [
#         'symbol', 'quadrant', 'premium_score', 'risk_score',
#         # straddle efficiency
#         'prem_per_iv_primary_14', 'prem_per_iv_primary_30',
#         'prem_per_hv30_14',       'prem_per_hv30_30',
#         # term structure
#         'premium_slope', 'iv_slope', 'slope_divergence', 'slope_div_pct',
#         # risk
#         'HV_30', 'ratio_30', 'spike_ratio', 'spike_signal',
#     ]
#     available = [c for c in cols if c in scored_df.columns]
#     return scored_df[available].reset_index(drop=True)


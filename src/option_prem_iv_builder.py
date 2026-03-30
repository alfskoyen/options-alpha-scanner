
"""
Python file to pull in API Option Data for a Symbol 'X' and output a DataFrame of 
sadfdsaf
asdfdsa

"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# if __name__ == '__main__':
#     # test code here

### Hard Coded Parameters ------------------------------------------------------
DTE_WINDOWS   = [14, 30, 'over60_1', 'over60_2']        ## target expirations in days
DTE_TOLERANCE = 13                                      ## ± days to accept around each target
OVER60_MIN    = 60                                      ## minimum days out for the dynamic long-dated window

DELTA_BUCKETS = {
    'ATM':      (0.40, 0.60),   # ~50% probability ITM
    'Slight':   (0.25, 0.40),   # ~25-40% probability
    'Moderate': (0.15, 0.25),   # ~15-25% probability
    'Far':      (0.05, 0.15),   # ~5-15% probability
}

MIN_OI_BY_BUCKET = {
    'ATM':      0,    # vega-only — ATM is always the most liquid strike
    'Slight':   1,    # some OI required
    'Moderate': 2,    # meaningful OI needed
    'Far':      5,   # far OTM needs real open interest to be tradeable
        }       

# MIN_OPEN_INTEREST = 2                # filter illiquid contracts
MIN_VEGA          = 0.001              # filter contracts with no vol sensitivity


### --- Step 1 Parse & clean raw contracts -----------------
def parse_contracts(raw: list[dict]):
    """
    Convert raw Alpha Vantage list-of-dicts to a typed DataFrame.
    Drops rows with missing or unparseable values.
    """
    df = pd.DataFrame(raw)

    numeric_cols = [
        'strike', 'last', 'mark', 'bid', 'ask',
        'volume', 'open_interest',
        'implied_volatility', 'delta', 'gamma', 'theta', 'vega', 'rho'
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['expiration'] = pd.to_datetime(df['expiration'])
    df['date']       = pd.to_datetime(df['date'])

    # drop rows where critical fields are null
    df.dropna(subset=['strike', 'implied_volatility', 'vega', 'expiration'], inplace=True)

    return df


 ### --- Step 2 - Identify the appropriate Days to Expiration (DTE) Date 
def get_target_friday_14d(current_date: datetime) -> datetime:
    """
    Weekday-aware target for the 14-day window. Options expire on Fridays, so we snap to the appropriate Friday:
      Mon / Tue / Wed  →  Friday of NEXT week  (~9–11 days out)
      Thu / Fri        →  Friday of the week AFTER next  (~8–15 days out)
      weekday() returns: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    """
    dow = current_date.weekday()

    if dow <= 2:   # Mon/Tue/Wed → next Friday
        days_until_friday = (4 - dow) + 7   # skip THIS week's Friday, go to next
    else:   # Thu/Fri → the Friday after next
        days_until_friday = (4 - dow) + 14

    return current_date + timedelta(days=days_until_friday)

def get_over60_expirations(unique_expirations, current_date, min_dte=OVER60_MIN, count=2):
    """
    Return the next `count` expirations beyond min_dte days. Naturally lands on standard monthly / LEAPS expirations
    (e.g. May 15, June 18) without hardcoding dates.
    """
    cutoff = pd.Timestamp(current_date + timedelta(days=min_dte))
    future = [exp for exp in unique_expirations if exp > cutoff]
    return future[:count]


def find_target_expirations(df: pd.DataFrame,
                         current_date: datetime,
                         dte_windows: list[int] = DTE_WINDOWS,
                         tolerance: int = DTE_TOLERANCE) -> dict[int, datetime]:
    """  For each DTE window, find the actual expiration date in the chain.

      14        : weekday-aware Friday snapping
      30, 45    : mechanical offset, nearest chain expiry within tolerance
      over60_1  : first standard expiration beyond 60 days  (e.g. May 15)
      over60_2  : second standard expiration beyond 60 days (e.g. June 18)
    """
    
    unique_expirations = sorted(df['expiration'].unique())
    result = {}

    ### Call method to resolve the two long-dated windows up front -> 
    over60_dates = get_over60_expirations(unique_expirations, current_date)
    result['over60_1'] = over60_dates[0] if len(over60_dates) >= 1 else None
    result['over60_2'] = over60_dates[1] if len(over60_dates) >= 2 else None

    for target_dte in dte_windows:

        if target_dte in ('over60_1', 'over60_2'):
            continue  # already resolved above
        elif target_dte == 14:
            target_date = get_target_friday_14d(current_date)
        else:
            target_date = current_date + timedelta(days=target_dte)

        candidates = [
            exp for exp in unique_expirations
            if abs((exp - pd.Timestamp(target_date)).days) <= tolerance
        ]

        # if target_dte != 14:   ### Added to see that the correct Target DTE and Candidate dates were showing
        #     print(target_dte)
        #     print(pd.Timestamp(target_date))
        #     print(candidates)

        if candidates:
            best = min(candidates, key=lambda e: abs((e - pd.Timestamp(target_date)).days))
            result[target_dte] = best
        else:
            result[target_dte] = None  # no expiration found near this window

    return result


### --- Step 3: Filter to liquid, meaningful contracts ----------
def filter_contracts(df, option_type='put'):
    """
    Keep only contracts that will produce meaningful premium signals:
    - correct option type (put / call)
    - sufficient open interest — threshold scales with abs(delta)
      so ATM contracts (high delta) require less OI than far OTM
    - non-zero vega (has vol sensitivity)
    - positive IV
 
    OI threshold uses abs(delta) — consistent with delta bucketing.
    Delta is already parsed to numeric in parse_contracts.
    spot parameter retained for API compatibility but no longer used
    for OI threshold computation.
    """
    base = (
        (df['type']               == option_type) &
        (df['vega']               >= MIN_VEGA)     &
        (df['implied_volatility']  > 0)
    )
 
    # OI threshold based on abs(delta) — mirrors DELTA_BUCKETS boundaries
    abs_delta = df['delta'].abs()
 
    def oi_threshold(d):
        if d >= 0.40:  return MIN_OI_BY_BUCKET['ATM']
        if d >= 0.25:  return MIN_OI_BY_BUCKET['Slight']
        if d >= 0.15:  return MIN_OI_BY_BUCKET['Moderate']
        return                MIN_OI_BY_BUCKET['Far']
 
    min_oi    = abs_delta.apply(oi_threshold)
    oi_filter = df['open_interest'] >= min_oi
 
    return df[base & oi_filter].copy()


### --- Step 4: Compute normalized premium ----------
def compute_normalized_premium(df: pd.DataFrame, spot: float) -> pd.DataFrame:
    """
    Add key derived columns:
    - otm_distance    : how far the strike is from spot as a fraction (puts: spot > strike)
    - intrinsic       : intrinsic value of the contract
    - extrinsic       : time/vol premium (what you actually collect above intrinsic)
    - premium_pct     : extrinsic / spot — THE normalized cross-ticker metric
    - mid_price       : (bid + ask) / 2 — cleaner than 'last' which can be stale
    """
    df = df.copy()
    df['mid_price'] = (df['bid'] + df['ask']) / 2

    # for puts: intrinsic = max(0, strike - spot)
    df['intrinsic'] = (df['strike'] - spot).clip(lower=0)
    df['extrinsic'] = (df['mid_price'] - df['intrinsic']).clip(lower=0)

    # normalized: extrinsic as % of spot — comparable across any ticker
    df['premium_pct']   = df['extrinsic'] / spot

    # OTM distance: for puts, how far below spot is the strike
    df['otm_distance']  = (spot - df['strike']) / spot

    return df


### --- Step 5: Assign Strike Distance buckets ────────────────
def assign_buckets(df: pd.DataFrame,
                   buckets: dict = DELTA_BUCKETS) -> pd.DataFrame:
    """
    Label each contract with its strike bucket based on abs(delta).
 
    Delta bucketing equalizes strike selection across the universe —
    a 0.20 delta put on MCHP and GME both represent ~20% probability
    of expiring ITM, regardless of very different price distances.
 
    Contracts with abs(delta) > 0.60 are ITM — excluded.
    Contracts with abs(delta) < 0.05 are deep OTM noise — excluded
    by falling outside all bucket ranges.
 
    otm_distance is retained as a reference column for downstream
    price-distance movement analysis.
    """
    df = df.copy()
    df['abs_delta'] = df['delta'].abs()
 
    # exclude ITM contracts
    df = df[df['abs_delta'] <= 0.60].copy()
 
    def label(d):
        for name, (lo, hi) in buckets.items():
            if lo <= d < hi:
                return name
        return None
 
    df['bucket'] = df['abs_delta'].apply(label)
    df.dropna(subset=['bucket'], inplace=True)
    return df


### --- Step 6: Aggregate to one row per strike bucket per DTE ──────────────────────────
def aggregate_buckets(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each (dte_window, bucket) group, compute summary stats:
    - avg_premium_pct  : mean normalized premium across contracts in bucket
    - avg_iv           : mean implied volatility
    - avg_otm_distance : mean distance from spot
    - contract_count   : how many contracts went into the average
    """
    agg = df.groupby(['dte_window', 'expiration','bucket']).agg(
        avg_premium_pct  = ('premium_pct',          'mean'),
        avg_iv           = ('implied_volatility',    'mean'),
        avg_delta        = ('abs_delta',             'mean'),  # mean abs delta per bucket
        avg_otm_distance = ('otm_distance',          'mean'),  # retained for price-distance analysis
        avg_vega         = ('vega',                  'mean'),
        contract_count   = ('contractID',            'count'),
    ).reset_index()
 
    # express as readable percentages
    agg['avg_premium_pct_display']  = (agg['avg_premium_pct']  * 100).round(3)
    agg['avg_iv_display']           = (agg['avg_iv']           * 100).round(2)
    agg['avg_delta_display']        = agg['avg_delta'].round(3)
    agg['avg_otm_distance_display'] = (agg['avg_otm_distance'] * 100).round(1)
 
    return agg
 

### --- Step 7: Two Flatten Methods - Premium and StraddleData from Strike Buckets to Single Row
def flatten_premium(summary_df, symbol, current_date, spot_price:None):
    """
    Pivot the premium summary DataFrame into a single row.

    Columns: symbol, date,
             expiration_14,
             premium_atm_14, iv_atm_14, premium_slight_14, iv_slight_14,
             premium_moderate_14, iv_moderate_14, premium_far_14, iv_far_14,
             expiration_30,
             premium_atm_30, iv_atm_30, ...etc across all DTE windows
    """
    row = {'symbol': symbol, 'date': current_date}
    bucket_order = ['ATM', 'Slight', 'Moderate', 'Far']

    # group by DTE window so expiration is inserted once per DTE block
    for dte_window, dte_group in summary_df.groupby('dte_window', sort=False):
        dte = str(dte_window)

        # insert expiration date once before each DTE block
        exp_val = dte_group['expiration'].iloc[0]
        row[f'expiration_{dte}'] = pd.Timestamp(exp_val).strftime('%Y-%m-%d') if pd.notna(exp_val) else None

        # write buckets in ATM → Slight → Moderate → Far order
        bucket_map = dte_group.set_index('bucket')
        for bucket in bucket_order:
            if bucket not in bucket_map.index:
                continue
            r = bucket_map.loc[bucket]
            b = bucket.lower()
            row[f'premium_{b}_{dte}'] = round(r['avg_premium_pct'] * 100, 4)
            row[f'iv_{b}_{dte}']      = round(r['avg_iv'] * 100, 4)

    return pd.DataFrame([row])


def flatten_premium_summary(put_result, prem_unit_df, symbol, current_date, spot_price:None):
    """
    Flatten all premium metrics into a single row DataFrame.
    Expiration inserted before each DTE block. Buckets in ATM → Slight → Moderate → Far order.
    """
    row = {'symbol': symbol, 'date': current_date, 'spot': spot_price}

    bucket_order = ['ATM', 'Slight', 'Moderate', 'Far']
    summary_df   = put_result['summary']

    # premium + IV — grouped by DTE, ordered buckets, expiration header per block
    for dte_window, dte_group in summary_df.groupby('dte_window', sort=False):
        dte = str(dte_window)

        exp_val = dte_group['expiration'].iloc[0]
        row[f'expiration_{dte}'] = pd.Timestamp(exp_val).strftime('%Y-%m-%d') if pd.notna(exp_val) else None

        bucket_map = dte_group.set_index('bucket')
        for bucket in bucket_order:
            if bucket not in bucket_map.index:
                continue
            r = bucket_map.loc[bucket]
            b = bucket.lower()
            row[f'premium_{b}_{dte}'] = round(r['avg_premium_pct'] * 100, 4)
            row[f'iv_{b}_{dte}']      = round(r['avg_iv'] * 100, 4)

    # straddle and per-unit metrics — one value per DTE, appended after premium block
    for _, r in prem_unit_df.iterrows():
        dte = str(r['dte_window'])
        row[f'straddle_{dte}']            = round(r['straddle_pct'] * 100,    4)
        row[f'put_atm_{dte}']             = round(r['put_atm_pct'] * 100,     4)
        row[f'call_atm_{dte}']            = round(r['call_atm_pct'] * 100,    4)
        row[f'prem_per_iv_primary_{dte}'] = r['prem_per_iv_primary']
        row[f'prem_per_iv_sec_{dte}']     = r['prem_per_iv_secondary']
        row[f'prem_per_hv30_{dte}']       = r['prem_per_hv30']

    return pd.DataFrame([row])


### --- Master function -----------------------------------------------------------
def build_premium_buckets(raw_contracts: list[dict],
                       symbol: str,
                       current_date: str,
                       spot_price: float,
                       # option_type: str = 'put') -> dict:
                       option_type: str ) -> dict:
    """
    Master pipeline. 

    Args:
        raw_contracts : list of dicts straight from Alpha Vantage API
        symbol        : e.g. 'AAPL'
        current_date  : 'YYYY-MM-DD'
        spot_price    : current stock price (you pass this in — pull from AV quote)
        option_type   : 'put' or 'call'

    Returns:
        {
          'symbol': 'AAPL',
          'date': '2026-02-25',
          'spot': 244.00,
          'option_type': 'put',
          'target_expirations': { 14: <date>, 30: <date>, 45: <date> },
          'summary': DataFrame — one row per (dte_window, bucket),
          'detail':  DataFrame — every filtered contract with derived columns
        }
    """
    today = datetime.strptime(current_date, '%Y-%m-%d')

    # 1. parse
    df = parse_contracts(raw_contracts)

    # 2. find target expirations | DF of data
    target_exps = find_target_expirations(df, today)

    # 3. filter to relevant expirations only, tag with dte_window
    frames = []
    for dte_window, exp_date in target_exps.items():
        if exp_date is None:
            print(f"  ⚠️  No expiration found near {dte_window} DTE for {symbol}")
            continue
        subset = df[df['expiration'] == exp_date].copy()
        subset['dte_window'] = dte_window
        subset['expiration'] = exp_date
        subset['actual_dte'] = (exp_date - pd.Timestamp(today)).days
        frames.append(subset)

    if not frames:
        raise ValueError(f"No usable expirations found for {symbol} on {current_date}")

    combined = pd.concat(frames, ignore_index=True)

    # 4. filter for liquidity / vega
    filtered = filter_contracts(combined, option_type=option_type)

    # 5. normalized premium
    with_premium = compute_normalized_premium(filtered, spot=spot_price)

    # 6. bucket by strike price
    bucketed = assign_buckets(with_premium)

    # 7. aggregate
    summary = aggregate_buckets(bucketed)

    # add symbol metadata
    summary.insert(0, 'symbol', symbol)
    summary.insert(1, 'date', current_date)
    summary.insert(2, 'spot', spot_price)

    ### Add flat summary
    flat_summary = flatten_premium(summary, symbol, current_date, spot_price)

    return {
        'symbol':             symbol,
        'date':               current_date,
        'spot':               spot_price,
        'option_type':        option_type,
        'target_expirations': target_exps,  ### Step 2 DataFrame Output
        'summary':            summary,      ### Step 7 DataFrame Output
        'detail':             bucketed,     ### Step 6 DF Output
        'flat_summary' : flat_summary       ### Offering a flat summary
    }

### --- Step 8 - Routine to take Call/Put data to build Straddle. 
def compute_straddle_premium(put_summary, call_summary):
    """
    Combine ATM put and call premiums into straddle premium per DTE window for analysis.
    Uses avg_premium_pct (extrinsic / spot) from each side.

    Args:
        put_summary  : result['summary'] from build_premium_buckets(..., 'put')
        call_summary : result['summary'] from build_premium_buckets(..., 'call')

    Returns DataFrame — one row per DTE window:
        dte_window, put_atm_pct, call_atm_pct, straddle_pct
    """
    put_atm = (
        put_summary[put_summary['bucket'] == 'ATM']
        [['dte_window', 'avg_premium_pct']]
        .rename(columns={'avg_premium_pct': 'put_atm_pct'})
    )
    call_atm = (
        call_summary[call_summary['bucket'] == 'ATM']
        [['dte_window', 'avg_premium_pct']]
        .rename(columns={'avg_premium_pct': 'call_atm_pct'})
    )

    straddle = put_atm.merge(call_atm, on='dte_window', how='inner')
    straddle['straddle_pct'] = straddle['put_atm_pct'] + straddle['call_atm_pct']

    return straddle.reset_index(drop=True)


### --- Step 9: Premium per unit of IV — primary / secondary / complement --------
def compute_premium_per_unit_iv(straddle_df, atm_iv_by_dte, hv_30, actual_dtes=None):
    """
    Three premium efficiency metrics per DTE window.

    Primary   : straddle_pct / (ATM IV x sqrt(DTE/252))
                Normalized by theoretical ATM move — near 1.0 = fair value,
                above 1.0 = collecting more than IV implies.

    Secondary : put_atm_pct / ATM IV
                Raw premium per point of implied vol.

    Complement: put_atm_pct / HV_30
                Premium per point of realized vol — how much you collect
                relative to what the stock has actually been doing.

    Args:
        straddle_df    : output of compute_straddle_premium()
        atm_iv_by_dte  : dict { dte_window -> ATM IV float } from build_hv_score()
        hv_30          : float — 30-day historical vol from build_hv_score()
        actual_dtes    : dict { dte_window -> actual int DTE } — use real DTE
                         values for sqrt(T). Falls back to nominal if None.

    Returns DataFrame — one row per DTE window:
        dte_window, straddle_pct, put_atm_pct, call_atm_pct,
        prem_per_iv_primary, prem_per_iv_secondary, prem_per_hv30
    """
    # nominal DTE fallback mapping
    nominal_dte = {14: 14, 30: 30, 45: 45, 'over60_1': 63, 'over60_2': 91}

    records = []

    for _, row in straddle_df.iterrows():
        dte_window = row['dte_window']
        atm_iv     = atm_iv_by_dte.get(dte_window)

        # use actual DTE if available, else nominal
        if actual_dtes and dte_window in actual_dtes:
            dte_days = actual_dtes[dte_window]
        else:
            dte_days = nominal_dte.get(dte_window, 30)

        t = dte_days / 252   # fraction of year

        # primary — straddle / (IV x sqrt(T))
        if atm_iv and atm_iv > 0 and t > 0:
            primary = row['straddle_pct'] / (atm_iv * np.sqrt(t))
        else:
            primary = np.nan

        # secondary — put_atm / IV
        if atm_iv and atm_iv > 0:
            secondary = row['put_atm_pct'] / atm_iv
        else:
            secondary = np.nan

        # complement — put_atm / HV_30
        if hv_30 and hv_30 > 0:
            complement = row['put_atm_pct'] / hv_30
        else:
            complement = np.nan

        records.append({
            'dte_window':            dte_window,
            'straddle_pct':          round(row['straddle_pct'],  4),
            'put_atm_pct':           round(row['put_atm_pct'],   4),
            'call_atm_pct':          round(row['call_atm_pct'],  4),
            'prem_per_iv_primary':   round(primary,    4) if not np.isnan(primary)    else np.nan,
            'prem_per_iv_secondary': round(secondary,  4) if not np.isnan(secondary)  else np.nan,
            'prem_per_hv30':         round(complement, 4) if not np.isnan(complement) else np.nan,
        })

    return pd.DataFrame(records)


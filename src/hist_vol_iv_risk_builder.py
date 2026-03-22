"""
The 'build_hv_score' method and supporting method calls develop data metrics covering; 
historical volatility over parametered lookback windows,
pulls ATM IV for each DTE period, 
calculates IV to HV ratio/spreads for risk scoring,
and Spike analysis. 

Key Assumptions embedded include;
a. Lookback windows for calculating historical vol. 
b. The primary HV window for assessing vol ratios. 
c. DTE Windows that should match the Option Premium call. 
d. IV/HV Ratio categorization thresholds. 
e. 
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

### Hard Params
HV_WINDOWS  = [20, 30, 60]   ### lookback windows in trading days
                              # 30 is the primary (matches 30-DTE IV comparison)
                              # 20 and 60 give short and long context
PRIMARY_HV  = 30
DTE_WINDOWS = [14, 30, 'over60_1', 'over60_2']

### -- Step 1: Parse TIME_SERIES_DAILY response ---------------------------------
def parse_daily_closes(av_response):
    """
    Parse Alpha Vantage TIME_SERIES_DAILY API response into a clean
    date-indexed Series of closing prices, sorted oldest to newest.
    """
    time_series = av_response.get('Time Series (Daily)', {})

    if not time_series:
        raise ValueError("No 'Time Series (Daily)' key found in response. "
                         "Check your API key and symbol.")

    closes = {}
    for date_str, price_data in time_series.items():
        closes[pd.Timestamp(date_str)] = float(price_data['4. close'])

    series = pd.Series(closes).sort_index()   # oldest first
    return series

### -- Step 2: Compute log returns ----------------------------------------------
def compute_log_returns(closes):
    """
    Daily log returns: ln(P_t / P_t-1)

    Natural log (np.log) ensures returns are:
      - additive across time (ln(P2/P0) = ln(P1/P0) + ln(P2/P1))
      - consistent with Black-Scholes lognormal assumption
      - directly comparable to annualized IV from options pricing
    """
    return np.log(closes / closes.shift(1))


### -- Step 3: Compute rolling annualized HV ------------------------------------
def compute_hv(closes, time_windows=None):
    """
    Compute annualized historical volatility for one or more lookback windows.

    Args:
        closes  : pd.Series of daily closing prices (oldest to newest)
        windows : list of int lookback windows in trading days (default HV_WINDOWS)

    Returns:
        pd.DataFrame with one column per window, e.g.:
            date        HV_20   HV_30   HV_60
            2026-02-26  0.231   0.244   0.267
            ...

        Values are decimals (0.25 = 25% annualized vol), matching IV format.
    """
    if time_windows is None:
        time_windows = HV_WINDOWS

    log_returns = compute_log_returns(closes)  ### engage method -> 'compute log returns'
    result = pd.DataFrame(index=closes.index)

    for time_windows in time_windows:
        rolling_std          = log_returns.rolling(window=time_windows).std()
        hv_annualized        = rolling_std * np.sqrt(252)
        result['HV_{}'.format(time_windows)] = hv_annualized

    return result


### -- Step 4: Extract current HV snapshot -------------------------------------
def get_current_hv(closes, time_windows=None, as_of_date=None):
    """
    Most recent HV reading for each window as a dict.
    e.g. { 'HV_20': 0.196, 'HV_30': 0.215, 'HV_60': 0.253 }
    """
    if time_windows is None:
        time_windows = HV_WINDOWS

    hv_df = compute_hv(closes, time_windows=time_windows)
    ### Identify the as-of-date in the updated closes DF, and filter df for the as-of-date and prior. 
    if as_of_date is not None:
        hv_df = hv_df[hv_df.index <= pd.Timestamp(as_of_date)]

    if hv_df.empty:
        raise ValueError("No HV data available for the requested date range.")

    return hv_df.iloc[-1].dropna().to_dict()


### -- Step 5: Extract ATM IV per DTE window ------------------------------------
def extract_atm_iv_by_dte(summary_df):
    """
    From the option premium summary DataFrame (output of build_premium_buckets),
    pull ATM IV for each DTE window.

    Uses ATM bucket only - most liquid, most stable IV reading.
    30-DTE ATM IV is the primary comparison against HV_30.

    Input:  result['summary'] from build_premium_buckets()
    Output: { 14: 0.32, 30: 0.28, 45: 0.27, 'over60_1': 0.26, 'over60_2': 0.25 }
    """
    atm_iv = {}

    for dte in DTE_WINDOWS:
        row = summary_df[
            (summary_df['dte_window'] == dte) &
            (summary_df['bucket']     == 'ATM')
        ]
        if not row.empty:
            atm_iv[dte] = row['avg_iv'].values[0]

    return atm_iv


### -- Step 6: IV/HV ratio per DTE window ---------------------------------------
def compute_iv_hv_ratios(atm_iv_by_dte, current_hv, primary_hv=PRIMARY_HV):
    """
    For each DTE window compute IV/HV ratio and spread against HV_30.

    iv_hv_ratio  > 1.0  options are pricing in MORE vol than realized  -> rich
    iv_hv_ratio  < 1.0  options are pricing in LESS vol than realized  -> cheap
    iv_hv_spread        raw percentage point gap (IV minus HV)

    Returns list of dicts, one per DTE window.
    """
    hv_key = 'HV_{}'.format(primary_hv)
    hv_val = current_hv.get(hv_key)

    rows = []
    for dte, iv in atm_iv_by_dte.items():

        if hv_val is None or hv_val == 0:
            continue

        ratio  = iv / hv_val
        spread = iv - hv_val

        if ratio >= 1.5:
            interpretation = 'Very Rich Vol'
        elif ratio >= 1.2:
            interpretation = 'Rich Vol'
        elif ratio >= 0.9:
            interpretation = 'Equiv. Vol'
        elif ratio >= 0.7:
            interpretation = 'Compressed Vol'
        else:
            interpretation = 'Discounted Vol'


        all_ratios = {
            key: round(iv / v, 3)
            for key, v in current_hv.items()
            if v and v > 0
        }

        rows.append({
            'dte_window':     dte,
            'atm_iv':         round(iv,     4),
            'hv_primary':     round(hv_val, 4),
            'iv_hv_ratio':    round(ratio,  3),
            'iv_hv_spread':   round(spread, 4),
            'interpretation': interpretation,
            'all_ratios':     all_ratios,
        })

    return rows


### -- Spike Analysis: Frequency and Magnitude --------------------------------------------
def compute_spike_analysis(closes, window=30, sigma_threshold=2.0):
    """
    Spike frequency and magnitude over a rolling window of trading days.
    A spike = |log_return| > sigma_threshold standard deviations of that window's returns.

    Args:
        closes          : pd.Series of daily closing prices
        window          : int lookback window in trading days (default 30, also run at 60)
        sigma_threshold : float std dev multiplier for spike definition (default 2.0 = 4.55% expected)

    Returns dict with spike_count, spike_ratio, avg_spike_pct, max_spike_pct, spike_signal, spike_days.
    """
    log_returns    = compute_log_returns(closes).dropna()
    recent_returns = log_returns.iloc[-window:]

    daily_std        = recent_returns.std()
    threshold        = sigma_threshold * daily_std
    is_spike_day     = recent_returns.abs() > threshold  #Create boolean for spikes over threshold.
    spike_days       = recent_returns[is_spike_day]

    spike_count    = len(spike_days)
    expected_count = 0.0455 * len(recent_returns)
    ### Spike Ratio is ratio of present spikes over expected 2 SD spike level for the symbol. 
    spike_ratio    = round(spike_count / expected_count, 2) if expected_count > 0 else 0  ##spike ratio

    if spike_ratio >= 4.0:
        spike_signal = 'Extreme'
    elif spike_ratio >= 2.5:
        spike_signal = 'Elevated'
    elif spike_ratio >= 1.5:
        spike_signal = 'Moderate'
    else:
        spike_signal = 'Normal'

    return {
        'spike_count':   spike_count,
        'spike_ratio':   spike_ratio,
        'avg_spike_pct': round(spike_days.abs().mean() * 100, 2) if spike_count > 0 else 0.0,
        'max_spike_pct': round(recent_returns.abs().max() * 100, 2),
        'spike_signal':  spike_signal,
        'spike_days':    [
            (d.strftime('%Y-%m-%d'), round(r * 100, 2))
            for d, r in spike_days.items()
        ],
    }


### -- Master function ---------------------------------------------------------------
def build_hv_score(av_daily_response, bucket_summary, symbol, as_of_date=None):
    """
    Master function.

    Args:
        av_daily_response : raw JSON from AV TIME_SERIES_DAILY
        bucket_summary    : result['summary'] DataFrame from build_premium_buckets()
                            must have columns: dte_window, bucket, avg_iv
        symbol            : e.g. 'AAPL'
        as_of_date        : 'YYYY-MM-DD' or None for latest

    Returns dict:
        {
          'symbol'        : 'AAPL',
          'current_hv'    : { 'HV_20': 0.196, 'HV_30': 0.215, 'HV_60': 0.253 },
          'atm_iv_by_dte' : { 14: 0.32, 30: 0.28, ... },
          'iv_hv_ratios'  : [ { dte_window, atm_iv, iv_hv_ratio, ... }, ... ],
          'term_structure': DataFrame - clean display table
          'hv_series'     : DataFrame - full rolling HV history
          'closes'        : pd.Series - full price history
        }
    """
    
    closes       = parse_daily_closes(av_daily_response)  ### Step 1
    current_hv   = get_current_hv(closes, as_of_date=as_of_date)   
    hv_series    = compute_hv(closes)    ### Step 3
    atm_iv       = extract_atm_iv_by_dte(bucket_summary)
    iv_hv_ratios = compute_iv_hv_ratios(atm_iv, current_hv)
    spike_30     = compute_spike_analysis(closes, window=30)   ### short-term spike window
    spike_60     = compute_spike_analysis(closes, window=60)   ### medium-term spike window

    term_structure = pd.DataFrame(iv_hv_ratios)[[   ### Build the IV to HV Ratio Dataframe
        'dte_window', 'atm_iv', 'hv_primary',
        'iv_hv_ratio', 'iv_hv_spread', 'interpretation'
    ]].copy()
    term_structure['atm_iv_pct']     = (term_structure['atm_iv']      * 100).round(2)
    term_structure['hv_primary_pct'] = (term_structure['hv_primary']  * 100).round(2)
    term_structure['spread_pct']     = (term_structure['iv_hv_spread'] * 100).round(2)

    hv_score_dict = {
        'symbol':         symbol,
        'date':           as_of_date,
        'current_hv':     current_hv,   ### Hist Vol by Windows
        'atm_iv_by_dte':  atm_iv,       ### IV at the ATM by DTE Windows from Option Method as Input
        'iv_hv_ratios':   iv_hv_ratios, 
        'term_structure': term_structure,
        'spike_30':       spike_30,      ### short-term spike window
        'spike_60':       spike_60,      ### medium-term spike window
        'hv_series':      hv_series,
        'closes':         closes,
    }

    ### Flatten:  Prepare single flat line of symbol HV, IV data. Input is the Dict with the 
    row = {'symbol': hv_score_dict['symbol'], 'date': hv_score_dict['date']}

    # HV columns
    for key, val in hv_score_dict['current_hv'].items():
        row[key] = round(val, 4)

    # per-DTE columns
    for r in hv_score_dict['iv_hv_ratios']:
        dte = str(r['dte_window'])
        row['atm_iv_{}'.format(dte)]  = round(r['atm_iv'],      4)
        row['ratio_{}'.format(dte)]   = round(r['iv_hv_ratio'],  3)
        row['spread_{}'.format(dte)]  = round(r['iv_hv_spread'], 4)
        row['signal_{}'.format(dte)]  = r['interpretation']

    ### Spike data/columns — 30-day window
    spike_30 = hv_score_dict['spike_30']
    row['spike_count_30']   = spike_30['spike_count']
    row['spike_ratio_30']   = spike_30['spike_ratio']
    row['avg_spike_pct_30'] = spike_30['avg_spike_pct']
    row['max_spike_pct_30'] = spike_30['max_spike_pct']
    row['spike_signal_30']  = spike_30['spike_signal']

    ### Spike data/columns — 60-day window
    spike_60 = hv_score_dict['spike_60']
    row['spike_count_60']   = spike_60['spike_count']
    row['spike_ratio_60']   = spike_60['spike_ratio']
    row['avg_spike_pct_60'] = spike_60['avg_spike_pct']
    row['max_spike_pct_60'] = spike_60['max_spike_pct']
    row['spike_signal_60']  = spike_60['spike_signal']

    # return pd.DataFrame([row])

    return pd.DataFrame([row]), {
        'atm_iv_by_dte': hv_score_dict['atm_iv_by_dte'],
        'current_hv':    hv_score_dict['current_hv'],
    }



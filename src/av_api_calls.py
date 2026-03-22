
"""
API Calls and Option Analysis Loop

Two methods to connect to the Alpha Vantage API and call both
a) Historical Options for a particular date, 
b) Historical Time Series Market Data
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

import requests
import json
import dotenv
dotenv.load_dotenv()

import sys
from IPython.display import clear_output
import time
import traceback
sys.tracebacklimit = 0 # turn off the error tracebacks

import option_prem_iv_builder_V
import hist_vol_iv_risk_builder_III


### Hardcoded setting up request and params. 
headers = {'From':'alfhaugen@gmail.com'}
api_root = 'https://www.alphavantage.co'
endpoint = '/query?'


### --- API Calls ---------------------------------------------------
def av_api_data(ticker, date, api_key):
    """
    Use the av_api_data method to pull both the historical options and 
    time series market data for a particular ticker symbol. 

    Returns two json files that are inputs into the analysis methods. 
    """
    option_hist_data = hist_options_call(ticker, date, api_key) 
    market_hist_data = hist_time_series_call(ticker, date, api_key) 

    return option_hist_data, market_hist_data


def hist_options_call(ticker, date, api_key):
    opt_params = {'function': 'HISTORICAL_OPTIONS', ### or REALTIME_OPTIONS
	# opt_params = {'function': 'REALTIME_OPTIONS', ### or HISTORICAL_OPTIONS 
                'symbol':ticker,
                'date': date, ### for Historical
                # 'require_greeks': 'true',   ### for Real Time
                'datatype':'json',
                'apikey':api_key
                }

    opt_request_prod=requests.get(api_root+endpoint, params=opt_params)
    opt_data_prod = opt_request_prod.json()
    opt_hist_data = opt_data_prod['data']
    # print(f"API Option Endpoint: {opt_data_prod['endpoint']}")
    # print(f"API Option Message: {opt_data_prod['message']}")

    return opt_data_prod


def hist_time_series_call(ticker, date, api_key):
    mkt_params = {'function': 'TIME_SERIES_DAILY', ### below params for Time Series
        'symbol': ticker,
          # 'interval': '5min',
          # 'adjusted': 'false',
          'outputsize':'compact', ### compact or full
          'datatype':'json',
          'entitlement':'delayed',
          'apikey':api_key
          }

    market_request = requests.get(api_root + endpoint, params = mkt_params)
    hist_market_data = market_request.json()

    # print(json.dumps(hist_market_data['Meta Data'], indent=4))

    return hist_market_data


### =======================================================================================
### Option Analysis Loop - Main Call --->

from IPython.display import clear_output
import time
import traceback
sys.tracebacklimit = 0 # turn off the error tracebacks

#### Params ---> Moved as Parameter Input from Call below...
# option_date = '2026-02-27'   # date for historical options chain
# as_of_date  = '2026-02-27'   # truncate HV history at this date

# -- Rate limit config --------------------------------------------------------
# HISTORICAL_OPTIONS + TIME_SERIES_DAILY = 2 calls per symbol
# 75 calls/min -> 37 symbols per batch

BATCH_SIZE = 37
PAUSE_SECS = 61

def option_analysis_scan(ticker_list, api_key, option_date, as_of_date):
    """
    Perform the Loop Scan to acquire and build the Option Premium, HV / Risk data for the list of tickers. 
    """

    ## --- Scan loop containers ----------------------------------------------------------------
    sym_analysis_comb = []
    errors       = []

    call_count  = 0
    batch_start = time.time()
    run_start = time.time()   # <- start timer before the loop
    api_key = api_key

    ## fetch benchmark HV once before scanning the universe ----------- -> New
    print("Fetching benchmark HV (SPY, QQQ)")
    spy_contracts, spy_daily  = av_api_data('SPY',  option_date, api_key)
    qqq_contracts, qqq_daily  = av_api_data('QQQ',  option_date, api_key)
    spy_cont_data = spy_contracts['data']
    qqq_cont_data = qqq_contracts['data']

    spy_spot = float(spy_daily['Time Series (Daily)'][as_of_date]['4. close'])  ### Grab Spot Price for date
    qqq_spot = float(qqq_daily['Time Series (Daily)'][as_of_date]['4. close'])  ### Grab Spot Price for date

    spy_put  = option_prem_iv_builder_V.build_premium_buckets(spy_cont_data,  'SPY',  option_date, spy_spot,  'put')
    qqq_put  = option_prem_iv_builder_V.build_premium_buckets(qqq_cont_data,  'QQQ',  option_date, qqq_spot,  'put')

    spy_hv_result, _ = hist_vol_iv_risk_builder_III.build_hv_score(spy_daily, spy_put['summary'],  'SPY',  as_of_date)
    qqq_hv_result, _ = hist_vol_iv_risk_builder_III.build_hv_score(qqq_daily, qqq_put['summary'],  'QQQ',  as_of_date)

    spy_hv_30 = float(spy_hv_result['HV_30'].iloc[0])
    qqq_hv_30 = float(qqq_hv_result['HV_30'].iloc[0])

    print("SPY HV_30: {:.1%}  |  QQQ HV_30: {:.1%}".format(spy_hv_30, qqq_hv_30))

    ## --- Run Loop -----------------------------------------------------------------> 
    for ind, symbol in enumerate(ticker_list):
        # print("[{}/{}] {}...".format(ind+1, len(ticker_list), symbol), end=' ')
        elapsed_total = time.time() - run_start
        mins, secs    = divmod(int(elapsed_total), 60)
        
        # clear_output(wait=True)
        if ind % 2 == 0:   # clear every other iteration
            clear_output(wait=True)
        print("Scanning {} symbols".format(len(ticker_list)))
        print("="*40)
        print("[{}/{}] Current: {}".format(ind+1, len(ticker_list), symbol))
        print("Succeeded : {}".format(len(sym_analysis_comb)))
        print("Failed    : {}".format(len(errors)))
        print("API calls : {}".format(call_count))
        print("Elapsed   : {:02d}:{:02d}".format(mins, secs))

        try:
            ### Run 2 API outputs from 'av_api_data' to get Option / Market Data ------->
            opt_contracts_call, daily_mkt_data = av_api_data(symbol, option_date, api_key)
            opt_contracts_data = opt_contracts_call['data']
            call_count += 2
            # print(type(opt_contracts_data), type(daily_mkt_data))  ## Checking type of outputs
            
            spot = float(daily_mkt_data['Time Series (Daily)'][as_of_date]['4. close'])  ### Grab Spot Price for date
            print(f' Pushing in the spot value {spot} ')
            
            # spot = spot_prices.get(symbol)
            if spot is None:
                raise ValueError("No spot price provided for {}".format(symbol))

            if len(ticker_list) < 10 or call_count % 30 == 0:
                print(spot)
                print(f"API Option Endpoint: {opt_contracts_call['endpoint']}")
                print(f"API Option Message: {opt_contracts_call['message']}")
                print(f"Daily Time Series Message: {json.dumps(daily_mkt_data['Meta Data'], indent=4)}")
        
            ### Build option premium buckets -------------------------------------------
            print("Building Option Premium Data")
            # opt_result_temp = option_prem_iv_builder_III.build_premium_buckets(
            #     raw_contracts = opt_contracts_data,
            #     symbol        = symbol,
            #     current_date  = option_date,
            #     spot_price    = spot,
            #     option_type   = 'put',
            # )

            put_result  = option_prem_iv_builder_V.build_premium_buckets(
                raw_contracts = opt_contracts_data,
                symbol        = symbol,
                current_date  = option_date,
                spot_price    = spot,
                option_type   = 'put',
            )
            
            call_result = option_prem_iv_builder_V.build_premium_buckets(
                raw_contracts = opt_contracts_data,
                symbol        = symbol,
                current_date  = option_date,
                spot_price    = spot,
                option_type   = 'call',
            )
            
            # option_premiums = opt_result_temp['summary'].sort_values(['expiration','avg_otm_distance'])
            # option_flat_premiums = opt_result_temp['flat_summary']
            option_premiums = put_result['summary'].sort_values(['expiration','avg_otm_distance'])
            # option_flat_premiums = flatten_premium_summary(put_result, prem_units, symbol, option_date)
            # print(option_flat_premiums)

            ### Build HV + Spike Score -> returns flattened single row df ------------------------
            print("Building Historical Vol and Spike Data")
            hv_flat, hv_vol_outputs = hist_vol_iv_risk_builder_III.build_hv_score(
                av_daily_response = daily_mkt_data,
                bucket_summary    = option_premiums,
                symbol            = symbol,
                as_of_date        = as_of_date,
            )

            ## relative vol vs benchmarks — how much more volatile than market  -> NEW
            symbol_hv_30 = hv_vol_outputs['current_hv']['HV_30']
            hv_flat['relative_vol_spy'] = round(symbol_hv_30 / spy_hv_30, 2) if spy_hv_30 > 0 else None
            hv_flat['relative_vol_qqq'] = round(symbol_hv_30 / qqq_hv_30, 2) if qqq_hv_30 > 0 else None

            ### Build Straddle and prem_units --------------------------
            print("Building Straddle Data")
            actual_dtes = (
                put_result['detail'][['dte_window', 'actual_dte']]
                .drop_duplicates('dte_window')
                .set_index('dte_window')['actual_dte']
                .to_dict()
            )
            
            straddle   = option_prem_iv_builder_V.compute_straddle_premium(put_result['summary'], call_result['summary'])
            prem_units = option_prem_iv_builder_V.compute_premium_per_unit_iv(
                             straddle,
                             atm_iv_by_dte = hv_vol_outputs['atm_iv_by_dte'],
                             hv_30         = hv_vol_outputs['current_hv']['HV_30'],
                             actual_dtes   = actual_dtes,
                         )

            ### Flatten Option Data w/ Straddle -------------------------------------------------------------
            option_flat_premiums = option_prem_iv_builder_V.flatten_premium_summary(put_result, 
                                                                    prem_units, symbol, option_date, spot)

            ### Merge Option and Hist. Vol Data
            single_symbol_option_analytics = option_flat_premiums.merge(right=hv_flat.loc[:,['symbol',
                            'HV_20', 'HV_30', 'HV_60', 'atm_iv_14', 'ratio_14',
                            'spread_14', 'signal_14', 'atm_iv_30', 'ratio_30', 'spread_30',
                            'signal_30', 'atm_iv_over60_1', 'ratio_over60_1', 'spread_over60_1',
                            'signal_over60_1', 'atm_iv_over60_2', 'ratio_over60_2',
                            'spread_over60_2', 'signal_over60_2', 'spike_count_30',
                            'spike_ratio_30', 'avg_spike_pct_30', 'max_spike_pct_30',
                            'spike_signal_30', 'spike_count_60', 'spike_ratio_60',
                            'avg_spike_pct_60', 'max_spike_pct_60', 'spike_signal_60',
                            "relative_vol_spy", "relative_vol_qqq"]],
                       how='left',
                       left_on=['symbol'],
                       right_on=['symbol'])
                    
            sym_analysis_comb.append(single_symbol_option_analytics)  ### Add cons. DF into hold log / list
            print("OK")

        # except Exception as e:  ## Old Exception
        #     errors.append({'symbol': symbol, 'error': str(e)})
        #     print("ERROR -> {}".format(e))
        #     traceback.print_exc()
        #     call_count += 2   # count failed calls to keep rate limit accurate

        except Exception as e:
            # log what AV actually returned if time series is the issue
            av_info = ''
            try:
                keys = list(daily_mkt_data.keys())
                if 'Information' in daily_mkt_data:
                    av_info = daily_mkt_data['Information'][:120]
                elif 'Note' in daily_mkt_data:
                    av_info = daily_mkt_data['Note'][:120]
                elif 'Error Message' in daily_mkt_data:
                    av_info = daily_mkt_data['Error Message'][:120]
                else:
                    av_info = 'keys: {}'.format(keys)
            except:
                av_info = 'could not read daily_mkt_data'

            errors.append({
                'symbol':   symbol,
                'error':    str(e),
                'av_info':  av_info,
            })
            print("ERROR -> {}  |  {}".format(e, av_info))
            call_count += 2

        # -- rate limit -----------------------------------------------------------
        elapsed = time.time() - batch_start

        if call_count >= BATCH_SIZE * 2:
            remaining = PAUSE_SECS - elapsed
            if remaining > 0:
                print("\n  Rate limit pause: {:.0f}s...\n".format(remaining))
                time.sleep(remaining)
            call_count  = 0
            batch_start = time.time()

    # -- Combine ------------------------------------------------------------------
    option_analysis_master = pd.concat(sym_analysis_comb, ignore_index=True)
    error_log_df = pd.DataFrame(errors)

    # -- Print Summary Message ----------------------------------------------------
    # final summary after loop
    total_time  = time.time() - run_start
    mins, secs  = divmod(int(total_time), 60)
    print('------------------------------------------')    
    print("\nDone: {} succeeded, {} failed".format(len(sym_analysis_comb), len(errors)))
    print("Total time: {:02d}:{:02d}".format(mins, secs))
    print("Master shape: {}".format(option_analysis_master.shape))

    return option_analysis_master, error_log_df


### --- Error Helper ---------------------------------------------------------------------
allowed_strings = ['date', 'expiration_14','expiration_30','expiration_over60_1',
    'expiration_over60_2','signal_14','signal_30','signal_over60_1','signal_over60_2','spike_signal_30','spike_signal_60']
    
def audit_non_numeric(df, symbol_col='symbol', allowed_string_cols=allowed_strings):
    """
    Log values where numeric features are logged as NaN. 
    """

    if allowed_string_cols is None:
        allowed_string_cols = []

    ignore_cols = [symbol_col] + allowed_string_cols
    check_cols = df.columns.difference(ignore_cols)

    mask = df[check_cols].apply(
        lambda c: pd.to_numeric(c, errors='coerce').isna()
    )

    bad = mask.stack()
    bad = bad[bad]

    if bad.empty:
        print("✓ No missing or non-numeric values found")
        return None

    report = bad.reset_index()
    report.columns = ['row','column','bad_flag']

    report['symbol'] = df.loc[report['row'], symbol_col].values
    report['value'] = [df.at[r, c] for r, c in zip(report['row'], report['column'])]

    report = report[['symbol','column','value']]

    print(f"\n⚠ Found {len(report)} missing or non-numeric values\n")
    return report



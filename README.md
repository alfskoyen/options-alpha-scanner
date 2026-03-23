<!-- <div align="center">
<img src="https://github.com/alfskoyen/options-alpha-scanner/blob/main/assets/opt_scan_scatter_3.13.png?raw=true"alt="asdfdsa" width="1500"/>
<p><em>Figure: Premium to Risk Spread Scatter-Plot of Global Universe of Put Options.</em></p>
</div> -->

<!-- <div align="center">
  <a href="https://raw.githubusercontent.com/alfskoyen/options-alpha-scanner/main/assets/opt_scan_scatter_3.13.png">
    <img src="https://raw.githubusercontent.com/alfskoyen/options-alpha-scanner/main/assets/opt_scan_scatter_3.13.png" alt="Premium to Risk Scatter" width="1500"/>
  </a>
  <p><em>Figure: Premium to Risk Spread Scatter-Plot of Global Universe of Put Options.</em></p>
</div> -->

<div align="center">
  <a href="https://raw.githubusercontent.com/alfskoyen/options-alpha-scanner/main/assets/opt_scan_scatter_3.13.png">
    <img src="https://github.com/alfskoyen/options-alpha-scanner/blob/main/assets/opt_scan_scatter_3.13.png?raw=true" alt="Premium to Risk Scatter" width="1500"/>
  </a>
  <p><em>Figure: Premium to Risk Spread Scatter-Plot of Global Universe of Put Options.</em></p>
</div>

## &nbsp;  Option / Put Alpha Analysis and Dashboard Project
### A quantitative put-selling opportunity scanner across ~600 NYSE & Nasdaq symbols

---

## Table of Contents

1. [Objective & North Star](#1-objective--north-star)
2. [Pipeline Architecture](#2-pipeline-architecture)
3. [Data Sources & API Pipeline](#3-data-sources--api-pipeline)
4. [Premium Layer](#4-premium-layer)
5. [Risk Layer](#5-risk-layer)
6. [Scoring Model](#6-scoring-model)
7. [Key Assumptions](#7-key-assumptions)
8. [Output & Dashboard](#8-output--dashboard)
9. [Repository Structure](#9-repository-structure)
10. [Configuration & Setup](#10-configuration--setup)

---
## 1. Objective & North Star
The core objective of this project is to systematically and directionally identify improved put-selling opportunities across the US equity universe on any given trading day. 
Rather than monitoring only a handful of exhange tickers using limited metrics, this framework builds a two-dimensional viewpoint for every symbol scoring a) how much premium is available in comparison to the present market and volatility profile and b) how much risk is embedded in the vol environment, quickly scoring and placing the global set into a quadrant based profile. 

**Our north star is Q1: High Premium / Low Risk.**

These are symbols where the options market is offering meaningful premium relative to spot price, while the underlying volatility environment does not justify exceptional caution. 
They represent the best asymmetric put-selling setups, by first being paid well for risk that, on a relative basis, is below the universe median.

The framework is intentionally cross-sectional. Every score is relative to the scanned universe on that specific date, not absolute. A premium score of 0.85 means the symbol is in the 85th percentile of the universe — not that it meets some fixed threshold. This makes the model self-calibrating across different vol regimes.

---

## 2. Pipeline Architecture

The pipeline is multi-phased and accomplishes several data capture, wrangilng and creation setps in four sequential layers:

```
┌─────────────────────────────────────────────────────┐
│  1. API LAYER           av_api_calls.py             │
│     Alpha Vantage → options chain + daily prices    │
│     Rate-limited batching, error handling           │
│     SPY/QQQ benchmark HV computed once pre-loop     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  2. PREMIUM LAYER   option_prem_iv_builder.py       │
│     Delta-bucketed put/call premium per DTE window  │
│     ATM straddle + 3 efficiency metrics             │
│     Normalized by spot price (cross-ticker)         │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  3. RISK LAYER      hist_vol_iv_risk_builder.py     │
│     HV_20 / HV_30 / HV_60 from daily log returns    │
│     IV/HV ratios per DTE window                     │
│     Spike analysis — self-relative + universe       │
│     Relative vol vs SPY and QQQ                     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│  4. SCORING LAYER   score_universe.py               │
│     Premium Score + Risk Score (StandardScaler)     │
│     Term structure regression slopes                │
│     Premium efficiency signals per DTE              │
│     Quadrant assignment (median split)              │
│     Universe-relative percentile ranks              │
└─────────────────────────────────────────────────────┘
```

---

## 3. Data Sources & API Pipeline

### Data Source

**Alpha Vantage Premium API** — two endpoints per symbol per run:

| Endpoint | Purpose | Key Fields Used |
|---|---|---|
| `HISTORICAL_OPTIONS` | Options chain snapshot for a specific date | strike, bid, ask, IV, delta, vega, OI, expiration |
| `TIME_SERIES_DAILY` | Daily closing prices for HV computation | `4. close` |

---

#### `TIME_SERIES_DAILY` — Response Structure

*Two top-level keys are returned. `Meta Data` describes the request context.
`Time Series (Daily)` contains the price history keyed by date string,
newest first. Only `4. close` is used — pulled at `as_of_date` for spot price
and across the full compact window (100 days) for HV computation.*
```python
dict_keys(['Meta Data', 'Time Series (Daily)'])
```

**Meta Data**
```json
{
    "1. Information": "Daily Prices (open, high, low, close) and Volumes - DATA DELAYED BY 15 MINUTES",
    "2. Symbol":      "TQQQ",
    "3. Last Refreshed": "2026-03-20",
    "4. Output Size": "Compact",
    "5. Time Zone":   "US/Eastern"
}
```

**Time Series (Daily)** — *one entry per trading day, newest first*
```json
{
    "2026-03-20": {
        "1. open":   "45.1800",
        "2. high":   "45.2100",
        "3. low":    "42.3000",
        "4. close":  "43.0800",
        "5. volume": "137952495"
    },
    "2026-03-19": {
        "1. open":   "44.8700",
        "2. high":   "46.3200",
        "3. low":    "44.3000",
        "4. close":  "45.6900",
        "5. volume": "138384909"
    }
}
```

> **Pipeline usage:** `spot = float(daily_data['Time Series (Daily)'][as_of_date]['4. close'])`
> HV is computed from the full series via `parse_daily_closes()` which truncates at `as_of_date`.


### API Design Decisions

**Historical vs Realtime options:** `HISTORICAL_OPTIONS` is used rather than `REALTIME_OPTIONS` because it allows point-in-time analysis with a specific `date` parameter — critical for backtesting and for ensuring the HV window and options chain are synchronized to the same date.

**`outputsize=compact`:** Returns the last 100 trading days of price history — sufficient for HV_60 (60 trading days minimum) while keeping API response times fast.

**Spot price derivation:** Spot is pulled from `TIME_SERIES_DAILY` at the `as_of_date` close, not from the options chain. This ensures the spot used for normalization is the actual closing price, not an inferred mid-market from the chain.

**Rate limiting:** Alpha Vantage Premium allows 75 calls/minute. Each symbol requires 2 calls (options + prices). The loop batches 37 symbols per minute with a 61-second pause between batches.

**Benchmark pre-fetch:** SPY and QQQ are fetched once before the main loop. Their `HV_30` values are used to compute `relative_vol_spy` and `relative_vol_qqq` for every symbol in the universe — adding these to the loop would cost 4 extra calls per symbol.

**Error handling:** Failed symbols are logged to `error_log_df` with the raw AV response keys captured — distinguishing between rate limit responses (`Information` key), per-minute throttles (`Note` key), and invalid symbols (`Error Message` key).

---


<div align="center">
<img src="https://github.com/alfskoyen/options-alpha-scanner/blob/main/assets/opt_scan_bar_prem_3.13.png?raw=true"alt="asdfdsa" width="1500"/>
<p><em>Figure: Premium to Risk Spread Scatter-Plot of Global Universe of Put Options.</em></p>
</div>

<div align="center">
<img src="https://github.com/alfskoyen/options-alpha-scanner/blob/main/assets/opt_scan_histo_risk_3.13.png?raw=true"alt="asdfdsa" width="1500"/>
<p><em>Figure: Premium to Risk Spread Scatter-Plot of Global Universe of Put Options.</em></p>
</div>

<div align="center">
<img src="https://github.com/alfskoyen/options-alpha-scanner/blob/main/assets/opt_scan_term_q3_atm_prem_3.13.png?raw=true"alt="asdfdsa" width="1500"/>
<p><em>Figure: Premium to Risk Spread Scatter-Plot of Global Universe of Put Options.</em></p>
</div>

<div align="center">
<img src="https://github.com/alfskoyen/options-alpha-scanner/blob/main/assets/opt_scan_table_3.13.png?raw=true"alt="asdfdsa" width="1500"/>
<p><em>Figure: Premium to Risk Spread Scatter-Plot of Global Universe of Put Options.</em></p>
</div>

Welcome

[![Live Demo](https://img.shields.io/badge/Live-Demo-4dd9d9?style=for-the-badge)]([https://your-app-name.onrender.com](https://options-alpha-scanner.onrender.com))

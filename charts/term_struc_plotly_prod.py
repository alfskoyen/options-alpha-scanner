
"""
term_structure.py
────────────────────────────────────────────────────────────────────────
Term structure line charts — median line + ±1σ/±2σ bands across DTE or
lookback windows, with optional quadrant overlay lines.

Functions
---------
build_term_structure(df, metric, ...)
    DTE-based metrics across 14 / 30 / 60D+1 / 60D+2:
      'put_atm'           ATM Put Premium
      'premium_slight'    Slight OTM Premium
      'premium_moderate'  Moderate OTM Premium
      'premium_far'       Far OTM Premium
      'atm_iv'            ATM Implied Volatility
      'ratio'             IV / HV Ratio

build_hv_term_structure(df, ...)
    HV lookback term structure across HV_20 / HV_30 / HV_60
    with optional IV overlay at matched windows.

build_iv_hv_overlay(df, ...)
    IV term structure (14/30/60D+1/60D+2) overlaid with
    HV (20/30/60) on a shared y-axis for direct comparison.

build_slope_overlay(df, metric, ...)
    Premium or IV term structure with per-symbol OLS regression
    lines overlaid — median regression + ±1σ slope bands.

build_slope_distribution(df, ...)
    Box chart of premium_slope_pct, iv_slope_pct, slope_div_pct
    split by quadrant.

show_term_structure_dashboard(df)
    Full interactive Jupyter widget covering all five views.

Usage:
    from term_structure import show_term_structure_dashboard
    show_term_structure_dashboard(df)
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ── DESIGN TOKENS ─────────────────────────────────────────────────
BG        = "#1e2127"
PANEL     = "#252830"
GRID      = "#2a2f3e"
CROSS     = "#4a5270"
TEXT_PRI  = "#edf0f7"
TEXT_AX   = "#c8cfe8"
AX_TITLE  = "#6ecece"
ACCENT    = "#4dd9d9"

Q_COLORS = {
    "Q1": "#2bde9e",
    "Q2": "#ffb340",
    "Q3": "#7b8bad",
    "Q4": "#ff5c6a",
}

Q_LABELS = {
    "Q1": "Q1 · High Premium / Low Risk",
    "Q2": "Q2 · High Premium / High Risk",
    "Q3": "Q3 · Low Premium  / Low Risk",
    "Q4": "Q4 · Low Premium  / High Risk",
}

MONO = "JetBrains Mono, Fira Mono, Consolas, monospace"

# ── DTE METRIC DEFINITIONS ────────────────────────────────────────
METRICS = {
    "put_atm": {
        "label": "ATM Put Premium (%)",
        "cols":  ["put_atm_14", "put_atm_30", "put_atm_over60_1", "put_atm_over60_2"],
    },
    "premium_slight": {
        "label": "Slight OTM Premium (%)",
        "cols":  ["premium_slight_14", "premium_slight_30",
                  "premium_slight_over60_1", "premium_slight_over60_2"],
    },
    "premium_moderate": {
        "label": "Moderate OTM Premium (%)",
        "cols":  ["premium_moderate_14", "premium_moderate_30",
                  "premium_moderate_over60_1", "premium_moderate_over60_2"],
    },
    "premium_far": {
        "label": "Far OTM Premium (%)",
        "cols":  ["premium_far_14", "premium_far_30",
                  "premium_far_over60_1", "premium_far_over60_2"],
    },
    "atm_iv": {
        "label": "ATM Implied Volatility",
        "cols":  ["atm_iv_14", "atm_iv_30", "atm_iv_over60_1", "atm_iv_over60_2"],
    },
    "ratio": {
        "label": "IV / HV Ratio",
        "cols":  ["ratio_14", "ratio_30", "ratio_over60_1", "ratio_over60_2"],
    },
}

# DTE x-axis — approximate calendar days for even spacing
DTE_X      = [14, 30, 63, 91]
DTE_LABELS = ["14D", "30D", "60D+1", "60D+2"]

# HV lookback x-axis
HV_X      = [20, 30, 60]
HV_LABELS = ["HV 20D", "HV 30D", "HV 60D"]
HV_COLS   = ["HV_20", "HV_30", "HV_60"]

# IV columns matched to approximate HV lookback windows
IV_HV_MATCH_COLS   = ["atm_iv_14", "atm_iv_30", "atm_iv_over60_1"]
IV_HV_MATCH_X      = [14, 30, 63]


# ── SHARED HELPERS ────────────────────────────────────────────────
def _base_layout(title_text: str, height: int = 520) -> dict:
    return dict(
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        height=height,
        margin=dict(l=72, r=200, t=72, b=64),
        title=dict(
            text=title_text,
            x=0.03,
            font=dict(family=MONO, color=TEXT_PRI, size=15),
        ),
        legend=dict(
            bgcolor=BG, bordercolor=CROSS, borderwidth=1,
            font=dict(size=12, color=TEXT_PRI, family=MONO),
            x=1.02, y=1, xanchor="left", yanchor="top",
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1a1d28", bordercolor=CROSS,
            font=dict(size=12, color=TEXT_PRI, family=MONO),
            namelength=0,
        ),
        font=dict(family=MONO, color=TEXT_PRI, size=11),
    )


def _ax(title: str = "", **kw) -> dict:
    base = dict(
        title=dict(text=title, font=dict(size=12, color=AX_TITLE, family=MONO)),
        gridcolor=GRID, gridwidth=1,
        zeroline=True, zerolinecolor=CROSS, zerolinewidth=1,
        linecolor="#363b50", linewidth=1,
        tickfont=dict(size=12, color=TEXT_AX, family=MONO),
        ticklen=5, showgrid=True,
    )
    base.update(kw)
    return base


def _extract(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Return only columns that exist in df."""
    return df[[c for c in cols if c in df.columns]].copy()


def _stats(data: pd.DataFrame) -> dict:
    """Median, mean, std, p25, p75, count per column across symbols."""
    return {
        "median": data.median().values,
        "mean":   data.mean().values,
        "std":    data.std().values,
        "p25":    data.quantile(0.25).values,
        "p75":    data.quantile(0.75).values,
        "count":  data.notna().sum().values,
    }


def _filter_quadrant(df: pd.DataFrame, quadrant_filter: str) -> tuple:
    """Return (filtered_df, display_label)."""
    if quadrant_filter != "all":
        dff   = df[df["quadrant"].str.startswith(quadrant_filter)].copy()
        label = Q_LABELS.get(quadrant_filter, quadrant_filter)
    else:
        dff   = df.copy()
        label = "All symbols"
    return dff, label


def _band_traces(fig, x, s, rgba_1sig, rgba_2sig):
    """Add ±2σ then ±1σ fill bands to fig."""
    fig.add_trace(go.Scatter(
        x=x + x[::-1],
        y=np.concatenate([s["median"] + 2*s["std"],
                          (s["median"] - 2*s["std"])[::-1]]).tolist(),
        fill="toself", fillcolor=rgba_2sig,
        line=dict(width=0), showlegend=True,
        name="±2σ band", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x + x[::-1],
        y=np.concatenate([s["median"] + s["std"],
                          (s["median"] - s["std"])[::-1]]).tolist(),
        fill="toself", fillcolor=rgba_1sig,
        line=dict(width=0), showlegend=True,
        name="±1σ band", hoverinfo="skip",
    ))


def _median_trace(fig, x, s, color, name, show_mean=False):
    """Add median line + optional dashed mean line to fig."""
    fig.add_trace(go.Scatter(
        x=x, y=s["median"].tolist(),
        mode="lines+markers", name=name,
        line=dict(color=color, width=2.5),
        marker=dict(size=7, color=color, line=dict(width=1.5, color=BG)),
        customdata=np.stack([s["median"], s["mean"], s["std"],
                              s["p25"], s["p75"], s["count"]], axis=-1),
        hovertemplate=(
            "<b>%{x}</b><br>"
            f"<span style='color:{color}'>Median</span>"
            "  <b>%{customdata[0]:.3f}</b><br>"
            "Mean  <b>%{customdata[1]:.3f}</b><br>"
            "Std   <b>%{customdata[2]:.3f}</b><br>"
            "25th  <b>%{customdata[3]:.3f}</b><br>"
            "75th  <b>%{customdata[4]:.3f}</b><br>"
            "n     <b>%{customdata[5]}</b><extra></extra>"
        ),
    ))
    if show_mean:
        fig.add_trace(go.Scatter(
            x=x, y=s["mean"].tolist(),
            mode="lines+markers", name="Mean",
            line=dict(color=color, width=1.5, dash="dash"),
            marker=dict(size=5, color=color),
            hovertemplate="<b>%{x}</b>  Mean <b>%{y:.3f}</b><extra></extra>",
        ))


def _quadrant_lines(fig, df, cols, x, show_quadrants, quadrant_filter):
    """Overlay per-quadrant dotted median lines when requested."""
    if not show_quadrants or quadrant_filter != "all":
        return
    for q, color in Q_COLORS.items():
        q_data = _extract(df[df["quadrant"].str.startswith(q)], cols)
        if q_data.empty:
            continue
        q_s = _stats(q_data)
        q_n = int(q_s["count"].mean())
        fig.add_trace(go.Scatter(
            x=x, y=q_s["median"].tolist(),
            mode="lines+markers", name=f"{q}  (n={q_n})",
            line=dict(color=color, width=1.8, dash="dot"),
            marker=dict(size=6, color=color, line=dict(width=1, color=BG)),
            customdata=np.stack([q_s["median"], q_s["std"],
                                  q_s["count"]], axis=-1),
            hovertemplate=(
                f"<b>%{{x}}</b>  "
                f"<span style='color:{color}'>{q}</span>"
                "  <b>%{customdata[0]:.3f}</b><br>"
                "Std  <b>%{customdata[1]:.3f}</b>  "
                "n  <b>%{customdata[2]}</b><extra></extra>"
            ),
        ))


# ── 1. DTE TERM STRUCTURE ─────────────────────────────────────────
def build_term_structure(
    df:              pd.DataFrame,
    metric:          str  = "put_atm",
    show_quadrants:  bool = False,
    quadrant_filter: str  = "all",
    show_mean:       bool = False,
    height:          int  = 520,
) -> go.Figure:
    """
    Term structure across 14D / 30D / 60D+1 / 60D+2.

    metric: 'put_atm' | 'premium_slight' | 'premium_moderate' |
            'premium_far' | 'atm_iv' | 'ratio'
    """
    cfg   = METRICS.get(metric, METRICS["put_atm"])
    cols  = cfg["cols"]
    label = cfg["label"]

    dff, univ_label = _filter_quadrant(df, quadrant_filter)
    data = _extract(dff, cols)
    s    = _stats(data)
    n    = int(s["count"].mean())

    fig = go.Figure()
    _band_traces(fig, DTE_X, s,
                 "rgba(77,217,217,0.18)", "rgba(77,217,217,0.08)")
    _median_trace(fig, DTE_X, s, ACCENT,
                  f"Median  ({univ_label}  n={n})", show_mean)
    _quadrant_lines(fig, df, cols, DTE_X, show_quadrants, quadrant_filter)

    if metric == "ratio":
        fig.add_hline(y=1.0, line=dict(color=CROSS, width=1.2, dash="dot"))
        fig.add_annotation(
            x=max(DTE_X), y=1.0, xref="x", yref="y",
            text="  IV = HV", showarrow=False,
            font=dict(size=9, color=CROSS, family=MONO), xanchor="left",
        )

    q_tag = f"  ·  {quadrant_filter}" if quadrant_filter != "all" else ""
    fig.update_layout(
        **_base_layout(
            f"<b>Term Structure  ·  {label}{q_tag}</b><br>"
            f"<span style='font-size:11px;color:#6b7394'>"
            f"n = {n} symbols  ·  median  ·  ±1σ ±2σ bands</span>",
            height=height,
        ),
        xaxis=_ax("DTE (days) →",
                  tickmode="array", tickvals=DTE_X, ticktext=DTE_LABELS),
        yaxis=_ax(f"{label} →"),
    )
    return fig


# ── 2. HV LOOKBACK TERM STRUCTURE ────────────────────────────────
def build_hv_term_structure(
    df:              pd.DataFrame,
    show_iv_overlay: bool = False,
    show_quadrants:  bool = False,
    quadrant_filter: str  = "all",
    show_mean:       bool = False,
    height:          int  = 520,
) -> go.Figure:
    """
    HV term structure across HV_20 / HV_30 / HV_60 (lookback windows).
    Optional IV overlay at matched windows (14D~20D, 30D, 60D+1~60D).
    """
    dff, univ_label = _filter_quadrant(df, quadrant_filter)
    hv_data = _extract(dff, HV_COLS)
    s       = _stats(hv_data)
    n       = int(s["count"].mean())

    fig = go.Figure()
    _band_traces(fig, HV_X, s,
                 "rgba(77,217,217,0.18)", "rgba(77,217,217,0.08)")
    _median_trace(fig, HV_X, s, ACCENT,
                  f"HV Median  ({univ_label}  n={n})", show_mean)
    _quadrant_lines(fig, df, HV_COLS, HV_X, show_quadrants, quadrant_filter)

    if show_iv_overlay:
        iv_data = _extract(dff, IV_HV_MATCH_COLS)
        if not iv_data.empty:
            iv_s = _stats(iv_data)
            iv_n = int(iv_s["count"].mean())
            fig.add_trace(go.Scatter(
                x=IV_HV_MATCH_X + IV_HV_MATCH_X[::-1],
                y=np.concatenate([iv_s["median"] + iv_s["std"],
                                  (iv_s["median"] - iv_s["std"])[::-1]]).tolist(),
                fill="toself", fillcolor="rgba(255,179,64,0.12)",
                line=dict(width=0), showlegend=True,
                name="IV ±1σ band", hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=IV_HV_MATCH_X, y=iv_s["median"].tolist(),
                mode="lines+markers",
                name=f"IV Median  (n={iv_n})",
                line=dict(color="#ffb340", width=2.0, dash="dash"),
                marker=dict(size=6, color="#ffb340",
                            line=dict(width=1, color=BG)),
                customdata=np.stack([iv_s["median"], iv_s["std"],
                                     iv_s["count"]], axis=-1),
                hovertemplate=(
                    "<b>%{x}D</b>  "
                    "<span style='color:#ffb340'>IV Median</span>"
                    "  <b>%{customdata[0]:.3f}</b><br>"
                    "Std  <b>%{customdata[1]:.3f}</b>  "
                    "n  <b>%{customdata[2]}</b><extra></extra>"
                ),
            ))

    fig.update_layout(
        **_base_layout(
            "<b>HV Term Structure  ·  Lookback Windows</b><br>"
            f"<span style='font-size:11px;color:#6b7394'>"
            f"n = {n} symbols  ·  HV 20D / 30D / 60D  ·  ±1σ ±2σ bands"
            + ("  ·  IV overlay" if show_iv_overlay else "")
            + "</span>",
            height=height,
        ),
        xaxis=_ax("Lookback (days) →",
                  tickmode="array", tickvals=HV_X, ticktext=HV_LABELS),
        yaxis=_ax("Volatility (annualized) →"),
    )
    return fig


# ── 3. IV vs HV OVERLAY ───────────────────────────────────────────
def build_iv_hv_overlay(
    df:              pd.DataFrame,
    show_quadrants:  bool = False,
    quadrant_filter: str  = "all",
    height:          int  = 540,
) -> go.Figure:
    """
    IV (forward DTE) overlaid with HV (lookback) on a shared y-axis.
    Teal = IV across 14/30/60D+1/60D+2.
    Amber = HV across 20/30/60D lookback.
    Where IV > HV the market is pricing in more vol than realized.
    """
    dff, univ_label = _filter_quadrant(df, quadrant_filter)

    iv_data = _extract(dff, METRICS["atm_iv"]["cols"])
    hv_data = _extract(dff, HV_COLS)
    iv_s    = _stats(iv_data)
    hv_s    = _stats(hv_data)
    iv_n    = int(iv_s["count"].mean())
    hv_n    = int(hv_s["count"].mean())

    fig = go.Figure()

    # IV traces
    _band_traces(fig, DTE_X, iv_s,
                 "rgba(77,217,217,0.15)", "rgba(77,217,217,0.07)")
    _median_trace(fig, DTE_X, iv_s, ACCENT,
                  f"IV Median  ({univ_label}  n={iv_n})")

    # HV traces
    _band_traces(fig, HV_X, hv_s,
                 "rgba(255,179,64,0.15)", "rgba(255,179,64,0.07)")
    _median_trace(fig, HV_X, hv_s, "#ffb340",
                  f"HV Median  (n={hv_n})")

    # Quadrant lines for IV
    _quadrant_lines(fig, df, METRICS["atm_iv"]["cols"],
                    DTE_X, show_quadrants, quadrant_filter)

    q_tag = f"  ·  {quadrant_filter}" if quadrant_filter != "all" else ""
    fig.update_layout(
        **_base_layout(
            f"<b>IV vs HV  ·  Implied vs Realized Volatility{q_tag}</b><br>"
            "<span style='font-size:11px;color:#6b7394'>"
            "Teal = IV (forward DTE)  ·  Amber = HV (lookback)  ·  "
            "±1σ ±2σ bands</span>",
            height=height,
        ),
        xaxis=_ax("Days →"),
        yaxis=_ax("Volatility (annualized) →"),
    )
    return fig


# ── 4. SLOPE REGRESSION OVERLAY ───────────────────────────────────
def build_slope_overlay(
    df:              pd.DataFrame,
    metric:          str  = "put_atm",
    show_quadrants:  bool = False,
    quadrant_filter: str  = "all",
    height:          int  = 560,
) -> go.Figure:
    """
    Term structure with per-symbol OLS regression lines overlaid.

    For each symbol: fits y = a + b*x across the four DTE points.
    Shows median regression line + ±1σ slope band.
    Positive slope = contango (premium grows with DTE).
    Negative slope = backwardation (premium shrinks with DTE).
    """
    cfg   = METRICS.get(metric, METRICS["put_atm"])
    cols  = cfg["cols"]
    label = cfg["label"]

    dff, univ_label = _filter_quadrant(df, quadrant_filter)
    data = _extract(dff, cols)
    s    = _stats(data)
    n    = int(s["count"].mean())
    x    = np.array(DTE_X, dtype=float)

    fig = go.Figure()

    # Base ±1σ/±2σ data bands (faint)
    _band_traces(fig, DTE_X, s,
                 "rgba(77,217,217,0.10)", "rgba(77,217,217,0.05)")

    # Per-symbol OLS
    slopes, intercepts = [], []
    for _, row in data.iterrows():
        y_vals = row.values.astype(float)
        mask   = ~np.isnan(y_vals)
        if mask.sum() < 2:
            continue
        b, a = np.polyfit(x[mask], y_vals[mask], 1)
        slopes.append(b)
        intercepts.append(a)

    slopes     = np.array(slopes)
    intercepts = np.array(intercepts)

    med_slope = float(np.median(slopes))
    med_inter = float(np.median(intercepts))
    std_slope = float(np.std(slopes))
    std_inter = float(np.std(intercepts))

    med_line  = med_inter + med_slope * x
    upper_reg = (med_inter + std_inter) + (med_slope + std_slope) * x
    lower_reg = (med_inter - std_inter) + (med_slope - std_slope) * x

    # Regression ±1σ slope band
    fig.add_trace(go.Scatter(
        x=DTE_X + DTE_X[::-1],
        y=np.concatenate([upper_reg, lower_reg[::-1]]).tolist(),
        fill="toself", fillcolor="rgba(255,92,106,0.15)",
        line=dict(width=0), showlegend=True,
        name="Regression ±1σ slope", hoverinfo="skip",
    ))

    # Median regression line
    slope_sign = "↗" if med_slope > 0 else "↘"
    fig.add_trace(go.Scatter(
        x=DTE_X, y=med_line.tolist(),
        mode="lines",
        name=f"Median regression  {slope_sign}  slope = {med_slope:.5f}",
        line=dict(color="#ff5c6a", width=2.0, dash="dash"),
        hovertemplate=(
            "<b>%{x}D</b>  Regression <b>%{y:.3f}</b><extra></extra>"
        ),
    ))

    # Median data line on top
    _median_trace(fig, DTE_X, s, ACCENT,
                  f"Median  ({univ_label}  n={n})")

    # Per-quadrant regression lines
    if show_quadrants and quadrant_filter == "all":
        for q, color in Q_COLORS.items():
            q_data = _extract(df[df["quadrant"].str.startswith(q)], cols)
            if q_data.empty:
                continue
            q_slopes, q_ints = [], []
            for _, row in q_data.iterrows():
                y_vals = row.values.astype(float)
                mask   = ~np.isnan(y_vals)
                if mask.sum() < 2:
                    continue
                b, a = np.polyfit(x[mask], y_vals[mask], 1)
                q_slopes.append(b)
                q_ints.append(a)
            if not q_slopes:
                continue
            ms   = float(np.median(q_slopes))
            mi   = float(np.median(q_ints))
            sign = "↗" if ms > 0 else "↘"
            fig.add_trace(go.Scatter(
                x=DTE_X, y=(mi + ms * x).tolist(),
                mode="lines",
                name=f"{q} regression  {sign}  slope = {ms:.5f}",
                line=dict(color=color, width=1.5, dash="dot"),
                hovertemplate=(
                    f"<b>%{{x}}D</b>  "
                    f"<span style='color:{color}'>{q} regression</span>"
                    "  <b>%{y:.3f}</b><extra></extra>"
                ),
            ))

    q_tag = f"  ·  {quadrant_filter}" if quadrant_filter != "all" else ""
    fig.update_layout(
        **_base_layout(
            f"<b>Slope Overlay  ·  {label}{q_tag}</b><br>"
            "<span style='font-size:11px;color:#6b7394'>"
            f"n = {n} symbols  ·  teal = data median  ·  "
            f"red dashed = median OLS regression  ·  "
            f"universe slope = {med_slope:.5f}</span>",
            height=height,
        ),
        xaxis=_ax("DTE (days) →",
                  tickmode="array", tickvals=DTE_X, ticktext=DTE_LABELS),
        yaxis=_ax(f"{label} →"),
    )
    return fig


# ── 5. SLOPE DISTRIBUTION ─────────────────────────────────────────
def build_slope_distribution(
    df:              pd.DataFrame,
    quadrant_filter: str  = "all",
    height:          int  = 480,
) -> go.Figure:
    """
    Box chart of premium_slope_pct, iv_slope_pct, slope_div_pct
    split by quadrant.

    slope_div_pct > 0 means premium slope is growing faster than IV
    slope across DTE — favorable for put sellers in outer windows.
    """
    slope_cols = {
        "premium_slope_pct": ("Premium Slope",     ACCENT),
        "iv_slope_pct":      ("IV Slope",           "#ffb340"),
        "slope_div_pct":     ("Slope Divergence",   "#2bde9e"),
    }

    dff, _ = _filter_quadrant(df, quadrant_filter)
    present = [c for c in slope_cols if c in dff.columns]

    fig = go.Figure()

    for col in present:
        name, color = slope_cols[col]
        for q, qcolor in Q_COLORS.items():
            sub  = dff[dff["quadrant"].str.startswith(q)][col].dropna()
            if sub.empty:
                continue
            vals = (sub * 100).values if col == "slope_div_pct" else sub.values
            fig.add_trace(go.Box(
                y=vals,
                name=f"{name}  {q}",
                marker=dict(color=qcolor, opacity=0.75),
                line=dict(color=qcolor, width=1.5),
                fillcolor=qcolor + "22",
                boxmean=True,
                legendgroup=col,
                legendgrouptitle=dict(
                    text=name,
                    font=dict(size=10, color=color, family=MONO),
                ),
                hovertemplate=(
                    f"<b>{name}  {q}</b><br>"
                    "Value: %{y:.3f}<extra></extra>"
                ),
            ))

    q_tag = f"  ·  {quadrant_filter}" if quadrant_filter != "all" else ""
    fig.update_layout(
        **_base_layout(
            f"<b>Slope Distribution  ·  Premium / IV / Divergence{q_tag}</b><br>"
            "<span style='font-size:11px;color:#6b7394'>"
            "premium_slope_pct  ·  iv_slope_pct  ·  slope_div_pct  ·  "
            "cross = mean</span>",
            height=height,
        ),
        xaxis=_ax(showgrid=False),
        yaxis=_ax("Slope Value →"),
        boxmode="group",
    )
    return fig


# ── INTERACTIVE WIDGET ────────────────────────────────────────────
def show_term_structure_dashboard(df: pd.DataFrame):
    """
    Full interactive term structure dashboard in Jupyter.

    Five views selectable via toggle buttons:
      1. DTE Term Structure
      2. HV Term Structure
      3. IV vs HV Overlay
      4. Slope Overlay
      5. Slope Distribution

    Controls:
      - View toggle
      - Metric dropdown     (views 1, 4)
      - Quadrant filter     (all views)
      - Quadrant lines      (all views)
      - Mean line           (views 1, 2)
      - IV overlay          (view 2)

    Usage:
        from term_structure import show_term_structure_dashboard
        show_term_structure_dashboard(df)
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError:
        print("ipywidgets required: pip install ipywidgets")
        return

    view_toggle = widgets.ToggleButtons(
        options=[
            "DTE Term Structure",
            "HV Term Structure",
            "IV vs HV Overlay",
        ],
        value="DTE Term Structure",
        style={"button_width": "160px"},
    )

    metric_dd = widgets.Dropdown(
        options=[
            ("ATM Put Premium",      "put_atm"),
            ("Slight OTM Premium",   "premium_slight"),
            ("Moderate OTM Premium", "premium_moderate"),
            ("Far OTM Premium",      "premium_far"),
            ("ATM Implied Vol",      "atm_iv"),
            ("IV / HV Ratio",        "ratio"),
        ],
        value="put_atm",
        description="Metric:",
        style={"description_width": "60px"},
        layout=widgets.Layout(width="280px"),
    )

    quad_toggle = widgets.ToggleButtons(
        options=["all", "Q1", "Q2", "Q3", "Q4"],
        value="all",
        description="Filter:",
        style={"description_width": "50px", "button_width": "60px"},
    )

    show_quads_cb = widgets.Checkbox(
        value=False, description="Quadrant lines",
        indent=False, layout=widgets.Layout(width="180px"),
    )
    show_mean_cb = widgets.Checkbox(
        value=False, description="Mean line",
        indent=False, layout=widgets.Layout(width="140px"),
    )
    show_iv_cb = widgets.Checkbox(
        value=False, description="IV overlay  (HV view)",
        indent=False, layout=widgets.Layout(width="210px"),
    )

    out = widgets.Output()

    def update(*args):
        with out:
            out.clear_output(wait=True)
            v  = view_toggle.value
            qf = quad_toggle.value

            if v == "DTE Term Structure":
                fig = build_term_structure(
                    df, metric=metric_dd.value,
                    show_quadrants=show_quads_cb.value,
                    quadrant_filter=qf,
                    show_mean=show_mean_cb.value,
                )
            elif v == "HV Term Structure":
                fig = build_hv_term_structure(
                    df,
                    show_iv_overlay=show_iv_cb.value,
                    show_quadrants=show_quads_cb.value,
                    quadrant_filter=qf,
                    show_mean=show_mean_cb.value,
                )
            elif v == "IV vs HV Overlay":
                fig = build_iv_hv_overlay(
                    df,
                    show_quadrants=show_quads_cb.value,
                    quadrant_filter=qf,
                )
            fig.show()

	## -- Add feature to remove dropdown for views that do not require ->    
    def toggle_metric(change):
        metric_dd.layout.display  = "flex" if change["new"] == "DTE Term Structure" else "none"
        show_iv_cb.layout.display = "flex" if change["new"] == "HV Term Structure"  else "none"
    view_toggle.observe(toggle_metric, names="value")
    
    # Set initial visibility state on load
    metric_dd.layout.display  = "flex"   # visible — default view is DTE Term Structure
    show_iv_cb.layout.display = "none"   # hidden — default view is not HV Term Structure

    for w in [view_toggle, metric_dd, quad_toggle,
              show_quads_cb, show_mean_cb, show_iv_cb]:
        w.observe(update, names="value")

    controls = widgets.VBox([
        view_toggle,
        widgets.HBox([metric_dd, show_quads_cb, show_mean_cb, show_iv_cb]),
        quad_toggle,
    ])

    display(controls, out)
    update()

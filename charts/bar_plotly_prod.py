
"""
charts/bar.py
────────────────────────────────────────────────────────────────────────
Horizontal bar chart builder for options scan DataFrame.
All design tokens imported from theme.py.

Usage (Jupyter):
    from charts.bar import build_bar, show_bar_dashboard
    show_bar_dashboard(df)

Usage (Dash app):
    from charts.bar import build_bar
    fig = build_bar(df, score_col='premium_score', top_n=20,
                    title='Top Premium Score')
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from theme import (
    BG, PANEL, GRID, CROSS,
    TEXT_PRI, TEXT_AX, AX_TITLE, ACCENT,
    Q_COLORS, MONO,
)

# ── HOVER COLUMNS ─────────────────────────────────────────────────
# Pulled into customdata for the hover tooltip.
# _safe_hover_cols() filters to only those present in the DataFrame.

HOVER_COLS = [
    "quadrant",
    # Premium
    "premium_slight_14",
    "premium_slight_30",
    "prem_per_hv30_14",         # premium vs what stock actually moves
    # IV vs HV
    "ratio_14",
    "ratio_30",
    "signal_30",                # readable IV/HV category
    # Realized vol
    "HV_30",                    # absolute vol level
    "relative_vol_spy",         # how much more volatile than market
    # Spikes
    "spike_signal_universe",
    "spike_pct_universe",
    # Term structure
    "slope_div_pct",
]

# ── PRESET VIEW DEFINITIONS ───────────────────────────────────────
PRESETS = [
    {
        "label":     "a. Top Global Premium Score",
        "score_col": "premium_score",
        "ascending": False,
        "df_filter": None,
        "title":     "Top Put Symbols by Premium Score",
    },
    {
        "label":     "b. Lowest Global Risk Score",
        "score_col": "risk_score",
        "ascending": True,
        "df_filter": None,
        "title":     "Top Put Symbols by Lowest Risk Score",
    },
    {
        "label":     "c. Top Global Risk Scores",
        "score_col": "risk_score",
        "ascending": False,
        "df_filter": None,
        "title":     "Top Risk Scores",
    },
	{
        "label":     "d. Q1 Only — Top Premium Score",
        "score_col": "premium_score",
        "ascending": False,
        "df_filter": lambda df: df[df["quadrant"].str.startswith("Q1")],
        "title":     "Q1 Only  ·  Top Premium Score",
    },
    {
        "label":     "e. Q2 Only — Lowest Risk Score",
        "score_col": "risk_score",
        "ascending": True,
        "df_filter": lambda df: df[df["quadrant"].str.startswith("Q2")],
        "title":     "Q2 Only  ·  Lowest Risk Score",
    },
	{
        "label":     "f. Top Premium - 14DTE / Slight OTM",
        "score_col": "premium_slight_14",
        "ascending": False,
        "df_filter": None,
        "title":     "Top Symbols by Premium 14D at Slight OTM",
    },
    {
        "label":     "g. Top 60D Spike Magnitude (count > 3)",
        "score_col": "max_spike_pct_60",
        "ascending": False,
        "df_filter": lambda df: df.query("spike_count_60 > 3"),
        "title":     "Top 60D Spike Magnitude Where Frequency > 3",
    },
    {
        "label":     "h. Top Straddle 14D",
        "score_col": "straddle_14",
        "ascending": False,
        "df_filter": None,
        "title":     "Top Symbols by Straddle Premium 14D",
    },
    {
        "label":     "i. Top IV/HV Ratio 14D",
        "score_col": "ratio_14",
        "ascending": False,
        "df_filter": None,
        "title":     "Top Symbols by IV/HV Ratio 14D  (IV most elevated vs realized vol)",
    },
    {
        "label":     "j. Top Prem/IV Efficiency 14D",
        "score_col": "prem_per_iv_primary_14",
        "ascending": False,
        "df_filter": None,
        "title":     "Top Symbols by Premium / IV Efficiency 14D",
    },
    {
        "label":     "k. Top Slope Divergence by Pct. Rank",
        "score_col": "slope_div_pct",
        "ascending": False,
        "df_filter": None,
        "title":     "Top Symbols by Premium vs IV Slope Divergence (%)",
    },
]


# ── HELPERS ───────────────────────────────────────────────────────
def _base_layout(title_text: str, height: int = 500) -> dict:
    return dict(
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        height=height,
        margin=dict(l=80, r=40, t=72, b=52),
        title=dict(
            text=title_text,
            x=0.03,
            font=dict(family=MONO, color=TEXT_PRI, size=14),
        ),
        legend=dict(
            bgcolor=BG, bordercolor=CROSS, borderwidth=1,
            font=dict(size=10, color=TEXT_PRI, family=MONO),
        ),
        font=dict(family=MONO, color=TEXT_PRI, size=11),
        hoverlabel=dict(
            bgcolor="#1a1d28", bordercolor=CROSS,
            font=dict(size=12, color=TEXT_PRI, family=MONO),
            namelength=0,
        ),
    )


def _safe_hover_cols(df: pd.DataFrame) -> list:
    """Return only HOVER_COLS that exist in the DataFrame."""
    return [c for c in HOVER_COLS if c in df.columns]


# ── CORE FIGURE BUILDER ───────────────────────────────────────────
def build_bar(
    df:        pd.DataFrame,
    score_col: str,
    top_n:     int  = 20,
    title:     str  = "",
    ascending: bool = False,
    df_filter       = None,
) -> go.Figure:
    """
    Build a horizontal bar chart for a given score column.

    Parameters
    ----------
    df         : master scan DataFrame
    score_col  : column to rank and plot on x-axis
    top_n      : number of symbols to show
    title      : chart title string
    ascending  : False = nlargest (highest = best)
                 True  = nsmallest (lowest = best, e.g. risk_score)
    df_filter  : optional callable lambda df: df.query(...) applied before ranking

    Returns
    -------
    go.Figure
    """
    # Apply optional pre-filter
    dff = df_filter(df) if df_filter else df

    # Guard — score_col must exist
    if score_col not in dff.columns:
        fig = go.Figure()
        fig.update_layout(
            **_base_layout(f"Column '{score_col}' not found in DataFrame")
        )
        return fig

    # Select top/bottom N
    if ascending:
        sub = dff.nsmallest(top_n, score_col)
    else:
        sub = dff.nlargest(top_n, score_col)

    # Pull hover columns that exist in the DataFrame
    h_cols = _safe_hover_cols(dff)

    # Deduplicate keep list — score_col may already appear in h_cols
    keep = ["symbol", "quadrant", score_col] + [
        c for c in h_cols if c not in ("quadrant", score_col, "symbol")
    ]
    sub = sub[keep].copy()

    # Sort for horizontal bar display (highest at top)
    sub = sub.sort_values(score_col, ascending=not ascending)

    # Scale pct-rank columns to % for display
    if "slope_div_pct" in sub.columns:
        sub["slope_div_pct"] = (sub["slope_div_pct"] * 100).round(1)
    if "spike_pct_universe" in sub.columns:
        sub["spike_pct_universe"] = (sub["spike_pct_universe"] * 100).round(1)

    # Bar colors by quadrant
    bar_colors = [Q_COLORS.get(str(q)[:2], ACCENT) for q in sub["quadrant"]]

    # Build customdata — quadrant always [0], score_col always [1], rest follow
    # Exclude score_col and quadrant from h_cols to prevent duplicates
    cd_cols = ["quadrant", score_col] + [
        c for c in h_cols if c not in ("quadrant", score_col)
    ]
    for c in cd_cols:
        if c not in sub.columns:
            sub[c] = np.nan
    customdata = sub[cd_cols].values

    # ── Hover template ────────────────────────────────────────────
    # cidx maps column name → integer position in customdata
    cidx = {col: i for i, col in enumerate(cd_cols)}

    hover = (
        "<span style='font-size:14px;font-weight:700;color:#edf0f7'>"
        "%{y}</span><br>"
        "<span style='color:#4a5270'>──────────────────────</span><br>"
        f"{score_col.replace('_', ' ').title()}  <b>%{{customdata[1]:.2f}}</b><br>"
        "Quadrant  <b>%{customdata[0]}</b><br>"

        "<span style='color:#4a5270'>── Premium ───────────</span><br>"
        f"Slight OTM 14D       <b>%{{customdata[{cidx['premium_slight_14']}]:.4f}}</b><br>"
        f"Slight OTM 30D       <b>%{{customdata[{cidx['premium_slight_30']}]:.4f}}</b><br>"
        f"Premium Per HV30 14D <b>%{{customdata[{cidx['prem_per_hv30_14']}]:.4f}}</b><br>"

        "<span style='color:#4a5270'>── IV / HV ───────────</span><br>"
        f"IV/HV Ratio 14D      <b>%{{customdata[{cidx['ratio_14']}]:.4f}}</b><br>"
        f"IV/HV Ratio 30D      <b>%{{customdata[{cidx['ratio_30']}]:.4f}}</b><br>"
        f"IV/HV Category 30D   <b>%{{customdata[{cidx['signal_30']}]}}</b><br>"

        "<span style='color:#4a5270'>── Realized Vol ──────</span><br>"
        f"HV 30D               <b>%{{customdata[{cidx['HV_30']}]:.4f}}</b><br>"
        f"Vol Relative SPY     <b>%{{customdata[{cidx['relative_vol_spy']}]:.4f}}</b><br>"

        "<span style='color:#4a5270'>── Vol Spike ─────────</span><br>"
        f"Spike Signal Global  <b>%{{customdata[{cidx['spike_signal_universe']}]}}</b><br>"
        f"Spike Pct Global     <b>%{{customdata[{cidx['spike_pct_universe']}]:.2f}}%</b><br>"

        "<span style='color:#4a5270'>── Premium Slope ─────</span><br>"
        f"Slope Divergence     <b>%{{customdata[{cidx['slope_div_pct']}]:.1f}}%</b><br>"

        "<extra></extra>"
    )

    # ── Figure ────────────────────────────────────────────────────
    n_filtered = len(dff)
    subtitle = (
        f"n = {len(sub)} of {n_filtered} symbols"
        + (f"  ·  filtered from {len(df)}" if df_filter else "")
    )

    fig = go.Figure(go.Bar(
        x=sub[score_col],
        y=sub["symbol"],
        orientation="h",
        marker=dict(color=bar_colors, line=dict(width=0)),
        customdata=customdata,
        hovertemplate=hover,
        text=sub[score_col].round(2),
        textposition="outside",
        textfont=dict(size=11, color=TEXT_AX),
    ))

    fig.update_layout(
        **_base_layout(
            f"<b>{title}</b><br>"
            f"<span style='font-size:11px;color:#6b7394'>{subtitle}</span>",
            height=max(380, top_n * 28 + 105),
        ),
        xaxis=dict(
            title=dict(
                text=score_col.replace("_", " ").title(),
                font=dict(size=13, color=AX_TITLE, family=MONO),
            ),
            gridcolor=GRID, gridwidth=1, zeroline=False,
            linecolor="#363b50", linewidth=1,
            tickfont=dict(size=13, color=TEXT_AX, family=MONO),
            ticklen=5, showgrid=True,
        ),
        yaxis=dict(
            gridcolor=GRID, zeroline=False,
            linecolor="#363b50", linewidth=1,
            tickfont=dict(size=12, color=TEXT_PRI, family=MONO),
        ),
        bargap=0.28,
    )

    return fig


# ── INTERACTIVE WIDGET (Jupyter) ──────────────────────────────────
def show_bar_dashboard(df: pd.DataFrame):
    """
    Launch interactive bar chart dashboard in Jupyter using ipywidgets.

    Controls:
      - Preset dropdown   (a–k predefined views + Custom)
      - Top-N slider      (5–50)
      - Custom score_col  (visible when Custom selected)
      - Custom filter     (e.g. spike_count_60 > 3)

    Usage:
        from charts.bar import show_bar_dashboard
        show_bar_dashboard(df)
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError:
        print("ipywidgets required: pip install ipywidgets")
        return

    valid_presets = [p for p in PRESETS if p["score_col"] in df.columns]
    preset_opts   = [(p["label"], i) for i, p in enumerate(valid_presets)] + [("z. Custom", -1)]

    preset_dd = widgets.Dropdown(
        options=preset_opts,
        value=0,
        description="View:",
        style={"description_width": "50px"},
        layout=widgets.Layout(width="400px"),
    )

    topn_slider = widgets.IntSlider(
        value=20, min=5, max=50, step=1,
        description="Top N:",
        style={"description_width": "55px"},
        layout=widgets.Layout(width="300px"),
    )

    custom_col = widgets.Text(
        value="premium_score",
        description="Column:",
        placeholder="e.g. premium_score",
        style={"description_width": "60px"},
        layout=widgets.Layout(width="280px"),
    )

    custom_asc = widgets.Checkbox(
        value=False,
        description="Ascending (lowest = best)",
        indent=False,
        layout=widgets.Layout(width="240px"),
    )

    custom_filter = widgets.Text(
        value="",
        description="Filter:",
        placeholder="e.g. spike_count_60 > 3",
        style={"description_width": "50px"},
        layout=widgets.Layout(width="320px"),
    )

    custom_box = widgets.VBox([
        widgets.HBox([custom_col, custom_asc]),
        custom_filter,
    ], layout=widgets.Layout(display="none"))

    out = widgets.Output()

    def toggle_custom(change):
        custom_box.layout.display = "flex" if change["new"] == -1 else "none"

    preset_dd.observe(toggle_custom, names="value")

    def update(*args):
        with out:
            out.clear_output(wait=True)
            idx = preset_dd.value
            if idx == -1:
                col    = custom_col.value.strip()
                asc    = custom_asc.value
                filt_s = custom_filter.value.strip()
                filt   = (lambda df, q=filt_s: df.query(q)) if filt_s else None
                fig    = build_bar(df, score_col=col, top_n=topn_slider.value,
                                   title=f"Custom  ·  {col}",
                                   ascending=asc, df_filter=filt)
            else:
                p   = valid_presets[idx]
                fig = build_bar(
                    df,
                    score_col=p["score_col"],
                    top_n=topn_slider.value,
                    title=p["title"],
                    ascending=p["ascending"],
                    df_filter=p["df_filter"],
                )
            fig.show()

    for w in [preset_dd, topn_slider, custom_col, custom_asc, custom_filter]:
        w.observe(update, names="value")

    display(widgets.VBox([
        widgets.HBox([preset_dd, topn_slider]),
        custom_box,
    ]), out)
    update()
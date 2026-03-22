
"""
hist_dashboard.py
────────────────────────────────────────────────────────────────────────
Interactive histogram dashboard for options scan DataFrame.
Built with Plotly + ipywidgets for Jupyter iteration.

Usage:
    from hist_dashboard import show_histogram_dashboard
    show_histogram_dashboard(df)

Or build individual figures:
    from hist_dashboard import build_histogram
    fig = build_histogram(df, metric='premium_slight_14', bins=25, view='all')
    fig.show()

Requires:
    pip install plotly ipywidgets scipy
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

# ── AVAILABLE METRICS ─────────────────────────────────────────────
METRICS = {
 	"premium_atm_14":         "ATM Premium 14D (%)",
    "premium_atm_30":         "ATM Premium 30D (%)",
    "premium_slight_14":      "Slight OTM Premium 14D (%)",
    "premium_slight_30":      "Slight OTM Premium 30D (%)",
    "premium_moderate_14":    "Moderate OTM Premium 14D (%)",
    "premium_moderate_30":    "Moderate OTM  Premium 30D (%)",
    "straddle_14":            "Straddle 14D (%)",
    "straddle_30":            "Straddle 30D (%)",
 	"premium_slope":		  "Premium Slope",		
 	"iv_slope":				  "IV Slope",
    "slope_divergence":		  "Premium / IV Slope Divergence",		
    "HV_20":                  "Hist. Vol. 20D (annualized)",
    "HV_30": 				  "Hist. Vol. 30D (annualized)",
    "HV_60":                  "Hist. Vol. 60D (annualized)",
    "ratio_14":               "IV/HV Ratio 14D",
    "ratio_30":               "IV/HV Ratio 30D",
    "spike_count_30":         "Spike Count 30D",
    "spike_count_60":         "Spike Count 60D",
 	"avg_spike_pct_30":       "Avg. Spike Magnitude 30D (%)",
	"avg_spike_pct_60":       "Avg. Spike Magnitude 60D (%)",
    "prem_per_iv_primary_14": "Prem / IV Primary 14D",
    "prem_per_iv_primary_30": "Prem / IV Primary 30D",
    "premium_score":          "Premium Score",
    "risk_score":             "Risk Score",			
}


# ── HELPERS ───────────────────────────────────────────────────────
def _quad_key(q_str: str) -> str:
    """Extract Q1/Q2/Q3/Q4 from full quadrant label string."""
    return str(q_str)[:2] if pd.notna(q_str) else None


def _get_values(df: pd.DataFrame, metric: str,
                view: str = "all") -> pd.DataFrame:
    """
    Return filtered subset for the given metric and view.
    view : 'all' | 'Q1' | 'Q2' | 'Q3' | 'Q4'
    """
    sub = df[["symbol", metric, "quadrant"]].dropna(subset=[metric]).copy()
    sub["_quad"] = sub["quadrant"].apply(_quad_key)
    if view != "all":
        sub = sub[sub["_quad"] == view]
    return sub


def _stats(vals: np.ndarray) -> dict:
    if len(vals) == 0:
        return {}
    return {
        "n":      len(vals),
        "mean":   float(np.mean(vals)),
        "median": float(np.median(vals)),
        "std":    float(np.std(vals)),
        "min":    float(np.min(vals)),
        "max":    float(np.max(vals)),
        "p25":    float(np.percentile(vals, 25)),
        "p75":    float(np.percentile(vals, 75)),
    }


def _kde_curve(vals: np.ndarray, n_points: int = 200) -> tuple:
    """Gaussian KDE using scipy if available, else manual."""
    try:
        from scipy.stats import gaussian_kde
        kde = gaussian_kde(vals, bw_method="silverman")
        x = np.linspace(vals.min(), vals.max(), n_points)
        return x, kde(x)
    except ImportError:
        bw = 1.06 * np.std(vals) * len(vals) ** (-0.2)
        x = np.linspace(vals.min(), vals.max(), n_points)
        y = np.array([
            np.sum(np.exp(-0.5 * ((x[i] - vals) / bw) ** 2) /
                   (bw * np.sqrt(2 * np.pi))) / len(vals)
            for i in range(n_points)
        ])
        return x, y


def _layout(title_text: str, height: int = 480) -> dict:
    return dict(
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        height=height,
        margin=dict(l=72, r=160, t=72, b=64),
        title=dict(
            text=title_text,
            x=0.03,
            font=dict(family=MONO, color=TEXT_PRI, size=15),
        ),
        legend=dict(
            bgcolor=BG,
            bordercolor=CROSS,
            borderwidth=1,
            font=dict(size=10.5, color=TEXT_PRI, family=MONO),
            x=1.02, y=1, xanchor="left", yanchor="top",
        ),
        font=dict(family=MONO, color=TEXT_PRI, size=11),
        hoverlabel=dict(
            bgcolor="#1a1d28",
            bordercolor=CROSS,
            font=dict(size=12, color=TEXT_PRI, family=MONO),
        ),
        barmode="overlay",
    )


def _ax(title: str = "", **kw) -> dict:
    base = dict(
        title=dict(text=title, font=dict(size=12, color=AX_TITLE, family=MONO)),
        gridcolor=GRID, gridwidth=1,
        zeroline=False,
        linecolor="#363b50", linewidth=1,
        tickfont=dict(size=12, color=TEXT_AX, family=MONO),
        ticklen=5, showgrid=True,
    )
    base.update(kw)
    return base


# ── CORE FIGURE BUILDER ───────────────────────────────────────────
def build_histogram(
    df:          pd.DataFrame,
    metric:      str  = "premium_slight_14",
    bins:        int  = 25,
    view:        str  = "all",     # 'all' | 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'overlay'
    show_kde:    bool = False,
    show_median: bool = False,
    show_mean:   bool = False,
    height:      int  = 700,
) -> go.Figure:
    """
    Build a histogram figure for the given metric and view.

    Parameters
    ----------
    df          : master scan DataFrame
    metric      : column name to plot
    bins        : number of histogram bins
    view        : 'all'     — all symbols, single teal bar
                  'Q1'-'Q4' — single quadrant, quadrant color
                  'overlay' — all four quadrants overlaid, each quadrant color
    show_kde    : overlay KDE density curve
    show_median : add dashed median reference line
    show_mean   : add dashed mean reference line
    height      : figure height in pixels

    Returns
    -------
    go.Figure
    """
    metric_label = METRICS.get(metric, metric.replace("_", " ").title())
    fig = go.Figure()

    if view == "overlay":
        # All four quadrants overlaid — each in quadrant color
        all_vals = []
        for q, color in Q_COLORS.items():
            sub = _get_values(df, metric, view=q)
            vals = sub[metric].values
            if len(vals) == 0:
                continue
            all_vals.extend(vals.tolist())
            fig.add_trace(go.Histogram(
                x=vals,
                name=f"{Q_LABELS[q]}  ({len(vals)})",
                nbinsx=bins,
                marker=dict(
                    color=color,
                    opacity=0.55,
                    line=dict(width=0),
                ),
                hovertemplate=(
                    f"<b style='color:{color}'>{q}</b><br>"
                    "Range: %{x}<br>"
                    "Count: %{y}<extra></extra>"
                ),
            ))

            if show_kde and len(vals) > 5:
                x_kde, y_kde = _kde_curve(vals)
                # Scale KDE to histogram counts
                bin_width = (vals.max() - vals.min()) / bins
                scale = len(vals) * bin_width
                fig.add_trace(go.Scatter(
                    x=x_kde, y=y_kde * scale,
                    mode="lines",
                    name=f"KDE {q}",
                    line=dict(color=color, width=2),
                    opacity=0.9,
                    hoverinfo="skip",
                ))

        title_text = (
            f"<b>{metric_label}  ·  All Quadrants Overlaid</b><br>"
            f"<span style='font-size:11px;color:#6b7394'>"
            f"n = {len(df[[metric]].dropna())} symbols  ·  bins = {bins}</span>"
        )

    else:
        # Single view — all or one quadrant
        sub = _get_values(df, metric, view=view)
        vals = sub[metric].values

        if view == "all":
            color = ACCENT
            view_label = f"All symbols  ({len(vals)})"
        else:
            color = Q_COLORS.get(view, ACCENT)
            view_label = f"{Q_LABELS.get(view, view)}  ({len(vals)})"

        fig.add_trace(go.Histogram(
            x=vals,
            name=view_label,
            nbinsx=bins,
            marker=dict(
                color=color,
                opacity=0.70,
                line=dict(width=0.5, color=BG),
            ),
            hovertemplate=(
                "Range: %{x}<br>"
                "Count: %{y}<extra></extra>"
            ),
        ))

        if show_kde and len(vals) > 5:
            x_kde, y_kde = _kde_curve(vals)
            bin_width = (vals.max() - vals.min()) / bins if bins > 0 else 1
            scale = len(vals) * bin_width
            fig.add_trace(go.Scatter(
                x=x_kde, y=y_kde * scale,
                mode="lines",
                name="KDE",
                line=dict(color=TEXT_PRI, width=2, dash="solid"),
                opacity=0.80,
                hoverinfo="skip",
            ))

        # Reference lines
        s = _stats(vals)
        if show_median and s:
            fig.add_vline(
                x=s["median"],
                line=dict(color=ACCENT, width=1.5, dash="dot"),
            )
            fig.add_annotation(
                x=s["median"], y=1.0, yref="paper",
                text=f"  Median {s['median']:.3f}",
                showarrow=False,
                font=dict(size=9, color=ACCENT, family=MONO),
                xanchor="left", yanchor="top",
            )
        if show_mean and s:
            fig.add_vline(
                x=s["mean"],
                line=dict(color="#ffb340", width=1.5, dash="dot"),
            )
            fig.add_annotation(
                x=s["mean"], y=0.88, yref="paper",
                text=f"  Mean {s['mean']:.3f}",
                showarrow=False,
                font=dict(size=9, color="#ffb340", family=MONO),
                xanchor="left", yanchor="top",
            )

        # Stats annotation box
        if s:
            ann_text = (
                f"n = {s['n']}<br>"
                f"mean = {s['mean']:.3f}<br>"
                f"median = {s['median']:.3f}<br>"
                f"std = {s['std']:.3f}<br>"
                f"min = {s['min']:.3f}<br>"
                f"max = {s['max']:.3f}"
            )
            fig.add_annotation(
                x=1.02, y=0.98, xref="paper", yref="paper",
                text=ann_text,
                showarrow=False,
                font=dict(size=10, color=TEXT_AX, family=MONO),
                xanchor="left", yanchor="top",
                bgcolor="#1a1d28",
                bordercolor=CROSS,
                borderpad=8,
                borderwidth=1,
            )

        view_str = "All symbols" if view == "all" else Q_LABELS.get(view, view)
        title_text = (
            f"<b>{metric_label}  ·  {view_str}</b><br>"
            f"<span style='font-size:11px;color:#6b7394'>"
            f"n = {len(vals)} symbols  ·  bins = {bins}</span>"
        )

    fig.update_layout(
        **_layout(title_text, height=height),
        xaxis=_ax(metric_label),
        yaxis=_ax("Count →"),
    )

    return fig


# ── MULTI-METRIC COMPARE ──────────────────────────────────────────
def build_histogram_compare(
    df:      pd.DataFrame,
    metrics: list,
    view:    str = "all",
    bins:    int = 25,
    height:  int = 500,
) -> go.Figure:
    """
    Overlay multiple metrics in one histogram for comparison.
    Useful for e.g. premium_slight_14 vs premium_slight_30 side by side.

    Parameters
    ----------
    metrics : list of column names, max 4 recommended
    view    : 'all' | 'Q1' | 'Q2' | 'Q3' | 'Q4'
    """
    palette = [ACCENT, "#ffb340", "#2bde9e", "#ff5c6a"]
    fig = go.Figure()

    for i, metric in enumerate(metrics):
        sub  = _get_values(df, metric, view=view)
        vals = sub[metric].values
        color = palette[i % len(palette)]
        label = METRICS.get(metric, metric)

        fig.add_trace(go.Histogram(
            x=vals,
            name=f"{label}  ({len(vals)})",
            nbinsx=bins,
            marker=dict(color=color, opacity=0.60, line=dict(width=0)),
            hovertemplate=f"<b>{label}</b><br>Range: %{{x}}<br>Count: %{{y}}<extra></extra>",
        ))

    view_str = "All symbols" if view == "all" else Q_LABELS.get(view, view)
    fig.update_layout(
        **_layout(
            f"<b>Metric Comparison  ·  {view_str}</b><br>"
            f"<span style='font-size:11px;color:#6b7394'>"
            f"bins = {bins}</span>",
            height=height,
        ),
        xaxis=_ax("Value"),
        yaxis=_ax("Count →"),
    )
    return fig


# ── INTERACTIVE WIDGET (Jupyter) ──────────────────────────────────
def show_histogram_dashboard(df: pd.DataFrame):
    """
    Launch interactive histogram dashboard in Jupyter using ipywidgets.

    Controls:
      - Metric dropdown
      - Bins slider
      - View toggle (All / Q1 / Q2 / Q3 / Q4 / Overlay)
      - KDE, Median, Mean toggles

    Usage:
        from hist_dashboard import show_histogram_dashboard
        show_histogram_dashboard(df)
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
        import plotly.graph_objects as go
    except ImportError:
        print("ipywidgets required: pip install ipywidgets")
        return

    # Controls
    metric_dd = widgets.Dropdown(
        options=[(v, k) for k, v in METRICS.items() if k in df.columns],
        value="premium_slight_14" if "premium_slight_14" in df.columns else list(METRICS.keys())[0],
        description="Metric:",
        style={"description_width": "60px"},
        layout=widgets.Layout(width="320px"),
    )

    bins_slider = widgets.IntSlider(
        value=25, min=5, max=60, step=1,
        description="Bins:",
        style={"description_width": "40px"},
        layout=widgets.Layout(width="280px"),
    )

    view_toggle = widgets.ToggleButtons(
        options=["all", "Q1", "Q2", "Q3", "Q4", "overlay"],
        value="all",
        description="View:",
        style={"description_width": "40px",
               "button_width": "70px"},
    )

    kde_cb    = widgets.Checkbox(value=False, description="KDE",    indent=False, layout=widgets.Layout(width="80px"))
    median_cb = widgets.Checkbox(value=False, description="Median", indent=False, layout=widgets.Layout(width="90px"))
    mean_cb   = widgets.Checkbox(value=False, description="Mean",   indent=False, layout=widgets.Layout(width="80px"))

    out = widgets.Output()

    def update(*args):
        with out:
            out.clear_output(wait=True)
            fig = build_histogram(
                df,
                metric=metric_dd.value,
                bins=bins_slider.value,
                view=view_toggle.value,
                show_kde=kde_cb.value,
                show_median=median_cb.value,
                show_mean=mean_cb.value,
            )
            fig.show()

    metric_dd.observe(update, names="value")
    bins_slider.observe(update, names="value")
    view_toggle.observe(update, names="value")
    kde_cb.observe(update, names="value")
    median_cb.observe(update, names="value")
    mean_cb.observe(update, names="value")

    controls = widgets.VBox([
        widgets.HBox([metric_dd, bins_slider]),
        view_toggle,
        widgets.HBox([kde_cb, median_cb, mean_cb]),
    ])

    display(controls, out)
    update()


# ── QUICK TEST ────────────────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np
    rng = np.random.default_rng(42)
    n = 200
    mock = pd.DataFrame({
        "symbol":           [f"SYM{i}" for i in range(n)],
        "premium_slight_14": rng.beta(2, 5, n) * 10,
        "premium_slight_30": rng.beta(2, 4, n) * 14,
        "HV_20":             rng.beta(2, 3, n) * 2,
        "ratio_14":          rng.normal(1.1, 0.3, n),
        "avg_spike_pct_30":  rng.exponential(5, n),
        "quadrant": rng.choice(
            ["Q1 High Premium / Low Risk", "Q2 High Premium / High Risk",
             "Q3 Low Premium  / Low Risk", "Q4 Low Premium  / High Risk"], n
        ),
        "premium_score": rng.normal(0, 1, n),
        "risk_score":    rng.normal(0, 0.5, n),
    })

    fig = build_histogram(mock, metric="premium_slight_14", bins=25,
                          view="all", show_kde=True, show_median=True)
    fig.show()

    fig2 = build_histogram(mock, metric="premium_slight_14", bins=25, view="overlay")
    fig2.show()

    fig3 = build_histogram_compare(mock, ["premium_slight_14","premium_slight_30"], view="all")
    fig3.show()
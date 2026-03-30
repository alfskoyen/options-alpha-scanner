"""
app_screener.py
────────────────────────────────────────────────────────────────────────
Options Put-Selling Screener — Main Dash Application

Tabs:
  1. Scatter        — Risk × Premium quadrant maps (global + per-quadrant)
  2. Rankings       — Top-N bar charts (premium, risk, spike, slope)
  3. Distributions  — Histogram dashboard (any metric, any quadrant)
  4. Term Structure — Premium / IV / HV across DTE windows
  5. Screening Table — Sortable filterable data table

Run locally:
    python app.py
    → http://127.0.0.1:8050

Deploy to Render:
    Render reads render.yaml automatically — just push to GitHub.

Data:
    Drop a CSV into data/ matching option_scores_YYYY_MM_DD.csv
    See data.py and README.md for the full data pipeline description.
"""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html

from data_prep import load_data, prep_data, get_scan_meta
from theme import (
    BG, PANEL, BORDER, CROSS, TEXT_PRI, TEXT_SEC,
    ACCENT, Q_COLORS, Q_LABELS, MONO,
)

from charts.scatter_plotly_prod   import _scatter_global_view, _scatter_quadrant_top_n
from charts.bar_plotly_prod   import build_bar
from charts.histo_plotly_prod     import build_histogram
from charts.term_struc_plotly_prod import (
    build_term_structure, build_hv_term_structure, build_iv_hv_overlay,)
from charts.table_plotly_prod import register_table_callbacks, _build_datatable

# ── Bootstrap ─────────────────────────────────────────────────────
df   = prep_data(load_data())
meta = get_scan_meta(df)

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.SLATE,
        "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600&display=swap",
    ],
    title="Options Screener",
    suppress_callback_exceptions=True,
)

server = app.server   # Gunicorn entry point for Render / Heroku

# ── Global CSS ────────────────────────────────────────────────────
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* ── Page ───────────────────────────────────── */
            body {
                background-color: #1e2127 !important;
                font-family: "JetBrains Mono", monospace !important;
                margin: 0;
            }
 
            /* ── dcc.Dropdown outer container ────────────── */
            .Select-control {
                background-color: #1e2127 !important;
                border: 1px solid #2e3340 !important;
                color: #edf0f7 !important;
            }
            .Select-control:hover {
                border-color: #4a5270 !important;
                box-shadow: none !important;
            }
            .is-open > .Select-control {
                border-color: #4dd9d9 !important;
            }
 
            /* ── Selected value text ─────────────────────── */
            .Select-value-label,
            .Select--single > .Select-control .Select-value {
                color: #edf0f7 !important;
                font-family: "JetBrains Mono", monospace !important;
                font-size: 12px !important;
            }
 
            /* ── Placeholder ─────────────────────────────── */
            .Select-placeholder {
                color: #8b93b0 !important;
                font-family: "JetBrains Mono", monospace !important;
                font-size: 12px !important;
            }
 
            /* ── Input text ──────────────────────────────── */
            .Select-input > input {
                color: #edf0f7 !important;
                font-family: "JetBrains Mono", monospace !important;
            }
 
            /* ── Arrow ───────────────────────────────────── */
            .Select-arrow {
                border-top-color: #8b93b0 !important;
            }
            .is-open .Select-arrow {
                border-bottom-color: #4dd9d9 !important;
            }
 
            /* ── Dropdown menu container ─────────────────── */
            .Select-menu-outer {
                background-color: #1e2127 !important;
                border: 1px solid #2e3340 !important;
                box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
                z-index: 9999 !important;
            }
            .Select-menu {
                background-color: #1e2127 !important;
            }
 
            /* ── Individual option ───────────────────────── */
            .Select-option {
                background-color: #1e2127 !important;
                color: #edf0f7 !important;
                font-family: "JetBrains Mono", monospace !important;
                font-size: 12px !important;
                padding: 8px 12px !important;
            }
 
            /* ── Hovered / focused option ────────────────── */
            .Select-option.is-focused {
                background-color: #252830 !important;
                color: #4dd9d9 !important;
            }
            .Select-option:hover {
                background-color: #252830 !important;
                color: #4dd9d9 !important;
            }
 
            /* ── Selected option ─────────────────────────── */
            .Select-option.is-selected {
                background-color: #2a2f3e !important;
                color: #4dd9d9 !important;
                font-weight: 600 !important;
            }
 
            /* ── DBC Tabs ────────────────────────────────── */
            .nav-tabs {
                border-bottom: 1px solid #2e3340 !important;
                background-color: #252830 !important;
            }
            .nav-link {
                color: #8b93b0 !important;
                font-family: "JetBrains Mono", monospace !important;
                font-size: 11px !important;
                letter-spacing: 0.05em !important;
                padding: 8px 18px !important;
                border: none !important;
                background-color: transparent !important;
            }
            .nav-link:hover {
                color: #edf0f7 !important;
                border: none !important;
                background-color: #2a2f3e !important;
            }
            .nav-link.active {
                color: #4dd9d9 !important;
                background-color: #1e2127 !important;
                border-bottom: 2px solid #4dd9d9 !important;
                font-weight: 600 !important;
            }
            .tab-content {
                background-color: #252830 !important;
                border: 1px solid #2e3340 !important;
                border-top: none !important;
                border-radius: 0 0 8px 8px !important;
                padding: 16px !important;
            }
 
            /* ── Checklist labels ────────────────────────── */
            .form-check-label {
                color: #edf0f7 !important;
                font-family: "JetBrains Mono", monospace !important;
                font-size: 12px !important;
            }
            .form-check-input:checked {
                background-color: #4dd9d9 !important;
                border-color: #4dd9d9 !important;
            }
 
            /* ── Slider ──────────────────────────────────── */
            .rc-slider-track {
                background-color: #4dd9d9 !important;
            }
            .rc-slider-handle {
                border-color: #4dd9d9 !important;
                background-color: #4dd9d9 !important;
            }
            .rc-slider-rail {
                background-color: #2a2f3e !important;
            }
            .rc-slider-mark-text {
                color: #8b93b0 !important;
                font-family: "JetBrains Mono", monospace !important;
                font-size: 10px !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


# ── Shared style helpers ──────────────────────────────────────────
def _label(text: str) -> html.Div:
    return html.Div(text, style={
        "fontSize": "11px", "color": TEXT_SEC, "fontFamily": MONO,
        "textTransform": "uppercase", "letterSpacing": "0.08em",
        "marginBottom": "4px",
    })


def _dd(min_width: str = "200px") -> dict:
    return {
        "background": BG, "border": f"1px solid {BORDER}",
        "color": TEXT_PRI, "fontFamily": MONO,
        "fontSize": "12px", "borderRadius": "4px",
        "minWidth": min_width,
    }


# ── Header ────────────────────────────────────────────────────────
q_counts = meta.get("q_counts", {})

header = html.Div(
    style={
        "background": PANEL, "borderBottom": f"1px solid {BORDER}",
        "padding": "14px 24px", "display": "flex",
        "alignItems": "center", "gap": "20px", "flexWrap": "wrap",
    },
    children=[
        html.Span("◈", style={"color": ACCENT, "fontSize": "22px"}),
        html.Div([
            html.Div(
                "OPTIONS SCANNER: PUT EXHANGE - model alf 1.0",
                style={"fontFamily": MONO, "letterSpacing": "0.1em",
                       "color": TEXT_PRI, "fontWeight": "600", "fontSize": "18px"},
            ),
            html.Div(
                f"Scan date: {meta['date']}  ·  {meta['n_symbols']} symbols",
                style={"fontFamily": MONO, "fontSize": "11px", "color": TEXT_SEC,
                       "marginTop": "2px"},
            ),
        ]),
        html.Div(
            style={"marginLeft": "auto", "display": "flex", "gap": "8px",
                   "flexWrap": "wrap"},
            children=[
                html.Span(
                    f"{q}  {q_counts.get(q, 0)}",
                    style={
                        "background": Q_COLORS[q] + "22",
                        "color": Q_COLORS[q],
                        "border": f"1px solid {Q_COLORS[q]}44",
                        "fontFamily": MONO, "fontSize": "10px",
                        "letterSpacing": "0.06em",
                        "padding": "3px 10px", "borderRadius": "4px",
                    },
                )
                for q in ["Q1", "Q2", "Q3", "Q4"]
            ],
        ),
        html.Span(
            f"Top: {meta['top_symbol']}",
            style={
                "color": ACCENT, "fontSize": "11px", "fontFamily": MONO,
                "border": f"1px solid {ACCENT}44",
                "padding": "3px 10px", "borderRadius": "4px",
            },
        ),
    ],
)


# ── Tab styles ────────────────────────────────────────────────────
TAB_STYLES = {
    "tab": {
        "fontFamily": MONO, "fontSize": "12px",
        "color": TEXT_SEC, "letterSpacing": "0.05em",
        "padding": "8px 18px",
    },
    "tabActive": {"color": ACCENT},
    "list": {"borderBottom": f"1px solid {BORDER}"},
}

CONTENT_STYLE = {
    "background": PANEL, "border": f"1px solid {BORDER}",
    "borderRadius": "8px", "padding": "16px",
}

CTRL_ROW = {
    "display": "flex", "gap": "16px", "marginBottom": "14px",
    "flexWrap": "wrap", "alignItems": "flex-end",
}


# _tab helper removed — using dbc.Tabs


# ── Tab 1: Scatter ────────────────────────────────────────────────
scatter_tab = html.Div(style={"paddingTop": "16px"}, children=[
    html.Div(style=CTRL_ROW, children=[
        html.Div([
            _label("View"),
            dcc.Dropdown(
                id="scatter-view",
                options=[
                    {"label": "Global Top N  (Premium − Risk)", "value": "global"},
                    {"label": "Top N per Quadrant",             "value": "quadrant"},
                ],
                value="global", clearable=False, style=_dd("260px"),
            ),
        ]),
        html.Div([
            _label("Top N"),
            dcc.Dropdown(
                id="scatter-top-n",
                options=[{"label": f"Top {n}", "value": n}
                         for n in [10, 15, 20, 25, 30, 35, 40]],
                value=20, clearable=False, style=_dd("120px"),
            ),
        ]),
    ]),
    # dcc.Graph(id="graph-scatter", config={"displayModeBar": True}),
    dcc.Graph(id="graph-scatter"),
])


# ── Tab 2: Rankings ───────────────────────────────────────────────
bar_tab = html.Div(style={"paddingTop": "16px"}, children=[
    html.Div(style=CTRL_ROW, children=[
        html.Div([
            _label("View"),
            dcc.Dropdown(
                id="bar-preset",
                options=[
                    {"label": "a. Top Global Premium Score",            "value": "premium_score"},
                    {"label": "b. Lowest Global Risk Score",            "value": "risk_score_asc"},
                    {"label": "c. Top Global Risk Scores",              "value": "risk_score"},
                    {"label": "d. Q1 Only — Top Premium Score",         "value": "q1_premium"},
                    {"label": "e. Q2 Only — Lowest Risk Score",         "value": "q2_risk_asc"},
                    {"label": "f. Q3 Only — Top Premium Score",         "value": "q3_premium"},
                    {"label": "g. Top Premium - Slight OTM / 14D",      "value": "premium_slight_14"},   
                    {"label": "h. Top Prem/IV Efficiency 14D",          "value": "prem_per_iv_primary_14"},             
                    {"label": "i. Top Global Ranked Spike Score (Blended)",   "value": "spike_score"},
                    {"label": "j. Top Straddle 14D",                    "value": "straddle_14"},
                    {"label": "k. Top IV/HV Ratio 14D",                 "value": "ratio_14"},
                    {"label": "l. Top Slope Divergence Ranked",         "value": "slope_div_pct"},
                ],
                value="premium_score", clearable=False, style=_dd("300px"),
            ),
        ]),
        html.Div([
            _label("Top N"),
            dcc.Dropdown(
                id="bar-top-n",
                options=[{"label": f"Top {n}", "value": n}
                         for n in [10, 15, 20, 25, 30, 50]],
                value=20, clearable=False, style=_dd("120px"),
            ),
        ]),
    ]),
    dcc.Graph(id="graph-bar", config={"displayModeBar": False}),
])


# ── Tab 3: Distributions ──────────────────────────────────────────
hist_tab = html.Div(style={"paddingTop": "16px"}, children=[
    html.Div(style=CTRL_ROW, children=[
        html.Div([
            _label("Metric"),
            dcc.Dropdown(
                id="hist-metric",
                options=[
                    {"label": "ATM Premium 14D",       "value": "premium_atm_14"},
                    {"label": "ATM Premium 30D",       "value": "premium_atm_30"},
                    {"label": "Slight Premium 14D",    "value": "premium_slight_14"},
                    {"label": "Slight Premium 30D",    "value": "premium_slight_30"},
                    {"label": "Moderate Premium 14D",  "value": "premium_moderate_14"},
                    {"label": "Moderate Premium 30D",  "value": "premium_moderate_30"},
                    {"label": "Far Premium 14D",       "value": "premium_far_14"},
                    {"label": "Far Premium 30D",       "value": "premium_far_30"},
                    {"label": "Straddle 14D",          "value": "straddle_14"},
                    {"label": "HV 20D",                "value": "HV_20"},
                    {"label": "HV 30D",                "value": "HV_30"},
                    {"label": "HV 60D",                "value": "HV_60"},
                    {"label": "IV/HV Ratio 14D",       "value": "ratio_14"},
                    {"label": "IV/HV Ratio 30D",       "value": "ratio_30"},
                    {"label": "Relative Vol. Ratio to S&P 500",  "value": "relative_vol_spy"},
                    {"label": "Avg. Spike Magnitude 60D",  "value": "avg_spike_pct_60"},
                    {"label": "Blended Spike Score (Freq./Mag.)",       "value": "spike_score_universe"},
                    {"label": "Premium Score",         "value": "premium_score"},
                    {"label": "Risk Score",            "value": "risk_score"},
                ],
                value="premium_slight_14", clearable=False,
                style=_dd("260px"),
            ),
        ]),
        html.Div([
            _label("View"),
            dcc.Dropdown(
                id="hist-view",
                options=[
                    {"label": "All symbols",  "value": "all"},
                    {"label": "Q1 only",      "value": "Q1"},
                    {"label": "Q2 only",      "value": "Q2"},
                    {"label": "Q3 only",      "value": "Q3"},
                    {"label": "Q4 only",      "value": "Q4"},
                    {"label": "All overlaid", "value": "overlay"},
                ],
                value="all", clearable=False, style=_dd("160px"),
            ),
        ]),
        html.Div([
            _label("Bins"),
            dcc.Slider(
                id="hist-bins", min=5, max=60, step=5, value=25,
                marks={v: str(v) for v in [5, 15, 25, 40, 60]},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ], style={"minWidth": "220px"}),
        html.Div([
            _label("Overlays"),
            dcc.Checklist(
                id="hist-overlays",
                options=[
                    {"label": " KDE",    "value": "kde"},
                    {"label": " Median", "value": "median"},
                    {"label": " Mean",   "value": "mean"},
                ],
                value=[],
                inline=True,
                style={"color": TEXT_PRI, "fontFamily": MONO, "fontSize": "12px"},
            ),
        ]),
    ]),
    dcc.Graph(id="graph-hist", config={"displayModeBar": False}),
])


# ── Tab 4: Term Structure ─────────────────────────────────────────
term_tab = html.Div(style={"paddingTop": "16px"}, children=[
    html.Div(style=CTRL_ROW, children=[
        html.Div([
            _label("View"),
            dcc.Dropdown(
                id="term-view",
                options=[
                    {"label": "DTE Term Structure", "value": "dte"},
                    {"label": "HV Term Structure",  "value": "hv"},
                    {"label": "IV vs HV Overlay",   "value": "iv_hv"},
                ],
                value="dte", clearable=False, style=_dd("220px"),
            ),
        ]),
        html.Div(id="term-metric-wrapper", children=[
            _label("Metric"),
            dcc.Dropdown(
                id="term-metric",
                options=[
                    {"label": "ATM Put Premium",      "value": "put_atm"},
                    {"label": "Slight OTM Premium",   "value": "premium_slight"},
                    {"label": "Moderate OTM Premium", "value": "premium_moderate"},
                    {"label": "Far OTM Premium",      "value": "premium_far"},
                    {"label": "ATM Implied Vol",      "value": "atm_iv"},
                    {"label": "IV / HV Ratio",        "value": "ratio"},
                ],
                value="put_atm", clearable=False, style=_dd("240px"),
            ),
        ]),
        html.Div([
            _label("Quadrant Filter"),
            dcc.Dropdown(
                id="term-quadrant",
                options=[
                    {"label": "All", "value": "all"},
                    {"label": "Q1",  "value": "Q1"},
                    {"label": "Q2",  "value": "Q2"},
                    {"label": "Q3",  "value": "Q3"},
                    {"label": "Q4",  "value": "Q4"},
                ],
                value="all", clearable=False, style=_dd("130px"),
            ),
        ]),
        html.Div([
            _label("Options"),
            dcc.Checklist(
                id="term-options",
                options=[
                    {"label": " Quadrant lines", "value": "quads"},
                    {"label": " Mean line",      "value": "mean"},
                    {"label": " IV overlay",     "value": "iv"},
                ],
                value=[],
                inline=True,
                style={"color": TEXT_PRI, "fontFamily": MONO, "fontSize": "12px"},
            ),
        ]),
    ]),
    dcc.Graph(id="graph-term", config={"displayModeBar": False}),
])


# ── Tab 5: Screening Table ────────────────────────────────────────
table_tab = html.Div(style={"paddingTop": "16px"}, children=[
    html.Div(style=CTRL_ROW, children=[
        html.Div([
            _label("Quadrant"),
            dcc.Dropdown(
                id="tbl-quadrant",
                options=[
                    {"label": "All Quadrants",                 "value": "all"},
                    {"label": "Q1 · High Premium / Low Risk",  "value": "Q1"},
                    {"label": "Q2 · High Premium / High Risk", "value": "Q2"},
                    {"label": "Q3 · Low Premium  / Low Risk",  "value": "Q3"},
                    {"label": "Q4 · Low Premium  / High Risk", "value": "Q4"},
                ],
                value="all", clearable=False, style=_dd("280px"),
            ),
        ]),
        html.Div([
            _label("Sort By"),
            dcc.Dropdown(
                id="tbl-sort",
                options=[
                    {"label": "Premium Score ↓",       "value": "premium_score"},
                    {"label": "Risk Score ↑ (lowest)", "value": "risk_score_asc"},
                    {"label": "Risk Score ↓",          "value": "risk_score"},
                    {"label": "Spike Magnitude ↓",     "value": "avg_spike_pct_60"},
                    {"label": "Spike Count ↓",         "value": "spike_count_60"},
                    {"label": "Premium Slope ↓",       "value": "premium_slope_pct"},
                    {"label": "IV Slope ↓",            "value": "iv_slope_pct"},
                    {"label": "Slope Divergence ↓",    "value": "slope_div_pct"},
                ],
                value="premium_score", clearable=False, style=_dd("240px"),
            ),
        ]),
        html.Div([
            _label("Show Top"),
            dcc.Dropdown(
                id="tbl-top-n",
                options=[
                    {"label": "Top 10",  "value": 10},
                    {"label": "Top 25",  "value": 25},
                    {"label": "Top 50",  "value": 50},
                    {"label": "Top 100", "value": 100},
                    {"label": "All",     "value": 9999},
                ],
                value=25, clearable=False, style=_dd("130px"),
            ),
        ]),
        html.Div(
            id="tbl-count",
            style={
                "color": TEXT_SEC, "fontSize": "11px",
                "fontFamily": MONO, "alignSelf": "flex-end",
                "paddingBottom": "8px",
            },
        ),
    ]),
    # html.Div(id="tbl-container"),
    html.Div(id="tbl-container", children=[_build_datatable([], df)]),
])


# ── Full layout ───────────────────────────────────────────────────
app.layout = html.Div(
    className="dash-bootstrap",
    style={"background": BG, "minHeight": "100vh", "fontFamily": MONO},
    children=[
        header,
        html.Div(
            style={"margin": "12px"},
            children=[
                dbc.Tabs(
                    id="main-tabs",
                    active_tab="scatter",
                    children=[
                        dbc.Tab(label="QUADRANT MAP",    tab_id="scatter",
                                children=[scatter_tab]),
                        dbc.Tab(label="RANKINGS",        tab_id="rankings",
                                children=[bar_tab]),
                        dbc.Tab(label="DISTRIBUTIONS",   tab_id="distributions",
                                children=[hist_tab]),
                        dbc.Tab(label="TERM STRUCTURE",  tab_id="term",
                                children=[term_tab]),
                        dbc.Tab(label="SCREENING TABLE", tab_id="table",
                                children=[table_tab]),
                    ],
                ),
            ],
        ),
    ],
)


# ── CALLBACKS ─────────────────────────────────────────────────────

@app.callback(
    Output("graph-scatter", "figure"),
    Input("scatter-view",   "value"),
    Input("scatter-top-n",  "value"),
)
def update_scatter(view, top_n):
    if view == "global":
        return _scatter_global_view(df, top_n=top_n)
    return _scatter_quadrant_top_n(df, top_n=top_n)


@app.callback(
    Output("graph-bar", "figure"),
    Input("bar-preset", "value"),
    Input("bar-top-n",  "value"),
)
def update_bar(preset, top_n):
    configs = {
        "premium_score":         ("premium_score",          False, None),
        "premium_slight_14":     ("premium_slight_14",      False, None),
        "risk_score_asc":        ("risk_score",             True,  None),
        "risk_score":            ("risk_score",             False, None),
        "spike_score":           ("spike_pct_universe",     False, None),
        "straddle_14":           ("straddle_14",            False, None),
        "ratio_14":              ("ratio_14",               False, None),
        "prem_per_iv_primary_14":("prem_per_iv_primary_14", False, None),
        "slope_div_pct":         ("slope_div_pct",          False, None),
        "q1_premium":            ("premium_score",          False,
                                  lambda d: d[d["quadrant"].str.startswith("Q1")]),
        "q2_risk_asc":            ("risk_score",            True,
                                  lambda d: d[d["quadrant"].str.startswith("Q2")]),
        "q3_premium":            ("premium_score",          False,
                                  lambda d: d[d["quadrant"].str.startswith("Q3")]),
    }
    titles = {
        "premium_score":         "Top Global by Premium Score",
        "premium_slight_14":     "Top Global by Premium Slight OTM / 14D",
        "risk_score_asc":        "Top Global by Lowest Risk Score",
        "risk_score":            "Top Global by Risk Score",
        "spike_score":           "Top Global Ranked Spike - Blended Score",
        "straddle_14":           "Top Global by Straddle 14D",
        "ratio_14":              "Top Global by IV/HV Ratio 14D",
        "prem_per_iv_primary_14":"Top Global by Prem/IV Efficiency 14D",
        "slope_div_pct":         "Top Global Ranked by Slope Divergence",
        "q1_premium":            "Top Q1 Symbols · Top Premium Score",
        "q2_risk_asc":           "Top Q2 Symbols · Lowest Risk Score",
        "q3_premium":            "Top Q3 Symbols · Top Premium Score",
    }
    score_col, ascending, df_filter = configs.get(
        preset, ("premium_score", False, None)
    )
    return build_bar(
        df, score_col=score_col, top_n=top_n,
        title=titles.get(preset, ""),
        ascending=ascending, df_filter=df_filter,
    )


@app.callback(
    Output("graph-hist",    "figure"),
    Input("hist-metric",    "value"),
    Input("hist-view",      "value"),
    Input("hist-bins",      "value"),
    Input("hist-overlays",  "value"),
)
def update_hist(metric, view, bins, overlays):
    overlays = overlays or []
    return build_histogram(
        df, metric=metric, view=view, bins=bins or 25,
        show_kde="kde"       in overlays,
        show_median="median" in overlays,
        show_mean="mean"     in overlays,
    )


@app.callback(
    Output("graph-term",          "figure"),
    Output("term-metric-wrapper", "style"),
    Input("term-view",            "value"),
    Input("term-metric",          "value"),
    Input("term-quadrant",        "value"),
    Input("term-options",         "value"),
)
def update_term(view, metric, quadrant, options):
    options      = options or []
    metric_style = (
        {"display": "none"}  if view in ("hv", "iv_hv")
        else {"display": "block"}
    )
    if view == "dte":
        fig = build_term_structure(
            df, metric=metric,
            show_quadrants="quads" in options,
            quadrant_filter=quadrant,
            show_mean="mean" in options,
        )
    elif view == "hv":
        fig = build_hv_term_structure(
            df,
            show_iv_overlay="iv" in options,
            show_quadrants="quads" in options,
            quadrant_filter=quadrant,
            show_mean="mean" in options,
        )
    else:
        fig = build_iv_hv_overlay(
            df,
            show_quadrants="quads" in options,
            quadrant_filter=quadrant,
        )
    return fig, metric_style


# Table callbacks registered from charts/table.py
register_table_callbacks(app, df)


# ── Run ───────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     app.run(debug=True, port=8050)
if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1', port=8050)

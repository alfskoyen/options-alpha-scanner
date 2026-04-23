

"""
screening_table.py
────────────────────────────────────────────────────────────────────────
Sortable, filterable screening table for options scan DataFrame.
Built with Dash DataTable — ready to drop into your Dash app.

Columns:
  Symbol, Quadrant, Premium Score, Risk Score,
  Spike Signal, Spike Magnitude, Spike Ratio, Spike Count,
  Premium Slope, IV Slope, Slope Divergence

Controls:
  - Quadrant filter     (All / Q1 / Q2 / Q3 / Q4)
  - Sort by metric      (dropdown)
  - Top N               (10 / 25 / 50 / 100 / All)

Usage in Dash app:
─────────────────
    from screening_table import build_table_layout, register_table_callbacks
    
    app.layout = build_table_layout()
    register_table_callbacks(app, df)

Usage in Jupyter (preview):
────────────────────────────
    from screening_table import preview_table
    preview_table(df)
"""

import pandas as pd
import numpy as np

# ── DESIGN TOKENS ─────────────────────────────────────────────────
BG        = "#1e2127"
PANEL     = "#252830"
BORDER    = "#2e3340"
ROW_ALT   = "#222630"
TEXT_PRI  = "#edf0f7"
TEXT_SEC  = "#8b93b0"
TEXT_DIM  = "#4a5270"
ACCENT    = "#4dd9d9"
MONO      = "JetBrains Mono, Fira Mono, Consolas, monospace"

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

# ── COLUMN DEFINITIONS ────────────────────────────────────────────
# id        : DataFrame column name
# name      : display header
# type      : 'numeric' | 'text'
# format    : display format string for numeric columns
# width     : column width in px

TABLE_COLS = [
    {"id": "symbol",           "name": "Symbol",         "type": "text",    "width": 40},
    {"id": "quadrant_short",   "name": "Quadrant",       "type": "text",    "width": 50},
    {"id": "premium_score",    "name": "Prem Score",     "type": "numeric", "width": 70,  "format": ".2f"},
    {"id": "risk_score",       "name": "Risk Score",     "type": "numeric", "width": 70,  "format": ".2f"},
    {"id": "premium_slight_30", "name": "Prem. Slight 30D",    "type": "numeric", "width": 95,  "format": ".2f"},
    {"id": "prem_per_iv_primary_30", "name": "Prem. per IV 30D (Eff.)",    "type": "numeric", "width": 95,  "format": ".2f"},
    {"id": "prem_efficiency_signal_30",           "name": "Prem. Efficiency Signal 30D",         "type": "text",    "width": 90},
    {"id": "atm_iv_30", "name": "IV ATM at 30D",    "type": "numeric", "width": 95,  "format": ".2f"},
    {"id": "HV_30", "name": "HV 30D",    "type": "numeric", "width": 70,  "format": ".2f"},
    {"id": "ratio_30", "name": "IV/HV Ratio",    "type": "numeric", "width": 70,  "format": ".2f"},
    {"id": "signal_30", "name": "IV/HV Signal",     "type": "text",    "width": 80},
    {"id": "relative_vol_spy", "name": "Relative Vol. to SPY",    "type": "numeric", "width": 95,  "format": ".2f"},
    {"id": "relative_vol_qqq", "name": "Relative Vol. to QQQ",    "type": "numeric", "width": 95,  "format": ".2f"},  
    # {"id": "relative_vol_spy_pct", "name": "Relative to SPY Rank Order",    "type": "numeric", "width": 95,  "format": ".2f"},
    # {"id": "spike_signal_60",  "name": "Spike Signal_Symbol",   "type": "text",    "width": 105},
    # {"id": "avg_spike_pct_60", "name": "Spike Mag (Avg.) %",    "type": "numeric", "width": 95,  "format": ".2f"},
    # {"id": "spike_ratio_60",   "name": "Spike Ratio",    "type": "numeric", "width": 90,  "format": ".2f"},
    # {"id": "spike_count_60",   "name": "Spike Count",    "type": "numeric", "width": 90,  "format": ".0f"},
    {"id": "spike_score_universe", "name": "Spike Score Blended_Univ.",    "type": "numeric", "width": 95,  "format": ".2f"},
    {"id": "spike_signal_universe", "name": "Spike Signal_Univ.",    "type": "text",    "width": 90},
    # {"id": "premium_slope_pct","name": "Prem Slope",     "type": "numeric", "width": 95,  "format": ".4f"},
    # {"id": "iv_slope_pct",     "name": "IV Slope",       "type": "numeric", "width": 85,  "format": ".4f"},
    # {"id": "slope_div_pct",    "name": "Slope Div",      "type": "numeric", "width": 85,  "format": ".4f"},
        ]

SORT_OPTIONS = [
    {"label": "Premium Score ↓",      "value": "premium_score"},
    {"label": "Risk Score ↑ (lowest)","value": "risk_score_asc"},
    {"label": "Risk Score ↓",         "value": "risk_score"},
    {"label": "Spike Magnitude ↓",    "value": "avg_spike_pct_60"},
    {"label": "Spike Magnitude ↑ (lowest)",    "value": "avg_spike_pct_60_asc"},
    {"label": "Spike Score Universal Rank ↓",        "value": "spike_pct_universe"},
    {"label": "Spike Score Universal Rank ↑ (lowest)",        "value": "spike_pct_universe_asc"},
    {"label": "IV/HV ↓",        "value": "ratio_30"},
    {"label": "Prem. per IV 30D ↓",        "value": "prem_per_iv_primary_30"},
    {"label": "Vol. Rel. to SPY Rank % ↓",        "value": "relative_vol_spy_pct"},
	{"label": "Vol. Rel. to SPY Rank % ↑ (lowest)",        "value": "relative_vol_spy_pct_asc"},

    # {"label": "Premium Slope ↓",      "value": "premium_slope_pct"},
    # {"label": "IV Slope ↓",           "value": "iv_slope_pct"},
    # {"label": "Slope Divergence ↓",   "value": "slope_div_pct"},
]

TOP_N_OPTIONS = [
    {"label": "Top 10",  "value": 10},
    {"label": "Top 25",  "value": 25},
    {"label": "Top 50",  "value": 50},
    {"label": "Top 100", "value": 100},
    {"label": "All",     "value": 9999},
]

QUAD_OPTIONS = [
    {"label": "All Quadrants", "value": "all"},
    {"label": "Q1 · High Premium / Low Risk",  "value": "Q1"},
    {"label": "Q2 · High Premium / High Risk", "value": "Q2"},
    {"label": "Q3 · Low Premium  / Low Risk",  "value": "Q3"},
    {"label": "Q4 · Low Premium  / High Risk", "value": "Q4"},
]


# ── DATA PREP ─────────────────────────────────────────────────────
def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare DataFrame for table display.
    - Adds quadrant_short (Q1/Q2/Q3/Q4) column
    - Rounds numeric columns
    - Returns only TABLE_COLS columns
    """
    out = df.copy()

    # Short quadrant label for display
    out["quadrant_short"] = out["quadrant"].str[:2].where(
        out["quadrant"].notna(), ""
    )

    # Round numerics
    rounding = {
        "premium_score":    2,
        "risk_score":       2,
        "avg_spike_pct_60": 2,
        "spike_ratio_60":   2,
        "premium_slope_pct":4,
        "iv_slope_pct":     4,
        "slope_div_pct":    4,
    }
    for col, dec in rounding.items():
        if col in out.columns:
            out[col] = out[col].round(dec)

    # Keep only columns we need
    keep = [c["id"] for c in TABLE_COLS if c["id"] in out.columns]
    return out[keep].copy()


def filter_and_sort(
    df:         pd.DataFrame,
    quadrant:   str = "all",
    sort_by:    str = "premium_score",
    top_n:      int = 25,
) -> pd.DataFrame:
    """Apply quadrant filter, sort, and top-N slice."""
    out = df.copy()

    if quadrant != "all":
        out = out[out["quadrant_short"] == quadrant]

    ascending = sort_by.endswith("_asc")
    col       = sort_by.replace("_asc", "")
    if col in out.columns:
        out = out.sort_values(col, ascending=ascending, na_position="last")

    if top_n < 9999:
        out = out.head(top_n)

    return out.reset_index(drop=True)


# ── DASH TABLE BUILDERS ───────────────────────────────────────────
def _dash_columns() -> list:
    """Build Dash DataTable columns spec from TABLE_COLS."""
    from dash.dash_table.Format import Format, Scheme
    cols = []
    for c in TABLE_COLS:
        entry = {
            "id":               c["id"],
            "name":             c["name"],
            "type":             c.get("type", "text"),
            "deletable":        False,
            "renamable":        False,
            "selectable":       True,
        }
        if c.get("type") == "numeric" and "format" in c:
            fmt = c["format"]
            decimals = int(fmt.replace(".", "").replace("f", ""))
            entry["format"] = Format(precision=decimals, scheme=Scheme.fixed)
        cols.append(entry)
    return cols


def _conditional_styles(df: pd.DataFrame) -> list:
    """
    Build conditional cell styles:
    - Quadrant column colored by Q1/Q2/Q3/Q4
    - Premium Score: green gradient for top values
    - Risk Score: red for high values
    - Spike Signal: colored by signal text
    """
    styles = []

    # Quadrant color coding
    for q, color in Q_COLORS.items():
        styles.append({
            "if": {
                "filter_query": f'{{quadrant_short}} = "{q}"',
                "column_id": "quadrant_short",
            },
            "color":      color,
            "fontWeight": "600",
        })

    # Premium score — top tercile teal tint
    if "premium_score" in df.columns:
        p75 = df["premium_score"].quantile(0.75)
        p50 = df["premium_score"].quantile(0.50)
        styles += [
            {
                "if": {
                    "filter_query": f"{{premium_score}} >= {p75:.2f}",
                    "column_id": "premium_score",
                },
                "color": Q_COLORS["Q1"],
                "fontWeight": "600",
            },
            {
                "if": {
                    "filter_query": f"{{premium_score}} >= {p50:.2f} && {{premium_score}} < {p75:.2f}",
                    "column_id": "premium_score",
                },
                "color": ACCENT,
            },
        ]

    # Risk score — high risk in red
    if "risk_score" in df.columns:
        r75 = df["risk_score"].quantile(0.75)
        styles.append({
            "if": {
                "filter_query": f"{{risk_score}} >= {r75:.2f}",
                "column_id": "risk_score",
            },
            "color": Q_COLORS["Q4"],
            "fontWeight": "600",
        })

    # Spike signal text coloring
    for signal, color in [
        ("Elevated", Q_COLORS["Q2"]),
        ("High",     Q_COLORS["Q4"]),
        ("Normal",   TEXT_SEC),
    ]:
        styles.append({
            "if": {
                "filter_query": f'{{spike_signal_60}} = "{signal}"',
                "column_id": "spike_signal_60",
            },
            "color": color,
            "fontWeight": "600" if signal != "Normal" else "400",
        })

    # Alternating row shading
    styles += [
        {
            "if": {"row_index": "odd"},
            "backgroundColor": ROW_ALT,
        },
    ]

    return styles


def build_table_layout(initial_df: pd.DataFrame = None) -> "html.Div":
    """
    Build the full Dash layout for the screening table.
    Pass initial_df to pre-populate; otherwise uses empty state.

    Returns an html.Div containing controls + DataTable.
    Designed to be assigned to app.layout or embedded in a larger layout.
    """
    from dash import dcc, html
    import dash_mantine_components as dmc

    control_style = {
        "display":    "flex",
        "gap":        "16px",
        "flexWrap":   "wrap",
        "alignItems": "flex-end",
        "padding":    "16px 20px 12px",
        "background": PANEL,
        "borderBottom": f"1px solid {BORDER}",
    }

    label_style = {
        "fontSize":      "12px",
        "color":         TEXT_SEC,
        "fontFamily":    MONO,
        "textTransform": "uppercase",
        "letterSpacing": "0.08em",
        "marginBottom":  "4px",
    }

    dd_style = {
        "background":  BG,
        "border":      f"1px solid {BORDER}",
        "color":       TEXT_PRI,
        "fontFamily":  MONO,
        "fontSize":    "12px",
        "borderRadius":"4px",
        "minWidth":    "200px",
    }

    initial_data = []
    if initial_df is not None:
        prep = prepare_df(initial_df)
        filt = filter_and_sort(prep)
        initial_data = filt.to_dict("records")

    layout = html.Div(
        style={"background": BG, "minHeight": "100vh", "fontFamily": MONO},
        children=[

            # ── Header ──────────────────────────────────────────────
            html.Div(
                style={
                    "background": PANEL,
                    "borderBottom": f"1px solid {BORDER}",
                    "padding": "14px 20px",
                },
                children=[
                    html.Span(
                        "OPTIONS SCREENING TABLE",
                        style={
                            "color":         TEXT_PRI,
                            "fontSize":      "16px",
                            "fontWeight":    "600",
                            "fontFamily":    MONO,
                            "letterSpacing": "0.1em",
                        },
                    ),
                ],
            ),

            # ── Controls ────────────────────────────────────────────
            html.Div(
                style=control_style,
                children=[
                    # Quadrant filter
                    html.Div([
                        html.Div("Quadrant", style=label_style),
                        dcc.Dropdown(
                            id="tbl-quadrant",
                            options=QUAD_OPTIONS,
                            value="all",
                            clearable=False,
                            style=dd_style,
                        ),
                    ]),

                    # Sort by
                    html.Div([
                        html.Div("Sort By", style=label_style),
                        dcc.Dropdown(
                            id="tbl-sort",
                            options=SORT_OPTIONS,
                            value="premium_score",
                            clearable=False,
                            style={**dd_style, "minWidth": "220px"},
                        ),
                    ]),

                    # Top N
                    html.Div([
                        html.Div("Show Top", style=label_style),
                        dcc.Dropdown(
                            id="tbl-top-n",
                            options=TOP_N_OPTIONS,
                            value=25,
                            clearable=False,
                            style={**dd_style, "minWidth": "120px"},
                        ),
                    ]),

                    # Live count badge
                    html.Div(
                        id="tbl-count",
                        style={
                            "color":      TEXT_SEC,
                            "fontSize":   "12px",
                            "fontFamily": MONO,
                            "alignSelf":  "flex-end",
                            "paddingBottom": "8px",
                        },
                    ),
                ],
            ),

            # ── Table ────────────────────────────────────────────────
            html.Div(
                style={"padding": "16px 20px"},
                children=[
                    _build_datatable(initial_data),
                ],
            ),
        ],
    )
    return layout


def _build_datatable(data: list = None, df_for_styles: pd.DataFrame = None):
    """Build the Dash DataTable component."""
    from dash import dash_table

    cell_style = {
        "backgroundColor": BG,
        "color":           TEXT_PRI,
        "fontFamily":      MONO,
        "fontSize":        "12px",
        "border":          f"1px solid {BORDER}",
        "padding":         "8px 12px",
        "whiteSpace":      "nowrap",
        "overflow":        "hidden",
        "textOverflow":    "ellipsis",
    }

    header_style = {
        "backgroundColor": PANEL,
        "color":           ACCENT,
        "fontFamily":      MONO,
        "fontSize":        "12.5px",
        "fontWeight":      "600",
        "letterSpacing":   "0.06em",
        "border":          f"1px solid {BORDER}",
        "padding":         "10px 12px",
        "textAlign":       "left",
        "whiteSpace":	   "normal",
        "height":		   "auto"
    }

    return dash_table.DataTable(
        id="screening-table",
        columns=_dash_columns(),
        data=data or [],

        # Sorting
        sort_action="native",
        sort_mode="single",

        # Pagination
        page_action="native",
        page_size=20,

        # Selection
        row_selectable="single",
        selected_rows=[],

        # Style
        style_cell=cell_style,
        style_header=header_style,
        style_data_conditional=_conditional_styles(
            df_for_styles if df_for_styles is not None else pd.DataFrame()
        ),
        style_table={
            "overflowX":   "auto",
            "borderRadius":"4px",
            "border":      f"1px solid {BORDER}",
        },
        style_as_list_view=False,

        # Column widths
        style_cell_conditional=[
            {"if": {"column_id": c["id"]}, "minWidth": f"{c['width']}px",
             "maxWidth": f"{c['width'] + 40}px"}
            for c in TABLE_COLS
        ],
    )


# ── CALLBACKS ─────────────────────────────────────────────────────
# def register_table_callbacks(app, df: pd.DataFrame):
def register_table_callbacks(app, app_data: pd.DataFrame):
    """
    Register Dash callbacks for the screening table.

    Call this after app.layout is set:
        register_table_callbacks(app, df)
    """
    from dash import Input, Output, callback

    # prep = prepare_df(df)
    prep = prepare_df(app_data['df'])

    @app.callback(
        Output("screening-table", "data"),
        Output("screening-table", "style_data_conditional"),
        Output("tbl-count",       "children"),
        Input("tbl-quadrant",     "value"),
        Input("tbl-sort",         "value"),
        Input("tbl-top-n",        "value"),
    )
    def update_table(quadrant, sort_by, top_n):
        df = app_data['df']   # reads fresh every time callback fires
        filtered = filter_and_sort(prep, quadrant=quadrant,
                                   sort_by=sort_by, top_n=top_n)
        total    = len(prep) if quadrant == "all" else len(
            prep[prep["quadrant_short"] == quadrant]
        )
        count_label = (
            f"Showing {len(filtered)} of {total} symbols"
            + (f"  ·  {Q_LABELS.get(quadrant, '')}" if quadrant != "all" else "")
        )
        return (
            filtered.to_dict("records"),
            _conditional_styles(filtered),
            count_label,
        )


# ── JUPYTER PREVIEW ───────────────────────────────────────────────
def preview_table(df: pd.DataFrame, quadrant: str = "all",
                  sort_by: str = "premium_score", top_n: int = 25,
                  _return_fig: bool = False):
    """
    Quick preview in Jupyter using Plotly Table (no Dash server needed).
    For full interactivity use show_table_dashboard(df).

    Usage:
        from screening_table import preview_table
        preview_table(df, top_n=25)
        preview_table(df, quadrant="Q1", sort_by="avg_spike_pct_60")
    """
    import plotly.graph_objects as go

    prep     = prepare_df(df)
    filtered = filter_and_sort(prep, quadrant=quadrant,
                                sort_by=sort_by, top_n=top_n)

    display_cols = [c for c in TABLE_COLS if c["id"] in filtered.columns]
    headers      = [c["name"] for c in display_cols]
    values       = []

    for c in display_cols:
        col_data = filtered[c["id"]].tolist()
        if c.get("type") == "numeric" and "format" in c:
            try:
                decimals = int(c["format"].replace(".", "").replace("f", ""))
            except ValueError:
                decimals = 2
            col_data = [
                round(float(v), decimals) if v is not None and not (isinstance(v, float) and np.isnan(v)) else ""
                for v in col_data
            ]
        values.append(col_data)

    # Row colors — plain PANEL for all rows, quadrant color on quadrant col only
    n_rows      = len(filtered)
    fill_colors = [[PANEL] * n_rows] * len(display_cols)

    fig = go.Figure(go.Table(
        header=dict(
            values=headers,
            fill_color=PANEL,
            font=dict(color=ACCENT, size=14, family=MONO),  ## Headers Font
            align="left",
            line_color=BORDER,
            height=32,
        ),
        cells=dict(                                   ## Cell level style, font, etc.  --> 
            values=values,
            fill_color=fill_colors,
            font=dict(color=TEXT_PRI, size=13.5, family=MONO),
            align="left",
            line_color=BORDER,
            height=28,
        ),
    ))

    q_tag = f"  ·  {Q_LABELS.get(quadrant, '')}" if quadrant != "all" else ""
    fig.update_layout(
        paper_bgcolor=BG,
        margin=dict(l=20, r=20, t=52, b=20),
        height=max(400, min(top_n * 30 + 80, 800)),
        title=dict(
            text=(
                f"<b>Options Screening Table{q_tag}</b><br>"
                f"<span style='font-size:13px;color:{TEXT_SEC}'>"
                f"n = {len(filtered)}  ·  sorted by {sort_by}</span>"
            ),
            x=0.01,
            font=dict(family=MONO, color=TEXT_PRI, size=17), ## Title Font
        ),
    )
    if _return_fig:
        return fig
    fig.show()


# ── JUPYTER INTERACTIVE WIDGET ───────────────────────────────────
def show_table_dashboard(df: pd.DataFrame):
    """
    Launch interactive table dashboard in Jupyter using ipywidgets.

    Controls:
      - Quadrant filter toggle  (All / Q1 / Q2 / Q3 / Q4)
      - Sort by dropdown
      - Top N slider

    Usage:
        from screening_table import show_table_dashboard
        show_table_dashboard(df)
    """
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError:
        print("ipywidgets required: pip install ipywidgets")
        return

    quad_toggle = widgets.ToggleButtons(
        options=["all", "Q1", "Q2", "Q3", "Q4"],
        value="all",
        description="Quadrant:",
        style={"description_width": "75px", "button_width": "60px"},
    )

 # {"label": "Premium Score ↓",      "value": "premium_score"},
 #    {"label": "Risk Score ↑ (lowest)","value": "risk_score_asc"},
 #    {"label": "Risk Score ↓",         "value": "risk_score"},
 #    {"label": "Spike Magnitude ↓",    "value": "avg_spike_pct_60"},
 #    {"label": "Spike Magnitude ↑ (lowest)",    "value": "avg_spike_pct_60_asc"},
 #    {"label": "Spike Score Universal Rank ↓",        "value": "spike_pct_universe"},
 #    {"label": "Spike Score Universal Rank ↑ (lowest)",        "value": "spike_pct_universe_asc"},
 #    {"label": "IV/HV ↓",        "value": "ratio_30"},
 #    {"label": "Vol. Rel. to SPY Rank % ↓",        "value": "relative_vol_spy_pct"},
# 	{"label": "Vol. Rel. to SPY Rank % ↑ (lowest)",        "value": "relative_vol_spy_pct_asc"},

    sort_dd = widgets.Dropdown(
        options=[
            ("Premium Score ↓",       "premium_score"),
            ("Risk Score ↓",          "risk_score"),
            ("Risk Score ↑ (lowest)", "risk_score_asc"),
			("Prem. Slight 30D ↓",     "premium_slight_30"),
			("Prem. per IV 30D ↓",     "prem_per_iv_primary_30"),
            ("Spike Magnitude ↓",     "avg_spike_pct_60"),
 			("Spike Magnitude ↑ (lowest)",     "avg_spike_pct_60_asc"),
 			("Spike Score Universal Rank ↓",     "spike_pct_universe"),
 			("Spike Score Universal Rank ↑ (lowest)",     "spike_pct_universe_asc"),
 			("IV/HV ↓",     "ratio_30"),
 			("Vol. Rel. to SPY Rank % ↓",     "relative_vol_spy_pct"),
 			("Vol. Rel. to SPY Rank % ↑ (lowest)",     "relative_vol_spy_pct_asc"),
            # ("Spike Count ↓",         "spike_count_60"),
            # ("Premium Slope ↓",       "premium_slope_pct"),
            # ("IV Slope ↓",            "iv_slope_pct"),
            # ("Slope Divergence ↓",    "slope_div_pct"),
        ],
        value="premium_score",
        description="Sort By:",
        style={"description_width": "65px"},
        layout=widgets.Layout(width="280px"),
    )

    topn_slider = widgets.IntSlider(
        value=25, min=10, max=min(200, len(df)), step=5,
        description="Top N:",
        style={"description_width": "55px"},
        layout=widgets.Layout(width="300px"),
    )

    count_label = widgets.Label(
        value="",
        style={"font_family": "monospace"},
    )

    out = widgets.Output()

    def update(*args):
        with out:
            out.clear_output(wait=True)
            fig = preview_table(  ### Call preview_table method to build table. 
                df,
                quadrant=quad_toggle.value,
                sort_by=sort_dd.value,
                top_n=topn_slider.value,
                _return_fig=True,
            )
            fig.show()
            total = len(df) if quad_toggle.value == "all" else len(
                df[df["quadrant"].str.startswith(quad_toggle.value)]
            )
            count_label.value = (
                f"Showing top {topn_slider.value} of {total} symbols"
                + (f"  ·  {Q_LABELS.get(quad_toggle.value, '')}"
                   if quad_toggle.value != "all" else "")
            )

    for w in [quad_toggle, sort_dd, topn_slider]:
        w.observe(update, names="value")

    controls = widgets.VBox([
        quad_toggle,
        widgets.HBox([sort_dd, topn_slider]),
        count_label,
    ])

    display(controls, out)
    update()


# ── STANDALONE DASH APP (dev / demo) ──────────────────────────────
def run_standalone(df: pd.DataFrame, port: int = 8051):
    """
    Spin up a standalone Dash app for the screening table.
    Use for development — in production embed via build_table_layout()
    and register_table_callbacks().

    Usage:
        from screening_table import run_standalone
        run_standalone(df)
    """
    import dash
    app = dash.Dash(__name__, title="Options Screening Table")
    app.layout = build_table_layout(initial_df=df)
    register_table_callbacks(app, df)
    app.run(debug=True, port=port)
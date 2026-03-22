"""
scatter plot.py
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
    Q_COLORS, MONO, LABEL_TEAL, Q_LABELS,
)

### --- Quadrant Assignment -------------------------------------------
def _assign_quadrants(df: pd.DataFrame) -> pd.DataFrame:
    """Auto-assign quadrant labels if the column doesn't exist."""

    df = df.copy()
    if "quadrant" not in df.columns:
        r_mid = df["risk_score"].median()
        p_mid = df["premium_score"].median()
        conditions = [
            (df["premium_score"] >= p_mid) & (df["risk_score"] <  r_mid),
            (df["premium_score"] >= p_mid) & (df["risk_score"] >= r_mid),
            (df["premium_score"] <  p_mid) & (df["risk_score"] <  r_mid),
            (df["premium_score"] <  p_mid) & (df["risk_score"] >= r_mid),
        ]
        df["quadrant"] = np.select(conditions, ["Q1", "Q2", "Q3", "Q4"], default="Q3")
    return df


### === Shared Base Elements ====================================================================
### --------------------------------------------------------------------------------------------

def _add_quadrant_base(fig, df, r_mid, p_mid, r_min, r_max, p_min, p_max, pr, pp):
    """
    Adds shading, watermark letters, corner labels, and divider lines.
    Shared between both scatter functions.
    """
    quads_geo = [
        ("Q1", r_min - pr, r_mid,      p_mid,      p_max + pp),
        ("Q2", r_mid,      r_max + pr, p_mid,      p_max + pp),
        ("Q3", r_min - pr, r_mid,      p_min - pp, p_mid),
        ("Q4", r_mid,      r_max + pr, p_min - pp, p_mid),    ]
 
    for q, x0, x1, y0, y1 in quads_geo:
        # Subtle fill
        fig.add_shape(
            type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
            fillcolor=Q_COLORS[q], opacity=0.05,
            line=dict(width=0), layer="below",
        )
 
        # Faint watermark letter
        fig.add_annotation(
            x=(x0 + x1) / 2, y=(y0 + y1) / 2,
            text=q,
            showarrow=False,
            font=dict(size=40, color=Q_COLORS[q], family=MONO),
            opacity=0.18,
        )
 
        # Corner labels — Q1/Q2 top, Q3/Q4 just below axis
        corner_positions = {
            "Q1": (x0 + (x1 - x0) * 0.025, y1 - (y1 - y0) * 0.04, "left",  "top"),     # top-left
            "Q2": (x1 - (x1 - x0) * 0.025, y1 - (y1 - y0) * 0.04, "right", "top"),     # top-right
            "Q3": (x0 + (x1 - x0) * 0.025, y0 + (y1 - y0) * 0.04, "left",  "bottom"),  # bottom-left
            "Q4": (x1 - (x1 - x0) * 0.025, y0 + (y1 - y0) * 0.04, "right", "bottom"),  # bottom-right
        }

        lx, ly, x_anchor, y_anchor = corner_positions[q]
        fig.add_annotation(
            x=lx, y=ly,
            text=f"<b>{q}</b><br>{Q_LABELS[q]}",
            showarrow=False,
            font=dict(size=11, color=LABEL_TEAL, family=MONO),
            opacity=0.92,
            xanchor=x_anchor,
            yanchor=y_anchor,
            bgcolor="rgba(30,33,39,0.50)",
            borderpad=4,
        )
 
    # Dashed divider lines
    fig.add_shape(
        type="line",
        x0=r_mid, x1=r_mid,
        y0=p_min - pp * 2, y1=p_max + pp * 2,
        line=dict(color=CROSS, width=1.2, dash="dash"),
    )
    fig.add_shape(
        type="line",
        x0=r_min - pr * 2, x1=r_max + pr * 2,
        y0=p_mid, y1=p_mid,
        line=dict(color=CROSS, width=1.2, dash="dash"),    )
 

def _add_scatter_traces(fig, df):
    """Adds one scatter trace per quadrant — shared between both views."""
    df = df.copy()
    df["_q"] = df["quadrant"].str.strip().str[:2]    # ← extract Q1/Q2/Q3/Q4 reliably

    for q, color in Q_COLORS.items():
        sub = df[df["quadrant"].str.startswith(q)]
        fig.add_trace(go.Scatter(
            x=sub["risk_score"],
            y=sub["premium_score"],
            mode="markers",
            # name=f"{Q_LABELS[q].replace('<br>', ' / ')}  ({len(sub)})",
            name=f"{q}  ({len(sub)})",
            marker=dict(
                color=color,
                size=6,          ## adjust point size. 
                opacity=0.76,
                line=dict(width=0.7, color=BG),
            ),
            customdata=np.stack([
                sub["symbol"],
                sub["quadrant"],
                sub["risk_score"].round(1),
                sub["premium_score"].round(1),
            ], axis=-1),
            hovertemplate=(
                f"<span style='font-size:15px;font-weight:700;color:{color}'>"
                "%{customdata[0]}"
                "</span><br>"
                "<span style='color:#4a5270'>──────────────────</span><br>"
                "Premium Score &nbsp; <b>%{customdata[3]}</b><br>"
                "Risk Score &nbsp;&nbsp;&nbsp;&nbsp; <b>%{customdata[2]}</b><br>"
                f"Quadrant &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; "
                f"<b style='color:{color}'>%{{customdata[1]}}</b>"
                "<extra></extra>"
            ),
        ))
  
def _base_layout(df, title_text, height=725) -> dict:
    """Shared layout dict for both scatter views."""
    return dict(
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        height=height,
        margin=dict(l=80, r=220, t=84, b=72),
        title=dict(                                ## Title Styles
            text=title_text,
            x=0.03,
            font=dict(family=MONO, color=TEXT_PRI, size=18),
        ),
        legend=dict(
            bgcolor="#1e2127",
            bordercolor="#363b50",
            borderwidth=1,
            font=dict(size=11.5, color=TEXT_PRI, family=MONO),
            itemsizing="constant",
            tracegroupgap=6,
            x=1.02, y=1,
            xanchor="left",
            yanchor="top",
        ),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#1a1d28",
            bordercolor="#363b50",
            font=dict(size=12, color=TEXT_PRI, family=MONO),
            namelength=0,
        ),
        font=dict(family=MONO, color=TEXT_PRI, size=11),
    )
 
 
def _base_axes(r_min, r_max, p_min, p_max, pr, pp) -> tuple:
    """Returns (xaxis_dict, yaxis_dict) shared between both views."""
    ax_shared = dict(
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        linecolor="#363b50",
        linewidth=1,
        tickfont=dict(size=13, color=TEXT_AX, family=MONO),
        ticklen=5,
        tickcolor="#363b50",
        showgrid=True,
        nticks=10,
    )
    xaxis = dict(
        **ax_shared,
        title=dict(
            text="← Safer   RISK SCORE   Riskier →",
            font=dict(size=13, color=AX_TITLE, family=MONO),
            standoff=14,
        ),
        range=[r_min - pr * 2, r_max + pr * 2],
    )
    yaxis = dict(
        **ax_shared,
        title=dict(
            text="← Lower   PREMIUM SCORE   Higher →",
            font=dict(size=13, color=AX_TITLE, family=MONO),
            standoff=14,
        ),
        range=[p_min - pp * 2, p_max + pp * 2],
    )
    return xaxis, yaxis


### === Scatter Plot Design ====================================================================
 
### --- Scatter 1: Global Top N ------------------------------------------------
def _scatter_global_view(df: pd.DataFrame, top_n: int = 20) -> go.Figure:
    """
    Full scatter — top N globally labeled by premium_score - risk_score.
    Labels are uniform teal (ACCENT color).
    """
    fig = go.Figure()
 
    r_min, r_max = df["risk_score"].min(),    df["risk_score"].max()
    p_min, p_max = df["premium_score"].min(), df["premium_score"].max()
    r_mid = df["risk_score"].median()
    p_mid = df["premium_score"].median()
    pr = (r_max - r_min) * 0.04
    pp = (p_max - p_min) * 0.04
 
    _add_quadrant_base(fig, df, r_mid, p_mid, r_min, r_max, p_min, p_max, pr, pp)
    _add_scatter_traces(fig, df)
 
    # Global top N — ranked by premium minus risk
    df2 = df.copy()
    df2["_rank"] = df2["premium_score"] - df2["risk_score"]
    top = df2.nlargest(top_n, "_rank")
 
    for _, row in top.iterrows():   ### Place symbols on plot
        fig.add_annotation(
            x=row["risk_score"],
            y=row["premium_score"],
            text=f"{row['symbol']}",
            showarrow=False,
            font=dict(size=14, color=LABEL_TEAL, family=MONO),
            xanchor="left",
            yanchor="middle",
            xshift=6,    # ← horizontal distance from point (pixels, + = right)
            yshift=2,    # ← vertical distance from point (pixels, + = up)
            opacity=0.95,
        )
 
    xaxis, yaxis = _base_axes(r_min, r_max, p_min, p_max, pr, pp)
    fig.update_layout(
        **_base_layout(
            df,
            title_text=(
                "<b>Option Premium to Risk Analysis · Top N Global Premium/Risk Score Spread (Alf 1.0)</b><br>"
                f"<span style='font-size:14px;color:#6b7394'>"
                f"n = {len(df)} symbols    "
                f"top {top_n} labeled globally by Premium − Risk Spread"
                "</span>"
            ),
        ),
        xaxis=xaxis,
        yaxis=yaxis,
    )
    return fig
 
 
### ── Scatter 2: Top N per Quadrant ────────────────────────────────
def _scatter_quadrant_top_n(df: pd.DataFrame, top_n: int = 20) -> go.Figure:
    """
    Full scatter — top N per quadrant, each in its quadrant color.
 
    Selection: For each quandrant specifically, viausl displays a spatial
    depth score to identify symbols sitting deepest in their respective 
    quadrant, avoiding bunching in the global center. 
 
    Ranking scores (multiplication rewards strength on BOTH dimensions):
      Q1: premium * (100 - risk)        high premium AND low risk
      Q2: premium * risk                high premium AND high risk
      Q3: (100-premium) * (100-risk)    low premium AND low risk
      Q4: (100-premium) * risk          low premium AND high risk
 
    With top_n=20 you get 5 labeled per quadrant.
    With top_n=16 you get exactly 4 per quadrant.
    """

    fig = go.Figure()
 
    r_min, r_max = df["risk_score"].min(),    df["risk_score"].max()
    p_min, p_max = df["premium_score"].min(), df["premium_score"].max()
    r_mid = df["risk_score"].median()
    p_mid = df["premium_score"].median()
    pr = (r_max - r_min) * 0.04
    pp = (p_max - p_min) * 0.04
 
    _add_quadrant_base(fig, df, r_mid, p_mid, r_min, r_max, p_min, p_max, pr, pp)
    _add_scatter_traces(fig, df)
 
    # Spatial depth ranking — filter first by pre-assigned quadrant,
    # then rank within each group using quadrant-appropriate score
    # quad_rank_fns = {
    #     "Q1": lambda d: d["premium_score"] * (100 - d["risk_score"]),
    #     "Q2": lambda d: d["premium_score"] * d["risk_score"],
    #     "Q3": lambda d: (100 - d["premium_score"]) * (100 - d["risk_score"]),
    #     "Q4": lambda d: (100 - d["premium_score"]) * d["risk_score"],
    # }

    # Normalize scores to 0-100 range for spatial depth ranking
    p_norm = (df["premium_score"] - df["premium_score"].min()) / (df["premium_score"].max() - df["premium_score"].min()) * 100
    r_norm = (df["risk_score"]    - df["risk_score"].min())    / (df["risk_score"].max()    - df["risk_score"].min())    * 100

    quad_rank_fns = {
        "Q1": lambda d, p=p_norm, r=r_norm: p.loc[d.index] * (100 - r.loc[d.index]),
        "Q2": lambda d, p=p_norm, r=r_norm: p.loc[d.index] * r.loc[d.index],
        "Q3": lambda d, p=p_norm, r=r_norm: (100 - p.loc[d.index]) * (100 - r.loc[d.index]),
        "Q4": lambda d, p=p_norm, r=r_norm: (100 - p.loc[d.index]) * r.loc[d.index],
    }

    n_per_q = max(1, top_n // 4)
    top_frames = []
    
    for q, rank_fn in quad_rank_fns.items():
        subset = df[df["quadrant"].str.startswith(q)].copy()  ## Search for the first two char. Q1, Q2, etc...
        if subset.empty:
            continue
        subset["_rank"] = rank_fn(subset)
        top_frames.append(subset.nlargest(n_per_q, "_rank"))
 
    top_per_q = pd.concat(top_frames)
 
    for _, row in top_per_q.iterrows():
        q_color = Q_COLORS.get(str(row["quadrant"])[:2], LABEL_TEAL)
        fig.add_annotation(
            x=row["risk_score"],
            y=row["premium_score"],
            text=f"{row['symbol']}",
            showarrow=False,
            font=dict(size=14, color=LABEL_TEAL, family=MONO),
            xanchor="left",
            yanchor="middle",
            xshift=6,    # ← horizontal distance from point (pixels, + = right)
            yshift=2,    # ← vertical distance from point (pixels, + = up)
            opacity=0.95,
        )
 
    xaxis, yaxis = _base_axes(r_min, r_max, p_min, p_max, pr, pp)
    fig.update_layout(
        **_base_layout(
            df,
            title_text=(
                "<b>Option Premium to Risk Analysis · Top N per Quadrant</b><br>"
                f"<span style='font-size:11px;color:#6b7394'>"
                f"n = {len(df)} symbols    "
                f"top {n_per_q} per quadrant ({top_n} total)  ·  "
                f"ranked by spatial depth within quadrant"
                "</span>"
            ),
        ),
        xaxis=xaxis,
        yaxis=yaxis,
    )
    return fig


### === Master Dashboard Run =====================================================================
### ------------------------------------------------------------------------------------------

# ─────────────────────────────────────────────────────────────
def build_dashboard(
    df: pd.DataFrame,
    top_n: int = 20,
    div_quadrant: str = "Q1",
) -> dict:
    """
    Build all dashboard figures and return as a dict.

    Parameters
    ----------
    df            : DataFrame with symbol, risk_score, premium_score, [quadrant]
    top_n         : N symbols shown in bar/bubble charts  (default 20)
    div_quadrant  : which quadrant to use in diversification view (default 'Q1')

    Returns
    -------
    dict of {name: go.Figure}  — call .show() on any or all of them.

    Example
    -------
    figs = build_dashboard(df)
    figs["scatter"].show()
    figs["top_premium"].show()
    figs["q1_top"].show()
    figs["diversification"].show()
    """
    df = _assign_quadrants(df)

    figs = {}

    # 1. Full scatter
    figs["scatter"] = _scatter_global_view(df, top_n=top_n)

    # 2. Global top-N by premium score
    figs["top_premium"] = _top_n_bar(
        df, "premium_score", top_n,
        f"Global Top {top_n} · Premium Score",
        ACCENT,
    )

    # 3. Global top-N by risk score (lowest = best for put-selling)
    df_risk = df.copy()
    df_risk["risk_score_inv"] = df_risk["risk_score"].max() - df_risk["risk_score"]
    figs["top_risk"] = _top_n_bar(
        df_risk, "risk_score_inv", top_n,
        f"Global Top {top_n} · Lowest Risk (inverted)",
        Q_COLORS["Q1"],
    )

    #4. 
    df_risk = df.copy()
    # lowest risk — ascending=True flips to nsmallest
    figs["top_risk"] = _top_n_bar(df, "risk_score", top_n,
    f"Global Top {top_n} · Lowest Risk Score", ascending=True,
    )

    # 4. Per-quadrant top-N bar charts
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        figs[f"{q.lower()}_top"] = _quadrant_top_n(df, q, top_n=top_n)

    # 5. Diversification bubble
    figs["diversification"] = _diversification_view(df, div_quadrant, top_n=top_n)

    return figs


# ─────────────────────────────────────────────────────────────
def show_all(figs: dict):
    """Render every figure sequentially (useful in Jupyter)."""
    for name, fig in figs.items():
        print(f"\n── {name} ──")
        fig.show()


def export_html(figs: dict, path: str = "etf_screening_dashboard.html"):
    """
    Export all views into a single self-contained HTML file with
    a tab-switcher nav bar.
    """
    import plotly.io as pio

    nav_items = ""
    div_items = ""
    for i, (name, fig) in enumerate(figs.items()):
        active_btn = "active" if i == 0 else ""
        active_div = "block" if i == 0 else "none"
        html_chart = pio.to_html(fig, full_html=False, include_plotlyjs=(i == 0))
        label = name.replace("_", " ").title()
        nav_items += (
            f'<button class="tab-btn {active_btn}" '
            f'onclick="showTab({i})" id="btn-{i}">{label}</button>\n'
        )
        div_items += (
            f'<div class="tab-pane" id="pane-{i}" '
            f'style="display:{active_div}">{html_chart}</div>\n'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>ETF Screening Dashboard</title>
<style>
  body {{ background:#0d0f14; color:#e8eaf2;
         font-family:'JetBrains Mono',monospace; margin:0; padding:0; }}
  .nav {{ background:#13161e; border-bottom:1px solid #1f2433;
          padding:10px 20px; display:flex; gap:8px; flex-wrap:wrap; }}
  .tab-btn {{
    background:#1a1e2b; color:#6b7394; border:1px solid #1f2433;
    padding:6px 14px; border-radius:4px; cursor:pointer;
    font-family:'JetBrains Mono',monospace; font-size:11px;
    transition:all .15s;
  }}
  .tab-btn:hover {{ color:#e8eaf2; border-color:#4fc3f7; }}
  .tab-btn.active {{ background:#4fc3f7; color:#0d0f14; border-color:#4fc3f7; }}
  .content {{ padding:12px 20px; }}
</style>
</head>
<body>
<div class="nav">{nav_items}</div>
<div class="content">{div_items}</div>
<script>
function showTab(idx) {{
  document.querySelectorAll('.tab-pane').forEach((p,i)=>
    p.style.display = i===idx ? 'block' : 'none');
  document.querySelectorAll('.tab-btn').forEach((b,i)=>
    b.classList.toggle('active', i===idx));
}}
</script>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard exported → {path}")


# ─────────────────────────────────────────────────────────────
# Demo / smoke test with synthetic data
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    rng = np.random.default_rng(42)
    n = 600
    mock_df = pd.DataFrame({
        "symbol": [f"ETF{i:03d}" for i in range(n)],
        "risk_score": rng.beta(2, 3, n) * 100,
        "premium_score": rng.beta(2, 5, n) * 100 + rng.normal(0, 3, n),
    })
    mock_df["premium_score"] = mock_df["premium_score"].clip(0, 100)

    figs = build_dashboard(mock_df, top_n=20, div_quadrant="Q1")
    export_html(figs, "etf_screening_demo.html")
    print("Figures available:", list(figs.keys()))
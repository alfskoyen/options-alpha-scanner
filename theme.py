"""
theme.py
────────────────────────────────────────────────────────────────────────
Single source of truth for all design tokens used across the dashboard.

All chart modules import from here:
    from theme import BG, PANEL, Q_COLORS, MONO, base_layout, axis

To restyle the entire app, change values here only.
"""

# ── Backgrounds ───────────────────────────────────────────────────
BG        = "#1e2127"   # page / paper background — dark grey
PANEL     = "#252830"   # chart plot area / card background
ROW_ALT   = "#222630"   # alternating table row

# ── Borders & lines ───────────────────────────────────────────────
BORDER    = "#2e3340"   # panel borders
GRID      = "#2a2f3e"   # chart gridlines
CROSS     = "#4a5270"   # quadrant divider lines / table grid

# ── Text ─────────────────────────────────────────────────────────
TEXT_PRI  = "#edf0f7"   # primary text — near white, slight blue tint
TEXT_SEC  = "#8b93b0"   # secondary text — muted
TEXT_DIM  = "#4a5270"   # dimmed text — hints, watermarks
TEXT_AX   = "#c8cfe8"   # axis tick values — bright
AX_TITLE  = "#6ecece"   # axis title text — teal

# ── Accent ───────────────────────────────────────────────────────
ACCENT     = "#4DD2D9"   # primary accent — teal
LABEL_TEAL = "#4DD2D9"   # quadrant corner labels

# ── Quadrant colors ───────────────────────────────────────────────
Q_COLORS = {
    "Q1": "#2DD68B",   # mint green  — High Premium / Low Risk  (ideal)
    "Q2": "#ffb340",   # warm amber  — High Premium / High Risk (risky/rich)
    "Q3": "#7b8bad",   # steel blue  — Low Premium  / Low Risk  (boring)
    "Q4": "#ff5c6a",   # coral red   — Low Premium  / High Risk (avoid)
}

Q_LABELS = {
    "Q1": "Q1 · High Premium / Low Risk",
    "Q2": "Q2 · High Premium / High Risk",
    "Q3": "Q3 · Low Premium  / Low Risk",
    "Q4": "Q4 · Low Premium  / High Risk",
}
#     "Q1": "Q1",
#     "Q2": "Q2", 
#     "Q3": "Q3", 
#     "Q4": "Q4", 

# ── Typography ────────────────────────────────────────────────────
MONO = "JetBrains Mono, Fira Mono, Consolas, monospace"

# ── Shared layout helpers ─────────────────────────────────────────
def base_layout(title_text: str, height: int = 625,
                margin: dict = None) -> dict:
    """
    Base Plotly layout dict applied to all figures.
    Unpack and override any key after:
        fig.update_layout(**base_layout(...), xaxis=axis("x →"))
    """
    return dict(
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        height=height,
        margin=margin or dict(l=72, r=180, t=72, b=64),
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
            x=1.02, y=1,
            xanchor="left",
            yanchor="top",
        ),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#1a1d28",
            bordercolor=CROSS,
            font=dict(size=12, color=TEXT_PRI, family=MONO),
            namelength=0,
        ),
        font=dict(family=MONO, color=TEXT_PRI, size=11),
    )


def axis(title: str = "", **kw) -> dict:
    """Standard axis styling. Pass extra kwargs to override."""
    base = dict(
        title=dict(text=title, font=dict(size=12, color=AX_TITLE, family=MONO)),
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        linecolor="#363b50",
        linewidth=1,
        tickfont=dict(size=13, color=TEXT_AX, family=MONO),
        ticklen=5,
        showgrid=True,
    )
    base.update(kw)
    return base


# ── DMC theme config (Dash Mantine Components) ────────────────────
DMC_THEME = {
    "colorScheme": "dark",
    "fontFamily":  MONO,
    "primaryColor": "cyan",
    "colors": {
        "dark": [
            TEXT_PRI,    # 0 — lightest
            "#b0b8d4",   # 1
            "#8892b0",   # 2
            TEXT_SEC,    # 3
            "#3d4466",   # 4
            BORDER,      # 5
            PANEL,       # 6
            BG,          # 7
            "#090b10",   # 8
            "#05060a",   # 9 — darkest
        ],
    },
}

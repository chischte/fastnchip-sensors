"""
fastnchip-sensors – long-term data viewer
Reads measurements.csv and shows interactive charts for CO2, Temperature,
and Humidity. Refreshes automatically while the logger is running.

Requirements:
    pip install matplotlib pandas
"""

import sys
from datetime import timedelta
from pathlib import Path

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.patches as mpatches
    from matplotlib.ticker import MultipleLocator
    from matplotlib.patches import FancyBboxPatch
    import matplotlib.animation as animation
except ImportError:
    print("Missing dependencies. Run:  pip install matplotlib pandas")
    sys.exit(1)

CSV_FILE = Path(__file__).parent / "data" / "measurements.csv"
REFRESH_INTERVAL_MS = 10_000

BG_PAGE    = "#f3f6f4"
BG_CARD    = "#ffffff"
BG_PLOT    = "#f9faf9"
COLOR_GRID = "#d9e2dc"
COLOR_BORDER = "#d9e2dc"
BTN_ON  = "#3b8c62"
BTN_OFF = "#b0bfb8"

SERIES = [
    {"col": "co2_ppm",       "label": "CO2",         "unit": "ppm", "color": "#d65a4a", "ymin": 0,  "ymax": 10000, "step": None, "fmt": ".0f"},
    {"col": "temperature_c", "label": "Temperature",  "unit": "°C",  "color": "#2878a8", "ymin": 20, "ymax": 35,    "step": 5,    "fmt": ".1f"},
    {"col": "humidity_rh",   "label": "Humidity",     "unit": "%RH", "color": "#3b8c62", "ymin": 85, "ymax": 100,   "step": 5,    "fmt": ".1f"},
]

_state = {"show_24h": False}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
    df.sort_values("timestamp", inplace=True)
    return df


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    if _state["show_24h"]:
        cutoff = df["timestamp"].max() - timedelta(hours=24)
        return df[df["timestamp"] >= cutoff]
    return df


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def format_xaxis(ax: "plt.Axes", df: pd.DataFrame) -> None:
    span = (df["timestamp"].max() - df["timestamp"].min()).total_seconds()
    if span < 3600:
        locator = mdates.MinuteLocator(byminute=range(0, 60, 5))
        fmt = mdates.DateFormatter("%H:%M")
    elif span < 86400:
        locator = mdates.HourLocator()
        fmt = mdates.DateFormatter("%H:%M")
    elif span < 7 * 86400:
        locator = mdates.HourLocator(byhour=range(0, 24, 6))
        fmt = mdates.DateFormatter("%d.%m %H:%M")
    else:
        locator = mdates.DayLocator()
        fmt = mdates.DateFormatter("%d.%m")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(fmt)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")


def plot_series(ax: "plt.Axes", df: pd.DataFrame, s: dict) -> None:
    ax.clear()
    col = s["col"]
    ax.fill_between(df["timestamp"], df[col], s["ymin"],
                    color=s["color"], alpha=0.12, zorder=2)
    ax.plot(df["timestamp"], df[col], color=s["color"], linewidth=1.5, zorder=3)
    ax.set_ylim(s["ymin"], s["ymax"])
    if s["step"]:
        ax.yaxis.set_major_locator(MultipleLocator(s["step"]))
    ax.set_title(f'{s["label"]} [{s["unit"]}]', fontsize=10, fontweight="bold",
                 color="#2a3630", pad=6)
    ax.set_facecolor(BG_PLOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COLOR_GRID)
    ax.tick_params(colors="#607068", labelsize=8)
    ax.grid(True, linestyle="--", linewidth=0.6, color=COLOR_GRID, zorder=1)
    format_xaxis(ax, df)


# ---------------------------------------------------------------------------
# Value boxes (like the website cards)
# ---------------------------------------------------------------------------

def draw_value_boxes(box_axes: list, last: pd.Series) -> None:
    for ax, s in zip(box_axes, SERIES):
        ax.clear()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # White card background with border
        card = FancyBboxPatch((0.03, 0.05), 0.94, 0.90,
                              boxstyle="round,pad=0.02",
                              linewidth=1, edgecolor=COLOR_BORDER,
                              facecolor=BG_CARD,
                              transform=ax.transAxes, zorder=1,
                              clip_on=False)
        ax.add_patch(card)

        val = last[s["col"]]
        val_str = format(val, s["fmt"])

        # Label (top, bold, muted grey like units)
        ax.text(0.5, 0.78, s["label"],
                ha="center", va="center", fontsize=10, fontweight="bold",
                color="#607068", transform=ax.transAxes, zorder=2)
        # Value (middle, large bold, metric color)
        ax.text(0.5, 0.45, val_str,
                ha="center", va="center", fontsize=22, fontweight="bold",
                color=s["color"], transform=ax.transAxes, zorder=2)
        # Unit (bottom, slightly larger, bold, muted)
        ax.text(0.5, 0.16, s["unit"],
                ha="center", va="center", fontsize=10, fontweight="bold",
                color="#607068", transform=ax.transAxes, zorder=2)


# ---------------------------------------------------------------------------
# Toggle switch (drawn on a dedicated axes)
# ---------------------------------------------------------------------------

def draw_toggle(toggle_ax: "plt.Axes") -> None:
    toggle_ax.clear()
    # Fixed data coords: width=10, height=1 — aspect is controlled by add_axes size
    toggle_ax.set_xlim(0, 10)
    toggle_ax.set_ylim(0, 1)
    toggle_ax.set_aspect("auto")
    toggle_ax.axis("off")

    on = _state["show_24h"]
    track_color = BTN_ON if on else BTN_OFF

    # Track: x=3..7, y=0.2..0.8
    track = FancyBboxPatch((3.0, 0.20), 4.0, 0.60,
                           boxstyle="round,pad=0.12",
                           linewidth=0, facecolor=track_color,
                           zorder=1)
    toggle_ax.add_patch(track)

    # Knob: a square-ish patch so it looks like a round pill knob
    kx = 5.8 if on else 3.2
    knob = FancyBboxPatch((kx - 0.55, 0.22), 1.1, 0.56,
                          boxstyle="round,pad=0.10",
                          linewidth=0, facecolor="white", zorder=2)
    toggle_ax.add_patch(knob)

    # Labels
    col_all = "#2a3630" if not on else "#9aada6"
    col_24h = "#2a3630" if on     else "#9aada6"
    fw_all  = "bold"    if not on else "normal"
    fw_24h  = "bold"    if on     else "normal"

    toggle_ax.text(2.2, 0.50, "All", ha="right", va="center",
                   fontsize=9, color=col_all, fontweight=fw_all)
    toggle_ax.text(7.3, 0.50, "24 h", ha="left", va="center",
                   fontsize=9, color=col_24h, fontweight=fw_24h)

    toggle_ax.figure.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Main draw loop
# ---------------------------------------------------------------------------

def draw(fig: "plt.Figure", box_axes: list, chart_axes: list,
         toggle_ax: "plt.Axes", footer_text: "plt.Text") -> None:
    try:
        df_all = load_data()
    except Exception as exc:
        print(f"Could not read CSV: {exc}", file=sys.stderr)
        return

    df = filter_data(df_all)
    if df.empty:
        return

    last = df_all.iloc[-1]
    ts = last["timestamp"]

    draw_value_boxes(box_axes, last)
    for ax, s in zip(chart_axes, SERIES):
        plot_series(ax, df, s)
    draw_toggle(toggle_ax)

    footer_text.set_text(
        f"Last Reading:  {ts.strftime('%A, %d %B %Y')}  {ts.strftime('%H:%M:%S')}"
        f"   |   {len(df_all)} data points"
    )

    fig.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not CSV_FILE.exists():
        print(f"No data file found at {CSV_FILE}")
        print("Start logger.py first to collect measurements.")
        sys.exit(1)

    fig = plt.figure(figsize=(13, 10.5))
    fig.patch.set_facecolor(BG_PAGE)

    from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

    # Outer grid: row 0 = boxes, row 1 = charts block, row 2 = toggle
    gs_outer = GridSpec(
        3, 1,
        figure=fig,
        height_ratios=[1, 6.5, 0.01],
        hspace=0.12,          # gap between boxes row and charts block
        top=0.97, bottom=0.10, left=0.07, right=0.97,
    )

    # Inner grid for the 3 charts — controls spacing between charts only
    gs_charts = GridSpecFromSubplotSpec(
        3, 1,
        subplot_spec=gs_outer[1],
        hspace=0.52,
    )

    # Value boxes (top row, one per column)
    gs_boxes = GridSpecFromSubplotSpec(1, 3, subplot_spec=gs_outer[0], wspace=0.28)
    box_axes = [fig.add_subplot(gs_boxes[0, i]) for i in range(3)]

    # Charts
    chart_axes = [fig.add_subplot(gs_charts[r]) for r in range(3)]

    # Toggle: fixed-size axes so it is never distorted
    toggle_ax = fig.add_axes([0.43, 0.055, 0.14, 0.048])

    # Footer text at very bottom
    footer_text = fig.text(
        0.5, 0.012, "",
        ha="center", va="bottom",
        fontsize=8, color="#607068", fontfamily="monospace",
    )

    draw(fig, box_axes, chart_axes, toggle_ax, footer_text)

    # Click on toggle_ax flips state
    def _on_click(event):
        if event.inaxes is toggle_ax:
            _state["show_24h"] = not _state["show_24h"]
            draw(fig, box_axes, chart_axes, toggle_ax, footer_text)

    fig.canvas.mpl_connect("button_press_event", _on_click)

    def _update(_frame):
        draw(fig, box_axes, chart_axes, toggle_ax, footer_text)

    ani = animation.FuncAnimation(
        fig, _update, interval=REFRESH_INTERVAL_MS, cache_frame_data=False
    )
    _ = ani

    plt.show()


if __name__ == "__main__":
    main()



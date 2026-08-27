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
    {"col": "co2_ppm",     "label": "CO2",        "unit": "ppm", "color": "#d65a4a", "ymin": 0,  "ymax": 10000, "step": None, "fmt": ".0f"},
    {"col": "temp_box_c",  "label": "Temperature", "unit": "°C",  "color": "#2878a8", "ymin": 20, "ymax": 35,    "step": 5,    "fmt": ".1f",
     "overlay_col": "temp_outer_c", "overlay_color": "#7bafd4"},
    {"col": "humidity_rh", "label": "Humidity",    "unit": "%RH", "color": "#3b8c62", "ymin": 85, "ymax": 100,   "step": 5,    "fmt": ".1f"},
]

_state = {"range": "all"}   # "all" | "40d" | "24h" | "30m"

RANGES = [
    ("all", "all data",    None),
    ("40d", "40 days",     timedelta(days=40)),
    ("24h", "24 hours",    timedelta(hours=24)),
    ("30m", "30 minutes",  timedelta(minutes=30)),
    ("5m",  "5 minutes",   timedelta(minutes=5)),
]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"],
                     names=["timestamp", "co2_ppm", "temp_box_c", "humidity_rh", "temp_outer_c"],
                     header=0, on_bad_lines="skip")
    if "temp_outer_c" not in df.columns:
        df["temp_outer_c"] = float("nan")
    df["temp_outer_c"] = pd.to_numeric(df["temp_outer_c"], errors="coerce")
    df.sort_values("timestamp", inplace=True)
    return df


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    delta = next(d for k, _, d in RANGES if k == _state["range"])
    if delta is None:
        return df
    cutoff = df["timestamp"].max() - delta
    return df[df["timestamp"] >= cutoff]


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def format_xaxis(ax: "plt.Axes", df: pd.DataFrame) -> None:
    span = (df["timestamp"].max() - df["timestamp"].min()).total_seconds()

    def _fmt_with_midnight(x, pos):
        dt = mdates.num2date(x)
        if dt.hour == 0 and dt.minute == 0:
            return dt.strftime("%d.%m\n00:00")
        return dt.strftime("%H:%M")

    def _bold_midnight():
        ax.get_figure().canvas.draw()
        for label in ax.get_xticklabels():
            if "\n" in label.get_text():
                label.set_fontweight("bold")

    if _state["range"] == "24h":
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(_fmt_with_midnight))
        t_max = df["timestamp"].max()
        ax.set_xlim(mdates.date2num(t_max - timedelta(hours=24)), mdates.date2num(t_max))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        _bold_midnight()
    elif _state["range"] == "5m":
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        t_max = df["timestamp"].max()
        ax.set_xlim(mdates.date2num(t_max - timedelta(minutes=5)), mdates.date2num(t_max))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    elif _state["range"] == "30m":
        ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 5)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        t_max = df["timestamp"].max()
        ax.set_xlim(mdates.date2num(t_max - timedelta(minutes=30)), mdates.date2num(t_max))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    elif span < 3600:
        ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 5)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    elif span < 86400:
        ax.xaxis.set_major_locator(mdates.HourLocator())
        ax.xaxis.set_major_formatter(plt.FuncFormatter(_fmt_with_midnight))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        _bold_midnight()
    elif span < 7 * 86400:
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(_fmt_with_midnight))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        _bold_midnight()
    else:
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")


def plot_series(ax: "plt.Axes", df: pd.DataFrame, s: dict) -> None:
    ax.clear()
    col = s["col"]
    ax.fill_between(df["timestamp"], df[col], s["ymin"],
                    color=s["color"], alpha=0.12, zorder=2)
    ax.plot(df["timestamp"], df[col], color=s["color"], linewidth=1.5, zorder=3,
            label="Box (SCD41)")

    # Optional second line (e.g. RTD ambient temperature)
    overlay_col = s.get("overlay_col")
    if overlay_col and overlay_col in df.columns:
        valid = df[overlay_col].notna() & (df[overlay_col] != 0)
        if valid.any():
            ax.plot(df["timestamp"][valid], df[overlay_col][valid],
                    color=s["overlay_color"], linewidth=1.2, linestyle="--",
                    zorder=4, label="Ambient (PT100)")
            ax.legend(fontsize=7, loc="upper left", framealpha=0.7,
                      facecolor=BG_CARD, edgecolor=COLOR_GRID)

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

        # Check for RTD overlay delta (temperature box only)
        overlay_col = s.get("overlay_col")
        has_delta = False
        delta_str = ""
        if overlay_col and overlay_col in last.index:
            rtd_val = last[overlay_col]
            if pd.notna(rtd_val) and rtd_val != 0:
                delta = val - rtd_val
                sign = "+" if delta >= 0 else ""
                delta_str = f"{sign}{delta:.1f}"
                has_delta = True

        val_y = 0.45

        # Label (top, bold, muted grey)
        ax.text(0.5, 0.78, s["label"],
                ha="center", va="center", fontsize=10, fontweight="bold",
                color="#607068", transform=ax.transAxes, zorder=2)
        # Value (always centered in box)
        ax.text(0.5, val_y, val_str,
                ha="center", va="center", fontsize=22, fontweight="bold",
                color=s["color"], transform=ax.transAxes, zorder=2)
        # RTD delta (centered between value right-edge and box right wall)
        if has_delta:
            ax.text(0.82, val_y, delta_str,
                    ha="center", va="center", fontsize=11, fontweight="bold",
                    color=s.get("overlay_color", "#7bafd4"),
                    transform=ax.transAxes, zorder=2)
        # Unit (bottom)
        ax.text(0.5, 0.13, s["unit"],
                ha="center", va="center", fontsize=10, fontweight="bold",
                color="#607068", transform=ax.transAxes, zorder=2)


# ---------------------------------------------------------------------------
# Checkboxes (radio-style: one selected at a time)
# ---------------------------------------------------------------------------

def draw_checkboxes(cb_ax: "plt.Axes") -> None:
    cb_ax.clear()
    cb_ax.set_xlim(0, 1)
    cb_ax.set_ylim(0, 1)
    cb_ax.axis("off")

    # Outer card — clip_on=False so border is fully visible
    card = FancyBboxPatch((0.01, 0.08), 0.98, 0.84,
                          boxstyle="round,pad=0.02",
                          linewidth=1, edgecolor=COLOR_BORDER,
                          facecolor=BG_CARD,
                          transform=cb_ax.transAxes, zorder=1,
                          clip_on=False)
    cb_ax.add_patch(card)

    n = len(RANGES)
    margin = 0.10
    slot_w = (1 - 2 * margin) / n
    box_w  = 0.022

    for i, (key, label, _) in enumerate(RANGES):
        cx = margin + (i + 0.5) * slot_w
        selected = _state["range"] == key

        # Fixed positions that look centred: box at y=0.38..0.66, label centre at 0.22
        box_h   = 0.28
        box_y   = 0.38
        label_y = 0.22   # text centre (va=center)

        rect = FancyBboxPatch((cx - box_w / 2, box_y), box_w, box_h,
                              boxstyle="round,pad=0.003",
                              linewidth=1.2,
                              edgecolor=BTN_ON if selected else "#9aada6",
                              facecolor=BTN_ON if selected else BG_PAGE,
                              transform=cb_ax.transAxes, zorder=2,
                              clip_on=False)
        cb_ax.add_patch(rect)

        cb_ax.text(cx, label_y, label,
                   ha="center", va="center", fontsize=8,
                   color="#2a3630" if selected else "#607068",
                   fontweight="bold" if selected else "normal",
                   transform=cb_ax.transAxes, zorder=2)

    cb_ax.figure.canvas.draw_idle()


# ---------------------------------------------------------------------------
# Main draw loop
# ---------------------------------------------------------------------------

def draw(fig: "plt.Figure", box_axes: list, chart_axes: list,
         cb_ax: "plt.Axes", footer_text: "plt.Text") -> None:
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
    draw_checkboxes(cb_ax)

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

    # Checkboxes: fixed-size axes at the bottom centre
    cb_ax = fig.add_axes([0.28, 0.030, 0.44, 0.060])

    # Footer text at very bottom
    footer_text = fig.text(
        0.5, 0.008, "",
        ha="center", va="bottom",
        fontsize=8, color="#607068", fontfamily="monospace",
    )

    draw(fig, box_axes, chart_axes, cb_ax, footer_text)

    # Click on a checkbox selects that range
    def _on_click(event):
        if event.inaxes is cb_ax and event.xdata is not None:
            n = len(RANGES)
            idx = int(event.xdata * n)
            idx = max(0, min(n - 1, idx))
            _state["range"] = RANGES[idx][0]
            draw(fig, box_axes, chart_axes, cb_ax, footer_text)

    fig.canvas.mpl_connect("button_press_event", _on_click)

    def _update(_frame):
        draw(fig, box_axes, chart_axes, cb_ax, footer_text)

    ani = animation.FuncAnimation(
        fig, _update, interval=REFRESH_INTERVAL_MS, cache_frame_data=False
    )
    _ = ani

    plt.show()


if __name__ == "__main__":
    main()



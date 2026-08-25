"""
fastnchip-sensors – long-term data viewer
Reads measurements.csv and shows interactive charts for CO2, Temperature,
and Humidity. Refreshes automatically while the logger is running.

Requirements:
    pip install matplotlib pandas
"""

import sys
from pathlib import Path

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import MultipleLocator
    import matplotlib.animation as animation
except ImportError:
    print("Missing dependencies. Run:  pip install matplotlib pandas")
    sys.exit(1)

CSV_FILE = Path(__file__).parent / "data" / "measurements.csv"
REFRESH_INTERVAL_MS = 10_000   # live-refresh every 10 s while logger is running

BG_PAGE   = "#f3f6f4"
BG_CARD   = "#ffffff"
BG_PLOT   = "#f9faf9"
COLOR_GRID = "#d9e2dc"

SERIES = [
    {"col": "co2_ppm",       "label": "CO2 [ppm]",         "unit": "ppm", "color": "#d65a4a", "ymin": 0,    "ymax": 10000, "step": None},
    {"col": "temperature_c", "label": "Temperature [°C]",  "unit": "°C",  "color": "#2878a8", "ymin": 20,   "ymax": 35,    "step": 5},
    {"col": "humidity_rh",   "label": "Humidity [%RH]",    "unit": "%RH", "color": "#3b8c62", "ymin": 85,   "ymax": 100,   "step": 5},
]


def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
    df.sort_values("timestamp", inplace=True)
    return df


def format_xaxis(ax: "plt.Axes", df: pd.DataFrame) -> None:
    span = (df["timestamp"].max() - df["timestamp"].min()).total_seconds()
    if span < 3600:
        locator = mdates.MinuteLocator(byminute=range(0, 60, 5))
        fmt = mdates.DateFormatter("%H:%M")
    elif span < 86400:
        locator = mdates.HourLocator()
        fmt = mdates.DateFormatter("%H:%M")
    else:
        locator = mdates.DayLocator()
        fmt = mdates.DateFormatter("%d.%m")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(fmt)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")


def plot_series(ax: "plt.Axes", df: pd.DataFrame, s: dict) -> None:
    ax.clear()
    col = s["col"]

    # Fill under curve like the web UI
    ax.fill_between(df["timestamp"], df[col], s["ymin"],
                    color=s["color"], alpha=0.12, zorder=2)
    ax.plot(df["timestamp"], df[col], color=s["color"], linewidth=1.5, zorder=3)

    # Fixed Y range matching web UI
    ax.set_ylim(s["ymin"], s["ymax"])
    if s["step"]:
        ax.yaxis.set_major_locator(MultipleLocator(s["step"]))

    ax.set_title(s["label"], fontsize=10, fontweight="bold", color="#2a3630", pad=6)
    ax.set_facecolor(BG_PLOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COLOR_GRID)
    ax.tick_params(colors="#607068", labelsize=8)
    ax.grid(True, linestyle="--", linewidth=0.6, color=COLOR_GRID, zorder=1)

    format_xaxis(ax, df)


def draw(fig: "plt.Figure", axes: list, live: bool) -> None:
    try:
        df = load_data()
    except Exception as exc:
        print(f"Could not read CSV: {exc}", file=sys.stderr)
        return

    for ax, s in zip(axes, SERIES):
        plot_series(ax, df, s)

    # stats bar in last subplot
    last = df.iloc[-1]
    fig.suptitle(
        f"Last reading: {last['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}  |  "
        f"CO₂ {last['co2_ppm']:.0f} ppm  |  "
        f"Temp {last['temperature_c']:.1f} °C  |  "
        f"Hum {last['humidity_rh']:.1f} %RH  |  "
        f"{len(df)} data points",
        fontsize=9, color="#607068",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])


def main() -> None:
    if not CSV_FILE.exists():
        print(f"No data file found at {CSV_FILE}")
        print("Start logger.py first to collect measurements.")
        sys.exit(1)

    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=False)
    fig.patch.set_facecolor(BG_PAGE)
    fig.subplots_adjust(hspace=0.45)

    draw(fig, axes, live=True)

    # Animate: re-read CSV every REFRESH_INTERVAL_MS
    def _update(_frame):
        draw(fig, axes, live=True)

    ani = animation.FuncAnimation(
        fig, _update, interval=REFRESH_INTERVAL_MS, cache_frame_data=False
    )
    _ = ani  # keep reference so GC doesn't delete it

    plt.show()


if __name__ == "__main__":
    main()

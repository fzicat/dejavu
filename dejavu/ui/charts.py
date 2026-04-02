import logging
import shutil
from typing import Dict, Optional

import pandas as pd
from rich.console import Console
from rich.text import Text

logger = logging.getLogger(__name__)
console = Console()


def plot_equity_curve(curve_series):
    logger.debug("Plotting equity curve")
    console.print("[blue]Equity Curve generated (placeholder).[/blue]")


def plot_price_and_states(df):
    logger.debug("Plotting price/states chart")
    console.print("[cyan]Price & Regimes chart generated (placeholder).[/cyan]")


def render_annotated_hlc(
    df: pd.DataFrame,
    states: Optional[pd.Series] = None,
    labels: Optional[Dict[int, str]] = None,
    trades: Optional[pd.DataFrame] = None,
    overlay_vwap: bool = False,
    show_states: bool = True,
    show_trades: bool = True,
):
    if df is None or df.empty:
        console.print("[red]No data to chart.[/red]")
        return

    labels = labels or {0: "Default"}
    terminal_width = shutil.get_terminal_size((120, 30)).columns
    width = max(20, min(len(df), terminal_width - 14))
    height = 18
    chunk_size = max(1, len(df) // width)
    num_buckets = max(1, len(df) // chunk_size)

    bucket_highs = []
    bucket_lows = []
    bucket_closes = []
    bucket_vwaps = []
    bucket_states = []
    bucket_entries = []
    bucket_exits = []

    trades = None if trades is None or getattr(trades, "empty", True) else trades

    for i in range(num_buckets):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size if i < num_buckets - 1 else len(df)
        chunk = df.iloc[start_idx:end_idx]
        if chunk.empty:
            continue
        bucket_highs.append(chunk["high"].max())
        bucket_lows.append(chunk["low"].min())
        bucket_closes.append(chunk["close"].iloc[-1])
        bucket_vwaps.append(chunk["vwap"].iloc[-1] if overlay_vwap and "vwap" in chunk.columns else None)
        if states is not None and show_states:
            chunk_states = states.iloc[start_idx:end_idx]
            bucket_states.append(int(chunk_states.mode().iloc[0]) if not chunk_states.empty else 0)
        else:
            bucket_states.append(0)

        has_entry = False
        has_exit = False
        if trades is not None and show_trades:
            chunk_start = chunk.index[0]
            chunk_end = chunk.index[-1]
            for _, trade in trades.iterrows():
                entry_ts = trade.get("Entry Timestamp")
                exit_ts = trade.get("Exit Timestamp")
                if entry_ts is not None and chunk_start <= entry_ts <= chunk_end:
                    has_entry = True
                if exit_ts is not None and chunk_start <= exit_ts <= chunk_end:
                    has_exit = True
        bucket_entries.append(has_entry)
        bucket_exits.append(has_exit)

    if not bucket_highs:
        console.print("[red]No chart buckets generated.[/red]")
        return

    min_price = min(bucket_lows)
    max_price = max(bucket_highs)
    price_range = max(max_price - min_price, 1e-9)
    state_colors = [
        "on dark_green",
        "on dark_red",
        "on grey37",
        "on dark_blue",
        "on purple4",
        "on dark_cyan",
        "on dark_magenta",
    ]

    def in_band(value: float, low: float, high: float) -> bool:
        return low <= value <= high

    rows = []
    for r in range(height - 1, -1, -1):
        band_low = min_price + (r / height) * price_range
        band_high = min_price + ((r + 1) / height) * price_range
        row = Text()
        row.append(f"{band_low:8.2f} | ")
        for idx in range(len(bucket_highs)):
            h = bucket_highs[idx]
            l = bucket_lows[idx]
            c = bucket_closes[idx]
            state_id = bucket_states[idx]
            style = state_colors[state_id % len(state_colors)] if show_states else ""
            char = " "
            if in_band(h, band_low, band_high) or in_band(l, band_low, band_high) or (l <= band_low and h >= band_high):
                char = "│"
            if in_band(c, band_low, band_high):
                char = "─"
            vwap_value = bucket_vwaps[idx]
            if overlay_vwap and vwap_value is not None and in_band(vwap_value, band_low, band_high):
                char = "┄"
            if show_trades and bucket_entries[idx] and in_band(c, band_low, band_high):
                char = "▲"
                style = f"bold bright_green {style}".strip()
            elif show_trades and bucket_exits[idx] and in_band(c, band_low, band_high):
                char = "▼"
                style = f"bold bright_red {style}".strip()
            row.append(char, style=style)
        rows.append(row)

    console.print("[bold]Annotated HLC Chart[/bold]")
    for row in rows:
        console.print(row)
    legend = Text("Legend: ")
    if show_states:
        for state_id, label in labels.items():
            legend.append(f" [{state_id}] {label} ", style=state_colors[state_id % len(state_colors)])
            legend.append(" ")
    if show_trades:
        legend.append(" ▲ Entry ", style="bold bright_green")
        legend.append(" ")
        legend.append(" ▼ Exit ", style="bold bright_red")
    if overlay_vwap:
        legend.append(" ┄ VWAP ", style="cyan")
    console.print(legend)

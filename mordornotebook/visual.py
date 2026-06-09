"""Generated notebook cells for financial visual inspection."""

from __future__ import annotations


def pnl_code(object_name: str, column: str | None = None) -> str:
    selector = f"[{column!r}]" if column else ""
    return f"""# Mordor generated PnL inspection cell
import pandas as pd
import matplotlib.pyplot as plt

obj = {object_name}
series = obj{selector}
if isinstance(series, pd.DataFrame):
    numeric_cols = series.select_dtypes("number").columns
    if len(numeric_cols) == 0:
        raise ValueError("No numeric columns available to plot")
    series = series[numeric_cols[0]]

ax = series.dropna().plot(figsize=(12, 5), linewidth=1.5)
ax.set_title("PnL / equity curve: {object_name}{selector}")
ax.set_xlabel("Index")
ax.set_ylabel("Value")
ax.grid(True, alpha=0.25)
plt.tight_layout()
plt.show()
"""


def event_window_code(object_name: str, date: str, before: int = 5, after: int = 5, ticker: str | None = None) -> str:
    ticker_line = f"ticker = {ticker!r}" if ticker else "ticker = None"
    return f"""# Mordor generated event-window inspection cell
import pandas as pd

obj = {object_name}
event_date = pd.Timestamp({date!r})
before = {int(before)}
after = {int(after)}
{ticker_line}

data = obj
if isinstance(getattr(data, "index", None), pd.MultiIndex):
    index_names = list(data.index.names)
    date_level = next((name for name in index_names if name and "date" in str(name).lower()), index_names[0])
    dates = pd.to_datetime(data.index.get_level_values(date_level), errors="coerce")
    mask = (dates >= event_date - pd.Timedelta(days=before)) & (dates <= event_date + pd.Timedelta(days=after))
    if ticker is not None:
        ticker_level = next((name for name in index_names if name and "ticker" in str(name).lower()), None)
        if ticker_level is not None:
            mask = mask & (data.index.get_level_values(ticker_level).astype(str) == str(ticker))
    display(data.loc[mask].head(200))
else:
    idx = pd.to_datetime(data.index, errors="coerce")
    mask = (idx >= event_date - pd.Timedelta(days=before)) & (idx <= event_date + pd.Timedelta(days=after))
    display(data.loc[mask].head(200))
"""


def multiindex_slice_code(object_name: str, date: str | None = None, ticker: str | None = None) -> str:
    return f"""# Mordor generated MultiIndex slice inspection cell
import pandas as pd

obj = {object_name}
date_value = {date!r}
ticker_value = {ticker!r}

if not isinstance(getattr(obj, "index", None), pd.MultiIndex):
    raise TypeError("{object_name} does not have a MultiIndex")

index_names = list(obj.index.names)
mask = pd.Series(True, index=obj.index)

if date_value is not None:
    date_level = next((name for name in index_names if name and "date" in str(name).lower()), index_names[0])
    dates = pd.to_datetime(obj.index.get_level_values(date_level), errors="coerce")
    mask &= dates == pd.Timestamp(date_value)

if ticker_value is not None:
    ticker_level = next((name for name in index_names if name and "ticker" in str(name).lower()), None)
    if ticker_level is None:
        ticker_level = index_names[1] if len(index_names) > 1 else index_names[0]
    mask &= obj.index.get_level_values(ticker_level).astype(str) == str(ticker_value)

display(obj.loc[mask.to_numpy()].head(200))
"""

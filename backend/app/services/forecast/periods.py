"""Calendar helpers for monthly series."""
from __future__ import annotations

from datetime import date

import pandas as pd


def advance_month(ts: pd.Timestamp, delta: int) -> pd.Timestamp:
    m = ts.month + delta
    y = ts.year
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return pd.Timestamp(year=y, month=m, day=1)


def next_period_str(last: pd.Timestamp, offset: int) -> str:
    m = last.month + offset
    y = last.year
    while m > 12:
        m -= 12
        y += 1
    return f"{y}-{m:02d}"


def first_forecast_period_from_today() -> pd.Timestamp:
    today = date.today()
    y = today.year
    m = today.month + 1
    if m > 12:
        m -= 12
        y += 1
    return pd.Timestamp(year=y, month=m, day=1)


def period_to_str(ts: pd.Timestamp) -> str:
    return f"{ts.year}-{ts.month:02d}"

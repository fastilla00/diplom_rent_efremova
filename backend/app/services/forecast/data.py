"""Load monthly metrics into a DataFrame."""
from __future__ import annotations

from collections.abc import Sequence
import pandas as pd
from app.models.metric import Metric

from app.services.forecast.constants import WINSORIZE_HIGH, WINSORIZE_LOW


def metric_df(rows: Sequence[Metric]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    data = []
    for r in rows:
        pct = None
        if r.revenue and r.costs is not None and r.revenue > 0:
            pct = float((r.revenue - r.costs) / r.revenue * 100)
        elif r.profitability_pct is not None:
            pct = float(r.profitability_pct)
        if pct is None:
            continue
        rev = float(r.revenue or 0)
        cost = float(r.costs or 0)
        data.append({"year": r.year, "month": r.month, "revenue": rev, "costs": cost, "profitability": pct})
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["period"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
    df = df.sort_values("period").reset_index(drop=True)
    if len(df) >= 4:
        lo = df["profitability"].quantile(WINSORIZE_LOW)
        hi = df["profitability"].quantile(WINSORIZE_HIGH)
        df["profitability"] = df["profitability"].clip(lo, hi)
    return df

# src/forecasting.py
"""
Forecasting helpers for financial-forecasting-engine.

Functions:
- compute_cagr(series_or_first_last, periods)
- project_revenue(last_value, base_growth, years)
- project_margin(base_margin, delta)
- build_forecast(last_revenue, growth, ebitda_margin, capex_pct, dep_pct, wc_pct, tax_rate, years)
- build_scenario_from_base(base_last_rev, base_growth, base_margin, growth_mul, margin_delta, capex_mul, dep_pct, wc_pct, tax_rate, years)
"""

from typing import Iterable
import pandas as pd


def compute_cagr(values: Iterable[float], periods: int) -> float:
    """Compute CAGR given an iterable of values from oldest -> newest and number of periods.
    If `values` is a pandas Series, it can be used directly."""
    vals = list(values)
    if len(vals) < 2:
        raise ValueError("need at least two values to compute CAGR")
    start = float(vals[0])
    end = float(vals[-1])
    if start <= 0:
        raise ValueError("start value must be > 0 for CAGR")
    return (end / start) ** (1.0 / periods) - 1.0


def project_revenue(last_value: float, growth_rate: float, years: int) -> pd.Series:
    """Project revenue given last known value, constant growth rate and number of years.
    Returns a pandas Series indexed 1..years (you can reindex later to actual years)."""
    arr = [last_value * (1 + growth_rate) ** i for i in range(1, years + 1)]
    return pd.Series(arr)


def project_margin(base_margin: float, delta: float = 0.0) -> float:
    """Return adjusted margin (simple)."""
    return base_margin + delta


def build_forecast(
    last_revenue: float,
    growth: float,
    ebitda_margin: float,
    capex_pct: float,
    dep_pct: float,
    wc_pct: float,
    tax_rate: float,
    years: int,
    start_year: int = None,
) -> pd.DataFrame:
    """Build a deterministic forecast table for `years` years.
    Returns DataFrame indexed by year numbers (if start_year provided uses actual years)."""
    rev = project_revenue(last_revenue, growth, years)
    ebitda = rev * ebitda_margin
    dep = rev * dep_pct
    ebit = ebitda - dep
    nopat = ebit * (1 - tax_rate)
    capex = rev * capex_pct
    wc = rev * wc_pct
    fcff = nopat + dep - capex - wc

    df = pd.DataFrame(
        {
            "Revenue": rev,
            "EBITDA": ebitda,
            "Depreciation": dep,
            "EBIT": ebit,
            "NOPAT": nopat,
            "Capex": capex,
            "ΔWorkingCapital": wc,
            "FCFF": fcff,
        }
    )

    if start_year is not None:
        years_index = [start_year + i for i in range(1, years + 1)]
        df.index = years_index
    return df


def build_scenario_from_base(
    last_revenue: float,
    base_growth: float,
    base_margin: float,
    growth_mul: float,
    margin_delta: float,
    capex_mul: float,
    dep_pct: float,
    wc_pct: float,
    tax_rate: float,
    years: int,
    start_year: int = None,
) -> pd.DataFrame:
    """Helper to build a scenario from base parameters with multipliers/deltas."""
    g = base_growth * growth_mul
    m = base_margin + margin_delta
    df = build_forecast(
        last_revenue,
        g,
        m,
        capex_pct=capex_mul * 0.06,  # default fallback if you don't have base capex_pct; override if needed
        dep_pct=dep_pct,
        wc_pct=wc_pct,
        tax_rate=tax_rate,
        years=years,
        start_year=start_year,
    )
    return df

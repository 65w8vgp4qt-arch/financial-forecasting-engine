# src/valuation.py
import numpy as np
import pandas as pd
from typing import Iterable, Tuple

def calc_free_cash_flow(forecast_df: pd.DataFrame) -> pd.Series:
    """Accepts a forecast DataFrame (as built by build_forecast) and returns FCFF series (index = Year)."""
    if "FCFF" not in forecast_df.columns:
        raise ValueError("forecast_df must contain 'FCFF' column")
    return pd.to_numeric(forecast_df["FCFF"], errors="coerce")

def wacc_calc(
    beta: float,
    rf: float,
    rm: float,
    market_debt: float,
    market_equity: float,
    cost_of_debt: float = None,
    tax_rate: float = 0.21
) -> float:
    """
    Basic WACC calculator.
    - Cost of equity via CAPM: re = rf + beta*(rm-rf)
    - cost_of_debt: if None, assume 0.035 (3.5%)
    - market_debt, market_equity are market values (not percentages)
    Returns WACC (decimal).
    """
    re = rf + beta * (rm - rf)
    if cost_of_debt is None:
        cost_of_debt = 0.035
    total = market_debt + market_equity
    if total <= 0:
        raise ValueError("market_debt + market_equity must be > 0")
    wd = market_debt / total
    we = market_equity / total
    wacc = we * re + wd * cost_of_debt * (1 - tax_rate)
    return float(wacc)

def discount_cash_flows(fcfs: Iterable[float], wacc: float) -> Tuple[float, np.ndarray]:
    """
    Discount an iterable of FCFF for years 1..n at constant WACC.
    Returns (pv_sum, discount_factors_array)
    """
    fcfs_arr = np.asarray(list(fcfs), dtype=float)
    n = fcfs_arr.shape[0]
    # discount factors for year i: (1+wacc)**i for i=1..n
    discount_factors = (1.0 + wacc) ** np.arange(1, n + 1)
    pv = np.sum(fcfs_arr / discount_factors)
    return float(pv), discount_factors

def terminal_value_gordon(fcff_last: float, wacc: float, g: float) -> float:
    """
    Gordon growth terminal value = FCFF_last * (1+g) / (wacc - g)
    wacc must be > g
    """
    if wacc <= g:
        raise ValueError("WACC must be greater than terminal growth g")
    return float((fcff_last * (1 + g)) / (wacc - g))

def compute_dcf_value(
    forecast_df: pd.DataFrame,
    wacc: float,
    terminal_g: float
) -> float:
    """
    Computes enterprise value using FCFF in forecast_df and terminal value.
    Assumes forecast_df index or 'Year' column is sequential for projection years
    Returns enterprise_value (PV of FCFF + PV terminal)
    """
    fcfs = calc_free_cash_flow(forecast_df).values
    pv_fcfs, discount_factors = discount_cash_flows(fcfs, wacc)
    # last year's FCFF (most recent forecast year)
    fcff_last = float(fcfs[-1])
    tv = terminal_value_gordon(fcff_last, wacc, terminal_g)
    # PV of TV discounted by (1+wacc)**n where n = len(fcfs)
    n = len(fcfs)
    pv_tv = tv / ((1.0 + wacc) ** n)
    enterprise_value = pv_fcfs + pv_tv
    return float(enterprise_value)
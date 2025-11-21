# src/simulation.py

import numpy as np
import pandas as pd
from typing import Dict
from src.valuation import compute_dcf_value
from src.forecasting import build_forecast

def run_mc_simulation(
    n_sims: int,
    base_inputs: Dict[str, float],
    sigma_inputs: Dict[str, float],
    years: int = 5,
    start_year: int = None,
    wacc_base: float = 0.075,        # Updated with ASML WACC
    wacc_sigma: float = 0.015,
    terminal_g_base: float = 0.025,  # Updated with realistic ASML LTG
    terminal_g_sigma: float = 0.005,
    verbose: bool = False
) -> np.ndarray:
    """
    Monte Carlo simulation for enterprise value.
    base_inputs must include:
        last_revenue, growth, ebitda_margin, capex_pct,
        dep_pct, wc_pct, tax_rate
    sigma_inputs must include stdev for each input.
    """

    vals = np.zeros(n_sims)
    rng = np.random.default_rng()

    for i in range(n_sims):

        # ---- Sample operational assumptions ----
        growth = rng.normal(base_inputs["growth"], sigma_inputs.get("growth", 0))

        ebitda_margin = rng.normal(
            base_inputs["ebitda_margin"],
            sigma_inputs.get("ebitda_margin", 0)
        )
        capex_pct = rng.normal(
            base_inputs["capex_pct"],
            sigma_inputs.get("capex_pct", 0)
        )
        dep_pct = rng.normal(
            base_inputs["dep_pct"],
            sigma_inputs.get("dep_pct", 0)
        )
        wc_pct = rng.normal(
            base_inputs["wc_pct"],
            sigma_inputs.get("wc_pct", 0)
        )
        tax_rate = rng.normal(
            base_inputs["tax_rate"],
            sigma_inputs.get("tax_rate", 0)
        )

        # ---- Sample discounting assumptions ----
        wacc = max(0.001, rng.normal(wacc_base, wacc_sigma))
        terminal_g = rng.normal(terminal_g_base, terminal_g_sigma)

        # ---- Safety limits ----
        ebitda_margin = max(-0.5, ebitda_margin)
        capex_pct = max(0.0, capex_pct)
        dep_pct = max(0.0, dep_pct)
        wc_pct = max(0.0, wc_pct)
        tax_rate = min(max(0.0, tax_rate), 1.0)

        # ---- Build forecast ----
        forecast_df = build_forecast(
            last_revenue=base_inputs["last_revenue"],
            growth=growth,
            ebitda_margin=ebitda_margin,
            capex_pct=capex_pct,
            dep_pct=dep_pct,
            wc_pct=wc_pct,
            tax_rate=tax_rate,
            years=years,
            start_year=start_year
        )

        # ---- Compute intrinsic value ----
        try:
            ev = compute_dcf_value(forecast_df, wacc=wacc, terminal_g=terminal_g)
        except Exception:
            ev = np.nan

        vals[i] = ev

        if verbose and i % 1000 == 0:
            print(f"[MC] Completed {i} simulations")

    return vals
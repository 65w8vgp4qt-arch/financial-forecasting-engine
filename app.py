# app.py (precomputed-only Streamlit app)
"""
Streamlit demo (precomputed-only)
Loads canonical Monte Carlo outputs and forecast CSVs.
No live Monte Carlo runs included.
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from datetime import datetime
import json

from src.forecasting import build_forecast  # used for building deterministic scenarios if CSV missing

st.set_page_config(page_title="Valuation Engine (precomputed)", layout="wide", initial_sidebar_state="expanded")

# ---- Sidebar: Inputs (display only / user values for per-share calc) ----
st.sidebar.header("Display controls")
ticker = st.sidebar.text_input("Ticker (info only)", value="ASML.AS")
start_year = st.sidebar.number_input("Start year (last reported)", value=2024, step=1)
horizon = st.sidebar.slider("Forecast horizon (years) — display only", min_value=3, max_value=10, value=5)

st.sidebar.subheader("Shares / Market (for per-share conversion)")
# expect shares in UNITS (not millions)
shares_outstanding = st.sidebar.number_input("Shares outstanding (units)", value=388150000.0, step=1.0, format="%.1f")
# ---- live market price helper ----
import yfinance as yf

market_price_override = st.sidebar.number_input(
    "Market price per share (manual override)", 
    value=0.0, format="%.5f"
)
use_live_price = st.sidebar.checkbox("Fetch live price (yfinance)", value=True)

@st.cache_data(ttl=300)
def fetch_live_price(ticker_symbol: str):
    t = yf.Ticker(ticker_symbol)
    h = t.history(period="2d")
    return float(h["Close"].dropna().iloc[-1])

st.sidebar.markdown("---")
st.sidebar.markdown("This app **only loads precomputed** Monte Carlo results. To regenerate MC, run the provided notebook/script.")

# ---- Helpers ----
# ----------------- REPLACE THESE FUNCTIONS IN app.py -----------------

def load_forecast_csvs(forecasts_dir="outputs/forecasts"):
    """Load base/bull/bear CSVs if present, else return None for each."""
    out = {}
    mapping = {"Base": "base_case.csv", "Bull": "bull_case.csv", "Bear": "bear_case.csv"}
    for name, fname in mapping.items():
        path = os.path.join(forecasts_dir, fname)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, index_col=0)
                # try make index numeric years if possible
                try:
                    df.index = df.index.map(int)
                except Exception:
                    pass
                out[name] = df
            except Exception as e:
                st.warning(f"Could not read {path}: {e}")
                out[name] = None
        else:
            out[name] = None
    return out

def display_forecast_tables(forecasts):
    col1, col2 = st.columns([1,1])
    with col1:
        st.subheader("Forecast table (Base)")
        if forecasts.get("Base") is not None:
            st.dataframe(forecasts["Base"].round(0))
        else:
            st.info("Base forecast CSV missing. Use notebook to generate outputs/forecasts/base_case.csv")
    with col2:
        st.subheader("Forecast table (Bull)")
        if forecasts.get("Bull") is not None:
            st.dataframe(forecasts["Bull"].round(0))
        else:
            st.info("Bull forecast CSV missing. Use notebook to generate outputs/forecasts/bull_case.csv")

def plot_forecasts(forecasts):
    # defensive: only plot if at least one non-None dataframe exists
    if not any(v is not None for v in forecasts.values()):
        st.info("No forecast CSVs to plot.")
        return
    plt.figure(figsize=(9,4))
    for name, df in forecasts.items():
        if df is None:
            continue
        if "Revenue" in df.columns:
            x = df.index
            plt.plot(x, df["Revenue"], label=f"{name} Revenue")
    plt.title("Revenue Forecast (from CSVs)")
    plt.xlabel("Year")
    plt.ylabel("Revenue")
    plt.legend()
    st.pyplot(plt.gcf())
    plt.close()

def plot_fcff(forecasts):
    # defensive: only plot if at least one non-None dataframe has FCFF
    if not any((df is not None and "FCFF" in df.columns) for df in forecasts.values()):
        # nothing to plot
        return
    plt.figure(figsize=(9,4))
    for name, df in forecasts.items():
        if df is None:
            continue
        if "FCFF" in df.columns:
            plt.plot(df.index, df["FCFF"], label=f"{name} FCFF")
    plt.title("FCFF (from CSVs)")
    plt.xlabel("Year")
    plt.ylabel("FCFF")
    plt.legend()
    st.pyplot(plt.gcf())
    plt.close()
    
def load_canonical_mc(out_dir="outputs/mc"):
    """Return ev_eur array (np.ndarray) and metadata dict (if available)."""
    ev_path = os.path.join(out_dir, "mc_values_live_eur.npy")
    metrics_csv = os.path.join(out_dir, "mc_last_run.csv")
    metrics_json = os.path.join(out_dir, "mc_metrics.json")
    if not os.path.exists(ev_path):
        return None, None
    ev_eur = np.load(ev_path)
    meta = None
    if os.path.exists(metrics_csv):
        try:
            meta = pd.read_csv(metrics_csv).to_dict(orient="records")[0]
        except Exception:
            meta = None
    elif os.path.exists(metrics_json):
        try:
            meta = json.load(open(metrics_json))
        except Exception:
            meta = None
    return ev_eur, meta

def compute_and_display_mc(ev_eur, shares_units, market_price, clip_pct=99):
    """Compute KPIs from ev_eur (full EUR) and display them + clipped histogram."""
    clean = ev_eur[~np.isnan(ev_eur)]
    if clean.size == 0:
        st.error("MC file contains no valid values.")
        return None

    qs = np.percentile(clean, [5,25,50,75,95])
    ev_median = float(qs[2])
    ev_mean = float(clean.mean())
    ev_5 = float(qs[0])
    ev_95 = float(qs[4])

    # per-share
    ps_array = clean / float(shares_units)
    median_ps = float(np.percentile(ps_array,50))
    mean_ps = float(np.nanmean(ps_array))
    prob_above = float(np.nanmean((ps_array > market_price).astype(float))) if market_price is not None else None

    # CVaR 5% on EV
    k = max(1, int(0.05 * len(clean)))
    cvar5 = float(np.sort(clean)[:k].mean())

    # KPI row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Median per-share (EUR)", f"€{median_ps:,.2f}")
    k2.metric("Median EV (EUR)", f"€{ev_median/1e9:,.2f}B")
    k3.metric("Prob(intrinsic > market)", f"{(prob_above*100):.2f}%" if prob_above is not None else "N/A")
    k4.metric("CVaR (5% EV)", f"€{cvar5/1e9:,.2f}B")

    # debug small numbers
    st.write(f"Debug: median_ev_eur={ev_median:.0f}, median_per_share={median_ps:.4f}, market_price={market_price}")

    # plot clipped per-share histogram
    clip_val = np.percentile(ps_array, clip_pct)
    plot_data = np.minimum(ps_array, clip_val)

    fig, ax = plt.subplots(figsize=(10,5))
    ax.hist(plot_data, bins=80)
    ax.axvline(median_ps, color="C1", linestyle="--", label=f"Median €{median_ps:,.2f}")
    if market_price is not None:
        ax.axvline(market_price, color="C3", linestyle="-.", label=f"Market €{market_price:.2f}")
    ax.set_title(f"Intrinsic value per share (clipped at {clip_pct}th pct)")
    ax.set_xlabel("EUR / share")
    ax.set_ylabel("Frequency")
    ax.legend()
    st.pyplot(fig)
    plt.close(fig)

    # return metrics dict
    return {
        "ev_median": ev_median,
        "ev_mean": ev_mean,
        "median_ps": median_ps,
        "prob_above": prob_above,
        "ev_5": ev_5,
        "ev_95": ev_95,
        "cvar5": cvar5
    }

# ---- Page content ----
st.title("Corporate Financial Forecasting & Valuation — (Precomputed-only)")

st.markdown(
    """
    This app loads **precomputed** Monte Carlo outputs from `outputs/mc/mc_values_live_eur.npy` (EV in full EUR)
    and forecast CSVs from `outputs/forecasts/`.  
    No live Monte Carlo runs are allowed here — regenerate MC only via the notebook or scripts.
    """
)

# Forecasts
st.header("Forecasts")
forecasts = load_forecast_csvs()
display_forecast_tables(forecasts)
st.subheader("Scenario charts")
plot_forecasts(forecasts)
plot_fcff(forecasts)

# Monte Carlo
st.header("Monte Carlo results (precomputed)")
ev_eur, meta = load_canonical_mc()
if ev_eur is None:
    st.error("Canonical MC file not found: outputs/mc/mc_values_live_eur.npy\n\nRun the notebook/script to regenerate canonical MC outputs.")
else:
    try:
        if market_price_override > 0:
            market_price_used = float(market_price_override)
            market_price_source = "manual override"
        elif use_live_price:
            market_price_used = fetch_live_price(ticker)
            market_price_source = "live yfinance"
        else:
            market_price_used = 0.0
            market_price_source = "fallback"
    except Exception:
        market_price_used = float(market_price_override) if market_price_override is not None else 0.0
        market_price_source = "fallback/manual"

    metrics = compute_and_display_mc(ev_eur, shares_outstanding, market_price_used, clip_pct=99)

    st.write(f"Market price used: **€{market_price_used:,.2f}**  _(source: {market_price_source})_")
    if meta is not None:
        with st.expander("Show last run metadata (mc_last_run.csv / mc_metrics.json)"):
            st.json(meta)

# Download buttons and housekeeping
st.markdown("---")
st.write("Files used:")
colA, colB = st.columns(2)
with colA:
    st.write("- Forecast CSVs from `outputs/forecasts/`")
    st.write("- Canonical MC EV: `outputs/mc/mc_values_live_eur.npy`")
with colB:
    download_ev = st.button("Download EV (EUR) .npy")
    if download_ev:
        st.write("To download, open the project folder in Finder/Explorer and copy `outputs/mc/mc_values_live_eur.npy`.")
st.markdown("**Note:** regenerate MC via `notebooks/model_dev.ipynb` or `scripts/regenerate_mc.py` (not this app).")

st.sidebar.markdown("---")
st.sidebar.info("Precomputed-only app. To refresh results run the regeneration notebook/script.")
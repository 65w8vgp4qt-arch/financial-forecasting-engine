import os, json, numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

project_root = os.path.abspath(".")
out_reports = os.path.join(project_root, "outputs", "reports")
os.makedirs(out_reports, exist_ok=True)

base_csv = os.path.join(project_root, "outputs", "forecasts", "base_case.csv")
bull_csv = os.path.join(project_root, "outputs", "forecasts", "bull_case.csv")
bear_csv = os.path.join(project_root, "outputs", "forecasts", "bear_case.csv")
mc_np = os.path.join(project_root, "outputs", "mc", "mc_values_live_eur.npy")

base_df = pd.read_csv(base_csv, index_col=0) if os.path.exists(base_csv) else None
bull_df = pd.read_csv(bull_csv, index_col=0) if os.path.exists(bull_csv) else None
bear_df = pd.read_csv(bear_csv, index_col=0) if os.path.exists(bear_csv) else None

if os.path.exists(mc_np):
    ev_eur = np.load(mc_np)
    ev_clean = ev_eur[~np.isnan(ev_eur)]
else:
    ev_clean = np.array([])

def plot_forecast_table(df, title, fname):
    if df is None:
        return
    fig, ax = plt.subplots(figsize=(10, 2.2))
    ax.axis('off')
    display_df = df.copy().round(0)
    table = ax.table(
        cellText=display_df.T.values,
        rowLabels=display_df.columns,
        colLabels=display_df.index.astype(str),
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    plt.title(title, fontsize=10)
    plt.savefig(fname, bbox_inches='tight', dpi=150)
    plt.close(fig)

plot_forecast_table(base_df, "Forecast – Base case", os.path.join(out_reports, "forecast_table_base.png"))

def plot_scenario_lines(dfs, series, fname):
    fig, ax = plt.subplots(figsize=(9, 4))
    for name, df in dfs.items():
        if df is not None and series in df.columns:
            ax.plot(df.index.astype(int), df[series], marker='o', label=name)
    ax.set_title(f"{series} – Scenarios")
    ax.set_xlabel("Year")
    ax.set_ylabel(series)
    ax.legend()
    fig.savefig(fname, bbox_inches='tight', dpi=150)
    plt.close(fig)

plot_scenario_lines(
    {"Base": base_df, "Bull": bull_df, "Bear": bear_df},
    "Revenue",
    os.path.join(out_reports, "scenario_revenue.png")
)

plot_scenario_lines(
    {"Base": base_df, "Bull": bull_df, "Bear": bear_df},
    "FCFF",
    os.path.join(out_reports, "scenario_fcff.png")
)

shares_units = 388_150_000
market_price = 869  # fallback

if ev_clean.size > 0:
    ps_array = ev_clean / shares_units
    median_ps = np.percentile(ps_array, 50)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(ps_array, bins=100, alpha=0.9)
    ax.axvline(median_ps, color="red", linestyle="--", label=f"Median €{median_ps:,.2f}")
    ax.axvline(market_price, color="green", linestyle="-.", label=f"Market €{market_price:.2f}")
    ax.legend()
    ax.set_title("Monte Carlo intrinsic value (EUR/share)")
    fig.savefig(os.path.join(out_reports, "mc_hist_ps.png"), bbox_inches='tight', dpi=150)
    plt.close(fig)

pdf_path = os.path.join(out_reports, "report.pdf")
with PdfPages(pdf_path) as pdf:
    fig = plt.figure(figsize=(11.7, 8.3))
    fig.text(0.05, 0.92, "Valuation Executive Summary", fontsize=16, weight='bold')

    if ev_clean.size > 0:
        median_ev = np.percentile(ev_clean, 50)
        prob_above = (ev_clean / shares_units > market_price).mean()
        kpi_text = f"Median EV: €{median_ev:,.0f}\nMedian per-share: €{median_ps:,.2f}\nProb > market: {prob_above*100:.2f}%"
    else:
        kpi_text = "No MC results found"

    fig.text(0.05, 0.82, kpi_text, fontsize=10)

    img1 = plt.imread(os.path.join(out_reports, "forecast_table_base.png"))
    img2 = plt.imread(os.path.join(out_reports, "mc_hist_ps.png"))
    img3 = plt.imread(os.path.join(out_reports, "scenario_fcff.png"))

    ax1 = fig.add_axes([0.05, 0.35, 0.55, 0.45]); ax1.imshow(img1); ax1.axis('off')
    ax2 = fig.add_axes([0.62, 0.5, 0.35, 0.4]); ax2.imshow(img2); ax2.axis('off')
    ax3 = fig.add_axes([0.62, 0.05, 0.35, 0.35]); ax3.imshow(img3); ax3.axis('off')

    fig.text(0.05, 0.02, "Insights:", fontsize=10, weight='bold')
    fig.text(0.15, 0.02,
             "1. Median intrinsic relative to market.\n"
             "2. Scenario spread driven by margins & terminal growth.\n"
             "3. Tail-risk visible in CVaR calculations.",
             fontsize=9)

    pdf.savefig(fig)
    plt.close(fig)

print("DONE — PDF saved to:", pdf_path)

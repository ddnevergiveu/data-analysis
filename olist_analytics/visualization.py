"""Headless charts with portable fonts and no import-time GUI dependency."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _save(figure, path):
    figure.tight_layout()
    if path is not None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(figure)
    return path


def plot_category_sales(category_stats, save_path=None):
    column = "merchandise_value" if "merchandise_value" in category_stats else "total_sales"
    top = category_stats.sort_values(column).tail(10)
    figure, axis = plt.subplots(figsize=(9, 5))
    axis.barh(top.index.astype(str), top[column], color="#246f78")
    axis.set(title="Top product categories", xlabel="Delivered merchandise value (BRL)")
    return _save(figure, save_path)


def plot_monthly_sales(monthly_sales, save_path=None):
    if isinstance(monthly_sales, pd.Series):
        values = monthly_sales
    elif "merchandise_value" in monthly_sales:
        values = monthly_sales["merchandise_value"]
    else:
        periods = pd.to_datetime(monthly_sales["order_purchase_timestamp"]).dt.to_period("M")
        values = monthly_sales.groupby(periods)["total_amount"].sum()
    figure, axis = plt.subplots(figsize=(10, 4))
    axis.plot(values.index.astype(str), values.values, marker="o", color="#246f78")
    axis.tick_params(axis="x", rotation=40)
    axis.set(title="Monthly sales (final month may be partial)", ylabel="Merchandise value (BRL)")
    return _save(figure, save_path)


def plot_state_heatmap(state_sales, save_path=None):
    """Legacy name retained: the output is accurately labeled a bar chart."""
    if not isinstance(state_sales, pd.Series):
        state_sales = state_sales.groupby("customer_state")["total_amount"].sum()
    figure, axis = plt.subplots(figsize=(9, 4))
    values = state_sales.sort_values(ascending=False)
    axis.bar(values.index.astype(str), values.values, color="#b17841")
    axis.set(title="Sales by state", ylabel="Merchandise value (BRL)")
    return _save(figure, save_path)


def plot_retention(rates, save_path):
    figure, axis = plt.subplots(figsize=(10, max(3, min(len(rates) * 0.45, 14))))
    if rates.empty:
        axis.text(0.5, 0.5, "No complete calendar months in the observation window", ha="center", va="center")
        axis.axis("off")
    else:
        values = np.ma.masked_invalid(rates.to_numpy(dtype=float))
        cmap = plt.get_cmap("YlGnBu").copy()
        cmap.set_bad("#eeeeee")
        plotted = axis.imshow(values, aspect="auto", vmin=0, vmax=1, cmap=cmap)
        axis.set_yticks(range(len(rates)), rates.index.astype(str))
        axis.set_xticks(range(len(rates.columns)), rates.columns.astype(str))
        axis.set(title="Monthly purchase retention (complete months only)", xlabel="Months since first observed purchase", ylabel="Cohort")
        figure.colorbar(plotted, ax=axis, label="Share of original cohort")
    return _save(figure, save_path)

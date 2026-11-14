"""Metrics with explicit item, order and persistent-customer grains."""

import numpy as np
import pandas as pd

from .data import require_columns


def order_summary(items):
    require_columns(items, ["order_id", "customer_unique_id", "order_purchase_timestamp", "total_amount", "freight_value"], "items")
    return items.groupby("order_id", as_index=False).agg(
        customer_unique_id=("customer_unique_id", "first"),
        order_purchase_timestamp=("order_purchase_timestamp", "first"),
        merchandise_value=("total_amount", "sum"),
        freight_value=("freight_value", "sum"),
        item_count=("order_id", "size"),
    )


def repeat_rate(items):
    counts = items.groupby("customer_unique_id")["order_id"].nunique()
    return float(counts.gt(1).mean()) if len(counts) else 0.0


def top_customers(items, percentile=90):
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    sales = items.groupby("customer_unique_id")["total_amount"].sum()
    if sales.empty:
        return sales
    return sales[sales >= np.percentile(sales, percentile)].sort_values(ascending=False)


def customer_lifetime_analysis(items):
    result = items.groupby("customer_unique_id")["order_purchase_timestamp"].agg(["min", "max"])
    result["observed_span_days"] = (result["max"] - result["min"]).dt.days
    return result


def sales_summary(items):
    orders = order_summary(items)
    values = orders["merchandise_value"]
    return {
        "orders": len(orders),
        "customers": int(orders["customer_unique_id"].nunique()),
        "item_rows": len(items),
        "merchandise_value": float(values.sum()),
        "freight_value": float(orders["freight_value"].sum()),
        "average_order_value": float(values.mean()) if len(orders) else 0.0,
        "median_order_value": float(values.median()) if len(orders) else 0.0,
        "repeat_customer_rate": repeat_rate(items),
    }


def sales_tables(items):
    category = items.groupby("product_category_name").agg(
        item_count=("order_item_id", "size"),
        order_count=("order_id", "nunique"),
        merchandise_value=("total_amount", "sum"),
    ).sort_values("merchandise_value", ascending=False)
    monthly = items.groupby("month").agg(
        orders=("order_id", "nunique"), merchandise_value=("total_amount", "sum")
    )
    state = items.groupby("customer_state")["total_amount"].sum().sort_values(ascending=False)
    state.name = "merchandise_value"
    return category, monthly, state

"""Compatibility helpers with corrected item-price semantics."""

import numpy as np
import pandas as pd


def add_total_amount(frame):
    result = frame.copy()
    price = pd.to_numeric(result["price"], errors="coerce")
    if not np.isfinite(price.to_numpy(dtype=float)).all() or (price < 0).any():
        raise ValueError("price must contain finite nonnegative values")
    result["total_amount"] = price
    return result


def add_month_feature(frame):
    result = frame.copy()
    result["month"] = pd.to_datetime(result["order_purchase_timestamp"], errors="raise").dt.to_period("M")
    return result

"""Load and validate the four Olist tables before computing any metrics."""

from pathlib import Path

import numpy as np
import pandas as pd


FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
}
SCHEMA = {
    "orders": ["order_id", "customer_id", "order_status", "order_purchase_timestamp"],
    "customers": ["customer_id", "customer_unique_id", "customer_state"],
    "items": ["order_id", "order_item_id", "product_id", "price", "freight_value"],
    "products": ["product_id", "product_category_name"],
}


def require_columns(frame, columns, name):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing required columns: {', '.join(missing)}")


def _keys(frame, columns, name):
    for column in columns:
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"{name}: {column} contains missing or blank keys")


def _unique(frame, keys, name):
    frame = frame.drop_duplicates().copy()
    if frame.duplicated(keys).any():
        raise ValueError(f"{name}: conflicting duplicate keys {keys}")
    return frame


def clean_orders(orders):
    require_columns(orders, SCHEMA["orders"], "orders")
    orders = orders.copy()
    _keys(orders, ["order_id", "customer_id", "order_status"], "orders")
    orders = _unique(orders, ["order_id"], "orders")
    try:
        orders["order_purchase_timestamp"] = pd.to_datetime(
            orders["order_purchase_timestamp"], errors="coerce", format="ISO8601"
        )
    except (TypeError, ValueError) as error:
        raise ValueError("orders: use consistent timezone-naive ISO timestamps") from error
    if orders["order_purchase_timestamp"].isna().any():
        raise ValueError("orders: invalid or missing order_purchase_timestamp")
    timestamp_dtype = orders["order_purchase_timestamp"].dtype
    if isinstance(timestamp_dtype, pd.DatetimeTZDtype) or not pd.api.types.is_datetime64_dtype(timestamp_dtype):
        raise ValueError("orders: use timezone-naive Olist local timestamps consistently")
    return orders


def load_tables(data_dir):
    root = Path(data_dir)
    missing = [filename for filename in FILES.values() if not (root / filename).is_file()]
    if missing:
        raise ValueError(
            f"Missing CSV files in {root}: {', '.join(missing)}. "
            "Download the Olist tables or run with --demo."
        )
    # Explicit identifiers preserve leading zeroes in user-provided extracts.
    ids = {"order_id": "string", "customer_id": "string", "customer_unique_id": "string", "product_id": "string"}
    return {name: pd.read_csv(root / filename, dtype=ids) for name, filename in FILES.items()}


def prepare_data(tables, as_of=None):
    """Return delivered item rows, quality counts and an exclusive observation end.

    Exact duplicate rows are removed; conflicting keys and invalid amounts fail.
    Only the four declared schemas are joined, preventing accidental column clashes.
    """
    cleaned = {}
    quality = {"input_rows": {}, "exact_duplicates_removed": {}}
    for name, required in SCHEMA.items():
        if name not in tables:
            raise ValueError(f"Missing table: {name}")
        source = tables[name]
        require_columns(source, required, name)
        quality["input_rows"][name] = len(source)
        frame = source[required].copy()
        before = len(frame)
        if name == "orders":
            frame = clean_orders(frame)
        elif name == "customers":
            _keys(frame, ["customer_id", "customer_unique_id"], name)
            frame = _unique(frame, ["customer_id"], name)
            frame["customer_state"] = frame["customer_state"].fillna("unknown")
        elif name == "products":
            _keys(frame, ["product_id"], name)
            frame = _unique(frame, ["product_id"], name)
            frame["product_category_name"] = frame["product_category_name"].fillna("unknown")
        else:
            _keys(frame, ["order_id", "product_id", "order_item_id"], name)
            for column in ["order_item_id", "price", "freight_value"]:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
                if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
                    raise ValueError(f"items: {column} must contain finite numbers")
            if (frame[["price", "freight_value"]] < 0).any().any():
                raise ValueError("items: price and freight_value cannot be negative")
            sequence = frame["order_item_id"]
            if ((sequence <= 0) | (sequence % 1 != 0)).any():
                raise ValueError("items: order_item_id must be a positive integer sequence")
            frame = _unique(frame, ["order_id", "order_item_id"], name)
        quality["exact_duplicates_removed"][name] = before - len(frame)
        cleaned[name] = frame

    orders, items = cleaned["orders"], cleaned["items"]
    if orders.empty:
        raise ValueError("orders: no orders supplied")
    for left, key, right in [(orders, "customer_id", cleaned["customers"]),
                             (items, "order_id", orders),
                             (items, "product_id", cleaned["products"])]:
        missing = ~left[key].isin(right[key])
        if missing.any():
            raise ValueError(f"Unmatched {key}: {int(missing.sum())} rows; check table coverage")

    try:
        observation_end = pd.Timestamp(as_of) if as_of is not None else (
            orders["order_purchase_timestamp"].max().normalize() + pd.Timedelta(days=1)
        )
    except (TypeError, ValueError) as error:
        raise ValueError("--as-of must be an ISO date or timestamp") from error
    if pd.isna(observation_end) or observation_end.tzinfo is not None:
        raise ValueError("--as-of must be a timezone-naive date or timestamp")
    eligible = orders[
        orders["order_status"].eq("delivered")
        & orders["order_purchase_timestamp"].lt(observation_end)
    ]
    quality["excluded_status_orders"] = int(orders["order_status"].ne("delivered").sum())
    quality["at_or_after_observation_end_orders"] = int(
        orders["order_purchase_timestamp"].ge(observation_end).sum()
    )
    quality["delivered_orders_without_items"] = int((~eligible["order_id"].isin(items["order_id"])).sum())
    if quality["delivered_orders_without_items"]:
        raise ValueError("Delivered orders lack item rows; sales and customer metrics would be incomplete")
    if eligible.empty:
        raise ValueError("No delivered orders before the observation end")
    merged = eligible.merge(items, on="order_id", validate="one_to_many")
    merged = merged.merge(cleaned["products"], on="product_id", validate="many_to_one")
    merged = merged.merge(cleaned["customers"], on="customer_id", validate="many_to_one")
    merged["total_amount"] = merged["price"]  # A line number is NOT a quantity.
    merged["month"] = merged["order_purchase_timestamp"].dt.to_period("M")
    quality["eligible_orders"] = int(eligible["order_id"].nunique())
    quality["eligible_item_rows"] = len(merged)
    quality["unknown_category_items"] = int(merged["product_category_name"].eq("unknown").sum())
    return merged, quality, observation_end


def merge_data(orders, order_items, products, customers):
    """Compatibility entry point; now validates and selects delivered orders."""
    return prepare_data({"orders": orders, "items": order_items, "products": products, "customers": customers})[0]

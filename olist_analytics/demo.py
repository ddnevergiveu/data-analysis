"""Small deterministic SYNTHETIC data; no Olist records or network calls."""

import numpy as np
import pandas as pd


DEMO_AS_OF = "2025-01-01"


def demo_tables(seed=42, customers_count=80):
    if customers_count < 1:
        raise ValueError("customers_count must be positive")
    rng = np.random.default_rng(seed)
    categories = ["books", "home", "sports", "electronics", "beauty"]
    products = pd.DataFrame({"product_id": [f"product_{i}" for i in range(15)],
                             "product_category_name": [categories[i % 5] for i in range(15)]})
    orders, customers, items = [], [], []
    order_number = 0
    for customer in range(customers_count):
        months = sorted(rng.choice(np.arange(1, 13), size=int(rng.integers(1, 7)), replace=False))
        for month in months:
            order_number += 1
            order_id = f"order_{order_number:05d}"
            customer_id = f"order_customer_{order_number:05d}"
            date = pd.Timestamp(2024, int(month), int(rng.integers(1, 28)))
            status = "canceled" if rng.random() < 0.06 else "delivered"
            orders.append({"order_id": order_id, "customer_id": customer_id,
                           "order_status": status, "order_purchase_timestamp": date})
            customers.append({"customer_id": customer_id, "customer_unique_id": f"person_{customer:04d}",
                              "customer_state": ["SP", "RJ", "MG", "BA", "PR"][customer % 5]})
            for sequence in range(1, int(rng.integers(2, 5))):
                items.append({"order_id": order_id, "order_item_id": sequence,
                              "product_id": f"product_{int(rng.integers(0, 15))}",
                              "price": float(rng.integers(1500, 18000)) / 100,
                              "freight_value": float(rng.integers(500, 2000)) / 100})
    return {"orders": pd.DataFrame(orders), "customers": pd.DataFrame(customers),
            "items": pd.DataFrame(items), "products": products}

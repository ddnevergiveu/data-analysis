"""Compatibility exports. Customer metrics now use customer_unique_id."""
from olist_analytics.metrics import customer_lifetime_analysis, repeat_rate, top_customers

__all__ = ["customer_lifetime_analysis", "repeat_rate", "top_customers"]

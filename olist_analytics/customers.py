"""Two portfolio projects: rule-based RFM segments and monthly purchase retention."""

import numpy as np
import pandas as pd

from .metrics import order_summary


def rfm_segments(items, as_of):
    """Fixed transparent rules preserve identical treatment of tied observations."""
    as_of = pd.Timestamp(as_of)
    orders = order_summary(items)
    orders = orders[orders["order_purchase_timestamp"] < as_of]
    result = orders.groupby("customer_unique_id").agg(
        last_purchase=("order_purchase_timestamp", "max"),
        frequency=("order_id", "nunique"),
        monetary=("merchandise_value", "sum"),
    )
    result["recency_days"] = (as_of - result["last_purchase"]).dt.days
    recent = result["recency_days"] <= 90
    repeat = result["frequency"] >= 2
    result["segment"] = np.select(
        [recent & (result["frequency"] >= 3) & (result["monetary"] >= 500),
         recent & repeat,
         (result["recency_days"] <= 30) & ~repeat,
         ~recent & repeat,
         result["recency_days"] > 180],
        ["champions", "loyal", "new", "at_risk", "hibernating"],
        default="occasional",
    )
    return result[["recency_days", "frequency", "monetary", "segment", "last_purchase"]].sort_index()


def cohort_retention(items, observation_end):
    """Return cohort counts/rates; unfinished calendar months are never zero-filled.

    The exclusive observation end must come from source coverage. The newest
    partial month is excluded, and cells after coverage remain NaN.
    """
    end = pd.Timestamp(observation_end)
    orders = order_summary(items)
    orders = orders[orders["order_purchase_timestamp"] < end].copy()
    orders["purchase_month"] = orders["order_purchase_timestamp"].dt.to_period("M")
    last_complete_month = end.to_period("M") - 1
    orders = orders[orders["purchase_month"] <= last_complete_month]
    if orders.empty:
        return pd.DataFrame(), pd.DataFrame()
    orders["cohort"] = orders.groupby("customer_unique_id")["purchase_month"].transform("min")
    orders["age"] = orders["purchase_month"].astype("int64") - orders["cohort"].astype("int64")
    observed = orders.groupby(["cohort", "age"])["customer_unique_id"].nunique()
    cohorts = sorted(orders["cohort"].unique())
    max_age = last_complete_month.ordinal - cohorts[0].ordinal
    counts = pd.DataFrame(np.nan, index=pd.PeriodIndex(cohorts, name="cohort"), columns=range(max_age + 1))
    counts.columns.name = "months_since_first_observed_purchase"
    for cohort in cohorts:
        age_limit = last_complete_month.ordinal - cohort.ordinal
        for age in range(age_limit + 1):
            counts.loc[cohort, age] = observed.get((cohort, age), 0)
    rates = counts.div(counts[0], axis=0)
    return counts, rates

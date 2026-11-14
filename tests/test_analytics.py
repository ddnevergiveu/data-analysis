"""Regression cases for business semantics, integrity and censored cohorts."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from olist_analytics.customers import cohort_retention, rfm_segments
from olist_analytics.data import FILES, load_tables, prepare_data
from olist_analytics.demo import demo_tables
from olist_analytics.features import add_total_amount
from olist_analytics.metrics import customer_lifetime_analysis, sales_summary


def fixture():
    return {
        "orders": pd.DataFrame([
            ["o1", "c1", "delivered", "2024-01-05"],
            ["o2", "c2", "delivered", "2024-02-05"],
            ["o3", "c3", "delivered", "2024-02-10"],
            ["o4", "c4", "canceled", "2024-03-05"],
        ], columns=["order_id", "customer_id", "order_status", "order_purchase_timestamp"]),
        "customers": pd.DataFrame([
            ["c1", "person_a", "SP"], ["c2", "person_a", "SP"],
            ["c3", "person_b", "RJ"], ["c4", "person_b", "RJ"],
        ], columns=["customer_id", "customer_unique_id", "customer_state"]),
        "items": pd.DataFrame([
            ["o1", 1, "p1", 10.0, 1.0], ["o1", 2, "p2", 20.0, 2.0],
            ["o2", 1, "p1", 30.0, 3.0], ["o3", 1, "p2", 50.0, 4.0],
            ["o4", 1, "p2", 900.0, 10.0],
        ], columns=["order_id", "order_item_id", "product_id", "price", "freight_value"]),
        "products": pd.DataFrame([["p1", "books"], ["p2", "home"]],
                                 columns=["product_id", "product_category_name"]),
    }


class BusinessMetricsTests(unittest.TestCase):
    def test_item_sequence_is_not_quantity_and_aov_is_per_order(self):
        items, quality, _ = prepare_data(fixture(), "2024-04-01")
        summary = sales_summary(items)
        self.assertEqual(summary["merchandise_value"], 110)
        self.assertEqual(summary["orders"], 3)
        self.assertAlmostEqual(summary["average_order_value"], 110 / 3)
        self.assertEqual(summary["freight_value"], 10)
        self.assertEqual(quality["excluded_status_orders"], 1)

    def test_persistent_customer_identity_and_observed_span(self):
        items, _, _ = prepare_data(fixture(), "2024-04-01")
        self.assertEqual(sales_summary(items)["customers"], 2)
        self.assertEqual(sales_summary(items)["repeat_customer_rate"], 0.5)
        self.assertEqual(customer_lifetime_analysis(items).loc["person_a", "observed_span_days"], 31)

    def test_cutoff_is_exclusive(self):
        items, _, _ = prepare_data(fixture(), "2024-02-05")
        self.assertEqual(set(items["order_id"]), {"o1"})

    def test_rfm_uses_order_amount_and_identical_ties(self):
        items, _, _ = prepare_data(fixture(), "2024-04-01")
        rfm = rfm_segments(items, "2024-04-01")
        self.assertEqual(rfm.loc["person_a", "frequency"], 2)
        self.assertEqual(rfm.loc["person_a", "monetary"], 60)
        self.assertEqual(rfm.loc["person_a", "segment"], "loyal")
        copied = items[items.customer_unique_id == "person_a"].copy()
        copied["customer_unique_id"] = "person_clone"
        copied["order_id"] += "_clone"
        rfm = rfm_segments(pd.concat([items, copied]), "2024-04-01")
        self.assertEqual(rfm.loc["person_a", "segment"], rfm.loc["person_clone", "segment"])

    def test_cohort_zero_is_different_from_unobserved(self):
        items, _, _ = prepare_data(fixture(), "2024-04-01")
        counts, rates = cohort_retention(items, "2024-04-01")
        january, february = pd.Period("2024-01"), pd.Period("2024-02")
        self.assertEqual(counts.loc[january, 0], 1)
        self.assertEqual(rates.loc[january, 1], 1)
        self.assertEqual(rates.loc[january, 2], 0)
        self.assertEqual(rates.loc[february, 1], 0)
        self.assertTrue(np.isnan(rates.loc[february, 2]))

    def test_partial_month_not_counted_as_zero_retention(self):
        items, _, _ = prepare_data(fixture(), "2024-03-15")
        _, rates = cohort_retention(items, "2024-03-15")
        self.assertEqual(list(rates.columns), [0, 1])
        self.assertTrue(np.isnan(rates.loc[pd.Period("2024-02"), 1]))
        _, no_complete = cohort_retention(items, "2024-01-20")
        self.assertTrue(no_complete.empty)


class DataQualityTests(unittest.TestCase):
    def test_exact_duplicate_removed_without_mutating_inputs(self):
        tables = fixture()
        tables["items"] = pd.concat([tables["items"], tables["items"].iloc[[0]]], ignore_index=True)
        original = tables["items"].copy(deep=True)
        items, quality, _ = prepare_data(tables, "2024-04-01")
        self.assertEqual(quality["exact_duplicates_removed"]["items"], 1)
        self.assertEqual(sales_summary(items)["merchandise_value"], 110)
        assert_frame_equal(original, tables["items"])

    def test_conflicting_duplicate_dimension_cannot_multiply_sales(self):
        tables = fixture()
        duplicate = tables["products"].iloc[[0]].copy()
        duplicate["product_category_name"] = "conflicting"
        tables["products"] = pd.concat([tables["products"], duplicate])
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            prepare_data(tables)

    def test_bad_prices_fail_instead_of_becoming_zero(self):
        for value in [-1, float("inf"), "bad", None]:
            with self.subTest(value=value):
                tables = fixture()
                tables["items"]["price"] = tables["items"]["price"].astype(object)
                tables["items"].loc[0, "price"] = value
                with self.assertRaises(ValueError):
                    prepare_data(tables)

    def test_missing_customer_and_unmatched_product_fail(self):
        tables = fixture()
        tables["customers"].loc[0, "customer_unique_id"] = None
        with self.assertRaisesRegex(ValueError, "missing or blank"):
            prepare_data(tables)
        tables = fixture()
        tables["items"].loc[0, "product_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "Unmatched product_id"):
            prepare_data(tables)

    def test_invalid_date_and_missing_item_rows_fail(self):
        tables = fixture()
        tables["orders"].loc[0, "order_purchase_timestamp"] = "bad"
        with self.assertRaisesRegex(ValueError, "invalid or missing"):
            prepare_data(tables)
        tables = fixture()
        tables["items"] = tables["items"][tables["items"].order_id != "o1"]
        with self.assertRaisesRegex(ValueError, "lack item rows"):
            prepare_data(tables)

    def test_item_sequence_validation(self):
        for value in [0, -1, 1.5]:
            tables = fixture()
            tables["items"]["order_item_id"] = tables["items"]["order_item_id"].astype(float)
            tables["items"].loc[0, "order_item_id"] = value
            with self.assertRaisesRegex(ValueError, "positive integer"):
                prepare_data(tables)

    def test_timezone_offsets_are_rejected_cleanly(self):
        tables = fixture()
        tables["orders"]["order_purchase_timestamp"] = [
            "2024-01-01T00:00:00+00:00", "2024-02-01T00:00:00+01:00",
            "2024-02-10T00:00:00+01:00", "2024-03-05T00:00:00+00:00",
        ]
        with self.assertRaisesRegex(ValueError, "timezone-naive"):
            prepare_data(tables)

    def test_feature_helper_is_pure(self):
        original = pd.DataFrame({"price": [10, 20], "order_item_id": [1, 2]})
        result = add_total_amount(original)
        self.assertEqual(result.total_amount.tolist(), [10, 20])
        self.assertNotIn("total_amount", original)

    def test_csv_roundtrip_and_missing_file_message(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "--demo"):
                load_tables(directory)
            for name, frame in fixture().items():
                frame.to_csv(Path(directory) / FILES[name], index=False)
            loaded = load_tables(directory)
            self.assertEqual(sales_summary(prepare_data(loaded, "2024-04-01")[0])["merchandise_value"], 110)


class EndToEndTests(unittest.TestCase):
    def test_demo_is_reproducible_and_labeled(self):
        first, second = demo_tables(42), demo_tables(42)
        for key in first:
            assert_frame_equal(first[key], second[key])

    def test_cli_produces_consistent_artifacts(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run([sys.executable, str(root / "main.py"), "--demo", "--output", directory],
                                       cwd=directory, capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = Path(directory)
            summary = json.loads((report / "summary.json").read_text())
            self.assertTrue(summary["synthetic"])
            orders = pd.read_csv(report / "orders.csv")
            self.assertEqual(len(orders), summary["metrics"]["orders"])
            self.assertAlmostEqual(orders.merchandise_value.sum(), summary["metrics"]["merchandise_value"])
            document = (report / "index.html").read_text()
            self.assertIn("合成演示数据", document)
            self.assertIn("data:image/png;base64,", document)
            self.assertTrue((report / "rfm_segments.csv").is_file())
            self.assertTrue((report / "cohort_retention.csv").is_file())


if __name__ == "__main__":
    unittest.main()

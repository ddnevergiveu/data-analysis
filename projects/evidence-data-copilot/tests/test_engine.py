"""Behavioral regression tests for data integrity, SQL policy and query budgets."""

import csv
import hashlib
from pathlib import Path
import tempfile
import unittest

from evidence_copilot.engine import QueryEngine, QueryExecutionError, QueryTimeoutError
from evidence_copilot.policy import QueryPolicyError, validate_sql
from evidence_copilot.warehouse import COLUMNS, create_demo, import_csv


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.csv_path = self.directory / "orders.csv"
        self.db_path = self.directory / "orders.duckdb"
        self.records = [
            ["o1", "a", "2025-01-02", "East", "10.10"],
            ["o2", "a", "2025-02-02", "East", "20.20"],
            ["o3", "b", "2025-02-10", "West", "30.30"],
        ]
        self.write_csv(self.records)

    def tearDown(self):
        self.temporary.cleanup()

    def write_csv(self, rows, header=COLUMNS):
        with self.csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)

    def engine(self, **options):
        import_csv(self.csv_path, self.db_path)
        return QueryEngine(self.db_path, **options)

    def test_exact_decimal_aggregates_and_customer_counts(self):
        result = self.engine().query("SELECT SUM(amount) AS gross_amount, COUNT(*) AS orders, COUNT(DISTINCT customer_id) AS customers FROM orders")
        self.assertEqual(result["rows"], [["60.60", 3, 2]])
        self.assertFalse(result["truncated"])
        self.assertFalse(result["dataset"]["synthetic"])

    def test_cte_and_monthly_aggregation(self):
        engine = self.engine()
        monthly = engine.query("SELECT DATE_TRUNC('month', order_date) AS month, SUM(amount) AS total FROM orders GROUP BY 1 ORDER BY 1")
        self.assertEqual(monthly["rows"], [["2025-01-01T00:00:00", "10.10"], ["2025-02-01T00:00:00", "50.50"]])
        repeat = engine.query("WITH f AS (SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id) SELECT AVG(CASE WHEN n > 1 THEN 1.0 ELSE 0.0 END) AS rate FROM f")
        self.assertEqual(repeat["rows"], [[0.5]])

    def test_truncation_and_stable_evidence_id(self):
        engine = self.engine(max_rows=2)
        first = engine.query("SELECT order_id, amount FROM orders ORDER BY order_id")
        second = engine.query("SELECT order_id, amount FROM orders ORDER BY order_id")
        self.assertEqual(first["row_count"], 2)
        self.assertTrue(first["truncated"])
        self.assertEqual(first["evidence_id"], second["evidence_id"])

    def test_queries_do_not_change_database_bytes(self):
        engine = self.engine()
        before = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        engine.query("SELECT AVG(amount) AS average FROM orders")
        engine.schema()
        self.assertEqual(hashlib.sha256(self.db_path.read_bytes()).hexdigest(), before)

    def test_conflicting_or_duplicate_orders_rejected(self):
        self.write_csv(self.records + [self.records[0]])
        with self.assertRaisesRegex(ValueError, "duplicate order_id"):
            import_csv(self.csv_path, self.db_path)
        self.assertFalse(self.db_path.exists())

    def test_invalid_dates_keys_and_amounts_rejected(self):
        for column, value in [(0, ""), (1, " "), (2, "2025-02-30"), (2, "20250101"),
                              (4, "NaN"), (4, "Infinity"), (4, "-1"), (4, "1.001"), (4, "1e17")]:
            with self.subTest(column=column, value=value):
                rows = [row[:] for row in self.records]
                rows[0][column] = value
                self.write_csv(rows)
                with self.assertRaises(ValueError):
                    import_csv(self.csv_path, self.db_path)
                self.assertFalse(self.db_path.exists())

    def test_existing_snapshot_preserved(self):
        self.engine()
        before = self.db_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            create_demo(self.db_path)
        self.assertEqual(self.db_path.read_bytes(), before)

    def test_semantic_hash_ignores_csv_row_order(self):
        first = import_csv(self.csv_path, self.db_path)
        self.write_csv(list(reversed(self.records)))
        second = import_csv(self.csv_path, self.directory / "reordered.duckdb")
        self.assertEqual(first["semantic_sha256"], second["semantic_sha256"])
        self.assertNotEqual(first["input_sha256"], second["input_sha256"])

    def test_synthetic_demo_is_reproducible(self):
        first = create_demo(self.db_path)
        second = create_demo(self.directory / "other.duckdb")
        self.assertTrue(first["synthetic"])
        self.assertEqual(first["rows"], 160)
        self.assertEqual(first["semantic_sha256"], second["semantic_sha256"])

    def test_no_result_and_invalid_result_are_explicit(self):
        engine = self.engine()
        empty = engine.query("SELECT order_id FROM orders WHERE amount < 0")
        self.assertEqual(empty["rows"], [])
        with self.assertRaises(QueryExecutionError):
            engine.query("SELECT 1.0 / 0.0 AS infinity FROM orders LIMIT 1")
        with self.assertRaises(QueryExecutionError):
            engine.query("SELECT missing_column FROM orders")

    def test_execution_budget_interrupts_expensive_query(self):
        create_demo(self.db_path)
        engine = QueryEngine(self.db_path, timeout_seconds=0.001)
        with self.assertRaises(QueryTimeoutError):
            engine.query("SELECT SUM(a.amount * b.amount * c.amount * d.amount) AS huge FROM orders a CROSS JOIN orders b CROSS JOIN orders c CROSS JOIN orders d")


class PolicyTests(unittest.TestCase):
    def test_unsafe_or_unbounded_language_is_rejected(self):
        statements = [
            "SELECT * FROM orders; DROP TABLE orders",
            "UPDATE orders SET amount=0",
            "COPY orders TO '/tmp/leaked.csv'",
            "PRAGMA database_list",
            "SET enable_external_access=true",
            "INSTALL httpfs",
            "SELECT * FROM read_csv('/etc/passwd')",
            "SELECT * FROM read_parquet('https://example.com/private')",
            "SELECT * FROM _metadata",
            "SELECT * FROM information_schema.tables",
            "SELECT * FROM main.orders",
            "SELECT * FROM range(1000000000000)",
            "SELECT unknown_function(amount) FROM orders",
            "WITH RECURSIVE r AS (SELECT 1 AS x) SELECT x FROM r",
            "SELECT * INTO secret FROM orders",
            "SELECT * FROM orders UNION SELECT * FROM orders",
        ]
        for statement in statements:
            with self.subTest(sql=statement):
                with self.assertRaises(QueryPolicyError):
                    validate_sql(statement)

    def test_comments_do_not_disguise_second_statement(self):
        with self.assertRaises(QueryPolicyError):
            validate_sql("SELECT * FROM orders; /* harmless? */ SELECT * FROM orders")
        self.assertIn("SELECT", validate_sql("SELECT SUM(amount) AS total FROM orders -- comment\n"))

    def test_length_and_output_configuration_limits(self):
        with self.assertRaises(QueryPolicyError):
            validate_sql("SELECT " + " " * 12000 + "1")


if __name__ == "__main__":
    unittest.main()

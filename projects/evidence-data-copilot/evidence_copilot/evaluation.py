"""Hand-calculated checks for execution, offline planning and query rejection.

This is a small deterministic regression set, not an LLM accuracy benchmark.
Every expected value below is independent of the implementation under test.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any


FIXTURE_ROWS = (
    ("o1", "A", "2026-01-02", "east", "100.00"),
    ("o2", "B", "2026-01-03", "north", "50.00"),
    ("o3", "A", "2026-02-02", "east", "200.00"),
    ("o4", "C", "2026-02-03", "west", "80.00"),
    ("o5", "B", "2026-02-04", "north", "50.00"),
    ("o6", "D", "2026-02-05", "east", "20.00"),
)

REPEAT_SQL = """WITH customer_orders AS (
    SELECT customer_id, COUNT(*) AS order_count
    FROM orders GROUP BY customer_id
)
SELECT SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) * 1.0
       / NULLIF(COUNT(*), 0) AS repeat_rate
FROM customer_orders"""

QUERY_CASES = (
    ("order_grain", "SELECT COUNT(*) AS orders, COUNT(DISTINCT customer_id) AS customers, SUM(amount) AS revenue FROM orders", [[6, 4, 500]]),
    ("average_order", "SELECT AVG(amount) AS average_order_value FROM orders", [[500 / 6]]),
    ("monthly_sales", "SELECT DATE_TRUNC('month', order_date) AS month, SUM(amount) AS revenue FROM orders GROUP BY 1 ORDER BY 1", [["2026-01", 150], ["2026-02", 350]]),
    ("region_sales", "SELECT region, SUM(amount) AS revenue FROM orders GROUP BY region ORDER BY revenue DESC, region", [["east", 320], ["north", 100], ["west", 80]]),
    ("repeat_customers", REPEAT_SQL, [[0.5]]),
    ("top_customers", "SELECT customer_id, SUM(amount) AS revenue FROM orders GROUP BY customer_id ORDER BY revenue DESC, customer_id LIMIT 10", [["A", 300], ["B", 100], ["C", 80], ["D", 20]]),
)

RULE_CASES = (
    ("total", "总销售额是多少？", ["order_count", "customer_count", "total_amount"], [[6, 4, 500]]),
    ("average", "平均客单价是多少？", ["average_order_value"], [[83.33]]),
    ("monthly", "每月销售额是多少？", ["month", "orders", "total_amount"], [["2026-01", 2, 150], ["2026-02", 4, 350]]),
    ("regions", "各地区销售额排名", ["region", "orders", "total_amount"], [["east", 3, 320], ["north", 2, 100], ["west", 1, 80]]),
    ("repeat", "客户复购率是多少？", ["customers", "repeat_customers", "repeat_customer_rate"], [[4, 2, 0.5]]),
    ("top_customers", "消费金额最高的前10位客户", ["customer_id", "orders", "total_amount"], [["A", 2, 300], ["B", 2, 100], ["C", 1, 80], ["D", 1, 20]]),
)

REJECTION_CASES = (
    ("multiple_statements", "SELECT COUNT(*) FROM orders; SELECT SUM(amount) FROM orders"),
    ("write_update", "UPDATE orders SET amount = 0"),
    ("write_delete", "DELETE FROM orders"),
    ("external_file", "SELECT * FROM read_csv('/etc/passwd')"),
    ("system_catalog", "SELECT * FROM information_schema.tables"),
    ("unknown_function", "SELECT mystery_function(amount) FROM orders"),
    ("table_function", "SELECT * FROM range(100)"),
)


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float, Decimal)) and not isinstance(expected, bool):
        try:
            left, right = Decimal(str(actual)), Decimal(str(expected))
        except (InvalidOperation, ValueError, TypeError):
            return False
        if not left.is_finite() or not right.is_finite():
            return False
        return abs(left - right) <= max(Decimal("0.000000001"), abs(right) * Decimal("0.0000000001"))
    if isinstance(expected, str) and re.fullmatch(r"\d{4}-\d{2}", expected):
        # DuckDB DATE/TIMESTAMP can serialize differently; the metric is month.
        return isinstance(actual, str) and actual[:7] == expected
    return actual == expected


def _same_rows(actual: Any, expected: list[list[Any]]) -> bool:
    return (
        isinstance(actual, list)
        and len(actual) == len(expected)
        and all(
            isinstance(left, (list, tuple))
            and len(left) == len(right)
            and all(_same_value(a, b) for a, b in zip(left, right))
            for left, right in zip(actual, expected)
        )
    )


def evaluate() -> dict[str, Any]:
    """Run 19 isolated checks against six explicitly synthetic orders.

    Failures are reported individually; setup failures remain explicit exceptions.
    No model calls, credentials, live customer data or external data are used.
    """
    from .engine import QueryEngine
    from .planning import rule_plan
    from .warehouse import import_csv

    cases: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="evidence-copilot-eval-") as directory:
        root = Path(directory)
        csv_path, database_path = root / "six_orders.csv", root / "orders.duckdb"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["order_id", "customer_id", "order_date", "region", "amount"])
            writer.writerows(FIXTURE_ROWS)
        import_csv(csv_path, database_path)
        engine = QueryEngine(database_path, max_rows=100, timeout_seconds=3)

        for case_id, sql, expected in QUERY_CASES:
            item: dict[str, Any] = {"id": f"query.{case_id}", "category": "query_execution", "sql": sql, "expected": expected}
            try:
                result = engine.query(sql)
                item["actual"] = result["rows"]
                item["passed"] = _same_rows(result["rows"], expected) and not result["truncated"]
            except Exception as error:
                item.update(passed=False, error=f"{type(error).__name__}: {error}")
            cases.append(item)

        for case_id, question, columns, expected in RULE_CASES:
            item = {"id": f"rules.{case_id}", "category": "rule_planning", "question": question, "expected_columns": columns, "expected": expected}
            try:
                plan = rule_plan(question)
                item["sql"] = plan.sql
                result = engine.query(plan.sql)
                column_positions = [result["columns"].index(name) for name in columns]
                actual = [[row[position] for position in column_positions] for row in result["rows"]]
                item["actual"] = actual
                item["passed"] = _same_rows(actual, expected) and not result["truncated"]
            except Exception as error:
                item.update(passed=False, error=f"{type(error).__name__}: {error}")
            cases.append(item)

        for case_id, sql in REJECTION_CASES:
            item = {"id": f"reject.{case_id}", "category": "query_rejection", "sql": sql, "expected": "ValueError"}
            try:
                engine.query(sql)
            except ValueError as error:
                item.update(passed=True, actual="ValueError", reason=str(error))
            except Exception as error:
                item.update(passed=False, error=f"Unexpected {type(error).__name__}: {error}")
            else:
                item.update(passed=False, actual="query was accepted")
            cases.append(item)

    passed = sum(case["passed"] for case in cases)
    return {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "all_passed": passed == len(cases),
        "scope": {
            "dataset": "six synthetic, hand-calculated orders; no real customer records",
            "query_execution": "six fixed SQL examples with independent expected values",
            "rule_planning": "six exact Chinese prompts for the offline rule planner",
            "query_rejection": "seven known unsupported SQL forms; not an exhaustive security audit",
            "llm_accuracy": "not measured: no LLM or Ollama inference is used",
        },
        "cases": cases,
    }

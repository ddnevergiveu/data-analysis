"""Exercise the actual MCP v2 client, both in memory and over stdio."""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from evidence_copilot.mcp_server import create_server
from evidence_copilot.warehouse import create_demo, import_csv


class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        source = root / "orders.csv"
        with source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["order_id", "customer_id", "order_date", "region", "amount"])
            writer.writerows([
                ["o1", "alice", "2026-01-01", "north", "42.50"],
                ["o2", "alice", "2026-02-01", "north", "27.50"],
                ["o3", "bob", "2026-02-02", "south", "100.00"],
            ])
        self.db = root / "fixture.duckdb"
        import_csv(source, self.db)

    async def test_discovery_advertises_only_fixed_readonly_tools(self):
        async with Client(create_server(self.db), raise_exceptions=True) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        self.assertEqual(set(tools), {"describe_dataset", "run_query"})
        self.assertEqual(set(tools["run_query"].input_schema["properties"]), {"sql"})
        for tool in tools.values():
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.open_world_hint)
            self.assertIsNotNone(tool.output_schema)

    async def test_structured_result_has_correct_values_and_stable_evidence(self):
        sql = "SELECT COUNT(*) AS orders, SUM(amount) AS total FROM orders"
        async with Client(create_server(self.db), raise_exceptions=True) as client:
            first = await client.call_tool("run_query", {"sql": sql})
            second = await client.call_tool("run_query", {"sql": sql})
        self.assertFalse(first.is_error)
        result = first.structured_content
        self.assertEqual(result["columns"], ["orders", "total"])
        self.assertEqual(result["rows"], [[3, "170.00"]])
        self.assertEqual(result["row_count"], 1)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["evidence_id"], second.structured_content["evidence_id"])
        self.assertIn("dataset", result)

    async def test_resource_matches_schema_tool(self):
        async with Client(create_server(self.db), raise_exceptions=True) as client:
            described = await client.call_tool("describe_dataset", {})
            resource = await client.read_resource("dataset://orders/schema")
            resources = (await client.list_resources()).resources
        self.assertFalse(described.is_error)
        self.assertEqual(json.loads(resource.contents[0].text), described.structured_content)
        self.assertIn("orders", resource.contents[0].text)
        self.assertIn("dataset://orders/schema", [str(item.uri) for item in resources])

    async def test_demo_source_and_truncation_survive_protocol(self):
        demo_db = Path(self.directory.name) / "demo.duckdb"
        create_demo(demo_db)
        async with Client(create_server(demo_db), raise_exceptions=True) as client:
            result = await client.call_tool(
                "run_query", {"sql": "SELECT order_id FROM orders ORDER BY order_id"}
            )
        payload = result.structured_content
        self.assertFalse(result.is_error)
        self.assertTrue(payload["dataset"]["synthetic"])
        self.assertEqual(payload["dataset"]["source"], "synthetic_demo")
        self.assertEqual(payload["row_count"], 100)
        self.assertTrue(payload["truncated"])

    async def test_rejected_sql_is_protocol_error_and_does_not_mutate(self):
        async with Client(create_server(self.db), raise_exceptions=True) as client:
            rejected = await client.call_tool("run_query", {"sql": "DROP TABLE orders"})
            afterward = await client.call_tool("run_query", {"sql": "SELECT COUNT(*) AS n FROM orders"})
        self.assertTrue(rejected.is_error)
        self.assertIn("Query rejected:", rejected.content[0].text)
        self.assertEqual(afterward.structured_content["rows"], [[3]])

    async def test_client_input_schema_rejects_empty_sql(self):
        async with Client(create_server(self.db), raise_exceptions=True) as client:
            result = await client.call_tool("run_query", {"sql": ""})
        self.assertTrue(result.is_error)

    async def test_stdio_subprocess_supports_discovery_and_query(self):
        project = Path(__file__).resolve().parents[1]
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "evidence_copilot", "serve", "--db", str(self.db)],
            cwd=project,
        )

        async def exchange():
            async with Client(parameters, read_timeout_seconds=10) as client:
                names = {tool.name for tool in (await client.list_tools()).tools}
                result = await client.call_tool("run_query", {"sql": "SELECT COUNT(*) AS n FROM orders"})
                return names, result

        names, result = await asyncio.wait_for(exchange(), timeout=20)
        self.assertIn("run_query", names)
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["rows"], [[3]])


if __name__ == "__main__":
    unittest.main()

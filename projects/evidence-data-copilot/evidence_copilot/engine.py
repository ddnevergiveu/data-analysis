"""Read-only query execution with bounded output and reproducible evidence IDs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import threading
import time

import duckdb

from .policy import validate_sql
from .warehouse import COLUMNS, SCHEMA_VERSION


CONNECTION_CONFIG = {
    "enable_external_access": "false",
    "autoinstall_known_extensions": "false",
    "autoload_known_extensions": "false",
    "allow_community_extensions": "false",
    "allow_unsigned_extensions": "false",
    "allow_persistent_secrets": "false",
    "threads": "2",
    "memory_limit": "256MB",
    "max_temp_directory_size": "0B",
    "temp_directory": "",
}


class QueryExecutionError(ValueError):
    """A supported query could not be executed on the validated dataset."""


class QueryTimeoutError(QueryExecutionError):
    """The cooperative DuckDB execution timeout elapsed."""


def _scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise QueryExecutionError("Query returned a non-finite or unsupported result value")


class QueryEngine:
    """Open a trusted snapshot per call; the SQL policy is defense in depth.

    The timer interrupts DuckDB execution cooperatively. This class is not an
    operating-system sandbox and should not be exposed to hostile remote users.
    """

    def __init__(self, db_path: Path, max_rows: int = 100, timeout_seconds: float = 3.0):
        self.db_path = Path(db_path).expanduser().absolute()
        if not self.db_path.is_file():
            raise ValueError(f"Database snapshot does not exist: {self.db_path}")
        if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 1 <= max_rows <= 1000:
            raise ValueError("max_rows must be an integer between 1 and 1000")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be positive and no greater than 30")
        self.max_rows = max_rows
        self.timeout_seconds = float(timeout_seconds)

    def _connect(self):
        try:
            connection = duckdb.connect(str(self.db_path), read_only=True, config=CONNECTION_CONFIG)
            connection.execute("SET lock_configuration=true")
            return connection
        except duckdb.Error as error:
            raise QueryExecutionError(f"Unable to open read-only snapshot: {error}") from error

    def _metadata(self, connection):
        try:
            values = connection.execute("SELECT content FROM _metadata").fetchall()
            if len(values) != 1:
                raise ValueError("expected one metadata record")
            metadata = json.loads(values[0][0])
            if metadata["schema_version"] != SCHEMA_VERSION:
                raise ValueError("unsupported schema version")
            digest = metadata["semantic_sha256"]
            if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("invalid semantic digest")
            return metadata
        except (duckdb.Error, ValueError, TypeError, KeyError) as error:
            raise QueryExecutionError("Not a valid Evidence Copilot snapshot; create it with demo or import") from error

    def schema(self) -> dict:
        with self._connect() as connection:
            metadata = self._metadata(connection)
        columns = [
            {"name": "order_id", "type": "VARCHAR", "description": "Unique order identifier; one row is one order"},
            {"name": "customer_id", "type": "VARCHAR", "description": "Stable customer identifier across orders"},
            {"name": "order_date", "type": "DATE", "description": "Purchase date in a single user-defined local calendar"},
            {"name": "region", "type": "VARCHAR", "description": "Order destination region"},
            {"name": "amount", "type": "DECIMAL(18,2)", "description": "Gross order amount in one consistent currency; not net revenue"},
        ]
        return {"tables": [{"name": "orders", "columns": columns}], "dataset": metadata,
                "result_encoding": "DECIMAL values are JSON strings to preserve exact amounts",
                "limits": {"max_rows": self.max_rows, "timeout_seconds": self.timeout_seconds}}

    def query(self, sql: str) -> dict:
        normalized = validate_sql(sql)
        started = time.perf_counter()
        connection = self._connect()
        timer = None
        expired = threading.Event()
        try:
            metadata = self._metadata(connection)

            def interrupt():
                expired.set()
                connection.interrupt()

            timer = threading.Timer(self.timeout_seconds, interrupt)
            timer.daemon = True
            timer.start()
            cursor = connection.execute(normalized)
            columns = [description[0] for description in cursor.description]
            if len(columns) != len(set(columns)):
                raise QueryExecutionError("Result columns must have unique names; add explicit SQL aliases")
            raw_rows = cursor.fetchmany(self.max_rows + 1)
            if expired.is_set():
                raise QueryTimeoutError(f"Query exceeded the {self.timeout_seconds:g}-second execution budget")
            truncated = len(raw_rows) > self.max_rows
            rows = [[_scalar(value) for value in row] for row in raw_rows[:self.max_rows]]
        except duckdb.InterruptException as error:
            raise QueryTimeoutError(f"Query exceeded the {self.timeout_seconds:g}-second execution budget") from error
        except duckdb.Error as error:
            raise QueryExecutionError(f"Query could not execute: {error}") from error
        finally:
            if timer is not None:
                timer.cancel()
                timer.join()
            connection.close()
        evidence = {"semantic_sha256": metadata["semantic_sha256"], "sql": normalized,
                    "columns": columns, "rows": rows, "truncated": truncated, "max_rows": self.max_rows}
        digest = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated,
                "sql": normalized, "dataset": metadata, "evidence_id": f"ev_{digest[:24]}",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}

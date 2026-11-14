"""Create immutable, validated single-table DuckDB snapshots from trusted inputs."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import random
import tempfile

import duckdb


COLUMNS = ("order_id", "customer_id", "order_date", "region", "amount")
SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_ROWS = 1_000_000


def _validate_rows(records):
    rows, seen = [], set()
    for number, record in enumerate(records, start=2):
        if number - 2 >= MAX_ROWS:
            raise ValueError(f"CSV exceeds the {MAX_ROWS:,}-order limit")
        if set(record) != set(COLUMNS):
            raise ValueError(f"CSV row {number}: expected exactly {', '.join(COLUMNS)}")
        values = {}
        for column in COLUMNS:
            value = record[column]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"CSV row {number}: missing {column}")
            value = value.strip()
            if len(value) > 128 or any(ord(char) < 32 for char in value):
                raise ValueError(f"CSV row {number}: invalid or oversized {column}")
            values[column] = value
        if values["order_id"] in seen:
            raise ValueError(f"CSV row {number}: duplicate order_id")
        seen.add(values["order_id"])
        try:
            order_date = date.fromisoformat(values["order_date"])
        except ValueError as error:
            raise ValueError(f"CSV row {number}: order_date must be YYYY-MM-DD") from error
        if order_date.isoformat() != values["order_date"]:
            raise ValueError(f"CSV row {number}: order_date must be YYYY-MM-DD")
        try:
            amount = Decimal(values["amount"])
        except InvalidOperation as error:
            raise ValueError(f"CSV row {number}: invalid amount") from error
        if not amount.is_finite() or amount < 0 or amount >= Decimal("10000000000000000"):
            raise ValueError(f"CSV row {number}: amount must be finite, nonnegative and fit DECIMAL(18,2)")
        if amount.as_tuple().exponent < -2:
            raise ValueError(f"CSV row {number}: amount must have at most two decimal places")
        rows.append((values["order_id"], values["customer_id"], order_date,
                     values["region"], amount.quantize(Decimal("0.01"))))
    if not rows:
        raise ValueError("CSV must contain at least one order")
    return sorted(rows, key=lambda row: row[0])


def _canonical_bytes(rows):
    normalized = [[order, customer, day.isoformat(), region, format(amount, ".2f")]
                  for order, customer, day, region, amount in rows]
    return json.dumps({"schema_version": SCHEMA_VERSION, "columns": COLUMNS, "rows": normalized},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _publish(rows, db_path, *, input_sha256, source, synthetic, seed=None):
    destination = Path(db_path).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Database already exists: {destination}; choose a new snapshot path")
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "synthetic": synthetic,
        "rows": len(rows),
        "input_sha256": input_sha256,
        "semantic_sha256": hashlib.sha256(_canonical_bytes(rows)).hexdigest(),
        "date_min": min(row[2] for row in rows).isoformat(),
        "date_max": max(row[2] for row in rows).isoformat(),
        "grain": "one row per order",
        "amount_definition": "gross order amount, not net revenue; one consistent currency required",
        "currency": "unspecified; demo uses synthetic currency units",
        "coverage_note": "Observed dates do not establish complete source coverage.",
    }
    if seed is not None:
        metadata["demo_seed"] = seed
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()  # DuckDB needs a missing path, not an empty file.
    connection = None
    try:
        connection = duckdb.connect(str(temporary))
        connection.execute("BEGIN TRANSACTION")
        connection.execute("""CREATE TABLE orders (
            order_id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL,
            order_date DATE NOT NULL,
            region VARCHAR NOT NULL,
            amount DECIMAL(18,2) NOT NULL CHECK (amount >= 0)
        )""")
        connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", rows)
        connection.execute("CREATE TABLE _metadata (content VARCHAR NOT NULL)")
        connection.execute("INSERT INTO _metadata VALUES (?)", [json.dumps(metadata, ensure_ascii=False, sort_keys=True)])
        connection.execute("COMMIT")
        connection.close()
        connection = None
        # Hard-link publication is atomic and cannot replace an existing target,
        # including one created by another writer after our first existence check.
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise ValueError("Database appeared during creation; existing snapshot was preserved") from error
    except duckdb.Error as error:
        raise ValueError(f"Could not create validated database: {error}") from error
    finally:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)
        Path(str(temporary) + ".wal").unlink(missing_ok=True)
    return metadata


def import_csv(csv_path: Path, db_path: Path) -> dict:
    """Import a trusted UTF-8 standardized order CSV; never overwrite a snapshot."""
    source = Path(csv_path)
    if not source.is_file():
        raise ValueError(f"CSV file does not exist: {source}")
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("CSV exceeds the 50 MiB input limit")
    raw = source.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("CSV exceeds the 50 MiB input limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must be UTF-8 encoded") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != set(COLUMNS):
        raise ValueError(f"CSV header must contain exactly: {', '.join(COLUMNS)}")
    try:
        rows = _validate_rows(reader)
    except csv.Error as error:
        raise ValueError(f"Invalid CSV structure: {error}") from error
    return _publish(rows, db_path, input_sha256=hashlib.sha256(raw).hexdigest(),
                    source="user_supplied_standardized_csv", synthetic=False)


def create_demo(db_path: Path, seed: int = 42) -> dict:
    """Build 160 deterministic synthetic orders without a network request."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    records = []
    regions = ("East", "North", "South", "West")
    for index in range(160):
        records.append({
            "order_id": f"SYN-{index + 1:04d}",
            "customer_id": f"customer_{rng.randrange(60):03d}",
            "order_date": (date(2025, 1, 1) + timedelta(days=rng.randrange(180))).isoformat(),
            "region": regions[rng.randrange(len(regions))],
            "amount": format(Decimal(rng.randrange(1000, 60000)) / 100, ".2f"),
        })
    rows = _validate_rows(records)
    input_hash = hashlib.sha256(_canonical_bytes(rows)).hexdigest()
    return _publish(rows, db_path, input_sha256=input_hash,
                    source="synthetic_demo", synthetic=True, seed=seed)

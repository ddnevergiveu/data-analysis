"""A deliberately small SQL language; parsing is not a general security sandbox."""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, ParseError
from sqlglot.optimizer.scope import Scope, traverse_scope


MAX_SQL_LENGTH = 12_000
MAX_AST_NODES = 800
ALLOWED_FUNCTIONS = {
    "SUM", "COUNT", "AVG", "MIN", "MAX", "ROUND", "NULLIF", "COALESCE",
    "CASE", "IF", "CAST", "TRY_CAST", "DATE_TRUNC", "TIMESTAMP_TRUNC",
    "ABS", "FLOOR", "CEIL", "CEILING", "LOWER", "UPPER", "LENGTH",
}
ALLOWED_NODES = {
    "Select", "From", "Join", "Where", "Group", "Having", "Order", "Ordered",
    "Limit", "Offset", "Column", "Identifier", "Table", "TableAlias", "Alias",
    "Literal", "Boolean", "Null", "Distinct", "Paren", "CTE", "With", "Subquery",
    "DataType", "DataTypeParam", "Star", "Tuple", "Var", "Add", "Sub", "Mul",
    "Div", "Mod", "Neg", "EQ", "NEQ", "GT", "GTE", "LT", "LTE", "And", "Or",
    "Not", "Is", "In", "Between", "Like", "ILike", "Filter",
}


class QueryPolicyError(ValueError):
    """The query is outside the supported read-only analysis language."""


def validate_sql(sql: str) -> str:
    """Return normalized DuckDB SQL only after inspecting the entire parsed AST."""
    if not isinstance(sql, str) or not sql.strip():
        raise QueryPolicyError("SQL must be a nonempty string")
    if len(sql) > MAX_SQL_LENGTH:
        raise QueryPolicyError(f"SQL exceeds the {MAX_SQL_LENGTH}-character limit")
    try:
        parsed = sqlglot.parse(sql, read="duckdb", error_level=ErrorLevel.RAISE)
    except (ParseError, ValueError, RecursionError) as error:
        raise QueryPolicyError("SQL could not be parsed as supported DuckDB SQL") from error
    statements = [statement for statement in parsed if statement is not None]
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise QueryPolicyError("Exactly one SELECT statement is permitted")
    tree = statements[0]
    nodes = list(tree.walk())
    if len(nodes) > MAX_AST_NODES:
        raise QueryPolicyError("SQL expression is too complex")
    if len(list(tree.find_all(exp.Join))) > 3 or len(list(tree.find_all(exp.CTE))) > 8:
        raise QueryPolicyError("Too many joins or common table expressions")
    for node in nodes:
        if isinstance(node, exp.Func):
            if isinstance(node, exp.Anonymous) or node.sql_name() not in ALLOWED_FUNCTIONS:
                raise QueryPolicyError(f"Function is not permitted: {node.sql_name()}")
        elif type(node).__name__ not in ALLOWED_NODES:
            raise QueryPolicyError(f"SQL construct is not supported: {type(node).__name__}")
        if isinstance(node, exp.With) and node.args.get("recursive"):
            raise QueryPolicyError("Recursive CTEs are not permitted")
        if isinstance(node, exp.Select) and node.args.get("into") is not None:
            raise QueryPolicyError("SELECT INTO is not permitted")
        if isinstance(node, exp.Table):
            if not isinstance(node.this, exp.Identifier) or node.db or node.catalog:
                raise QueryPolicyError("Table functions and qualified table names are not permitted")
        if isinstance(node, exp.Column) and (node.db or node.catalog):
            raise QueryPolicyError("Qualified database/schema column names are not permitted")
    try:
        scopes = list(traverse_scope(tree))
        for scope in scopes:
            for _, (_, source) in scope.selected_sources.items():
                if isinstance(source, exp.Table) and source.name.lower() != "orders":
                    raise QueryPolicyError("Only the orders table and query-local CTEs may be read")
                if not isinstance(source, (exp.Table, Scope)):
                    raise QueryPolicyError("Unsupported query source")
    except QueryPolicyError:
        raise
    except (ValueError, TypeError) as error:
        raise QueryPolicyError("Invalid or ambiguous query sources") from error
    if not scopes:
        raise QueryPolicyError("Could not resolve query sources")
    return tree.sql(dialect="duckdb", pretty=False, comments=False)

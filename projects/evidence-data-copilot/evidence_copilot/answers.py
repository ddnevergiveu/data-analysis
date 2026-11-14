"""Deterministic answers linked to database evidence, not generated assertions."""

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import re

from .engine import QueryEngine
from .planning import OllamaPlanner, rule_plan


def answer_question(db_path, question, *, planner="offline_rules", model=None,
                    base_url="http://127.0.0.1:11434", ollama_client=None):
    if planner == "offline_rules":
        plan = rule_plan(question)
    elif planner == "ollama":
        plan = OllamaPlanner(model or "", base_url, client=ollama_client).plan(question)
    else:
        raise ValueError("planner must be offline_rules or ollama")
    result = QueryEngine(db_path).query(plan.sql)
    return {
        "format_version": "1.0",
        "question": plan.question,
        "plan": plan.model_dump(),
        "evidence": result,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {name: version(name) for name in ["duckdb", "mcp", "sqlglot", "pydantic"]},
        "limitations": [
            "The planner proposes SQL; execution success does not prove that it correctly interpreted the question.",
            "All numerical answers below come from the returned database rows, not model-generated claims.",
            "Coverage, currency consistency and the business definition of amount are the data owner's responsibility.",
            "This is a local constrained-query project, not an operating-system sandbox or a public multi-tenant service.",
        ],
    }


def _cell(value):
    if value is None:
        return "NULL"
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("<", "&lt;").replace(">", "&gt;")


def render_markdown(bundle):
    evidence = bundle["evidence"]
    table = ["| " + " | ".join(_cell(value) for value in evidence["columns"]) + " |",
             "| " + " | ".join("---" for _ in evidence["columns"]) + " |"]
    table.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in evidence["rows"])
    synthetic = evidence["dataset"].get("synthetic", False)
    status = "合成演示数据，不能代表真实业务表现" if synthetic else "用户主动导入的数据，业务口径需自行核实"
    mode = "离线规则演示（没有调用大模型）" if bundle["plan"]["planner"] == "offline_rules" else "本地 Ollama 结构化规划（模型解释可能出错）"
    cutoff = "结果已截断，不能将返回行数当作全量行数。" if evidence["truncated"] else "返回结果未截断。"
    # SQL literals may themselves contain Markdown fences. Keep them inside code.
    fence = "`" * max(3, 1 + max((len(match.group()) for match in re.finditer(r"`+", evidence["sql"])), default=0))
    return "\n".join([
        "# 可追溯的数据分析结果", "", f"**数据来源：{status}。**", "", f"问题：{_cell(bundle['question'])}",
        "", f"规划模式：{mode}。", "", "## 数据库实际返回", "", *table, "",
        f"返回 {evidence['row_count']} 行。{cutoff}", "", "## 可复核的执行 SQL", "", fence + "sql",
        evidence["sql"], fence, "", "## 证据与口径", "",
        f"证据 ID：`{evidence['evidence_id']}`", "",
        "数据元信息：", "", "```json", json.dumps(evidence["dataset"], ensure_ascii=False, indent=2), "```", "",
        "规划说明（不构成事实证明）：" + _cell(bundle["plan"]["rationale"]), "",
        *["- " + _cell(text) for text in bundle["plan"]["assumptions"]], "",
        "SQL 和数据指纹用于复核计算；它们不能保证模型对问题的理解正确，也不是防篡改签名。", "",
    ])


def write_bundle(bundle, output_path):
    output = Path(output_path)
    if output.suffix.lower() != ".json":
        raise ValueError("Answer output path must end with .json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(bundle), encoding="utf-8")
    return output


def verify_bundle(bundle, db_path):
    """Replay saved SQL and compare results; this is not a digital signature."""
    if not isinstance(bundle, dict) or bundle.get("format_version") != "1.0":
        raise ValueError("Unsupported or missing evidence bundle format_version")
    saved = bundle.get("evidence")
    if not isinstance(saved, dict) or not isinstance(saved.get("sql"), str):
        raise ValueError("Evidence bundle must contain an executed SQL string")
    actual = QueryEngine(db_path).query(saved["sql"])
    fields = ["sql", "columns", "rows", "truncated", "evidence_id"]
    matches = {field: saved.get(field) == actual[field] for field in fields}
    saved_dataset = saved.get("dataset", {})
    matches["dataset_semantic_sha256"] = isinstance(saved_dataset, dict) and (
        saved_dataset.get("semantic_sha256") == actual["dataset"]["semantic_sha256"]
    )
    return {"verified": all(matches.values()), "matches": matches,
            "replayed_evidence_id": actual["evidence_id"],
            "scope": "Recomputed SQL results and dataset identity only; does not authenticate the file or validate the question interpretation."}

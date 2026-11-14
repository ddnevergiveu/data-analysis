"""CLI for demo/import, constrained SQL, question answering, evals and MCP."""

import argparse
import json
from pathlib import Path


def _emit(value, path=None):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    if path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evidence Data Copilot · DuckDB 2.0 + MCP v2")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="create a deterministic SYNTHETIC database")
    demo.add_argument("--db", type=Path, default=Path("artifacts/demo.duckdb"))
    demo.add_argument("--seed", type=int, default=42)
    load = commands.add_parser("import-csv", help="import trusted local order-level CSV")
    load.add_argument("--csv", type=Path, required=True)
    load.add_argument("--db", type=Path, required=True)
    commands.add_parser("questions", help="list the six exact offline question examples")
    catalog = commands.add_parser("schema", help="show the schema and dataset provenance")
    catalog.add_argument("--db", type=Path, required=True)
    query = commands.add_parser("query", help="run a constrained read-only SELECT")
    query.add_argument("--db", type=Path, required=True)
    query.add_argument("--sql", required=True)
    query.add_argument("--output", type=Path)
    ask = commands.add_parser("ask", help="plan a question and save its execution evidence")
    ask.add_argument("question")
    ask.add_argument("--db", type=Path, required=True)
    ask.add_argument("--planner", choices=["offline_rules", "ollama"], default="offline_rules")
    ask.add_argument("--model", help="installed local Ollama model name; required for --planner ollama")
    ask.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    ask.add_argument("--output", type=Path, default=Path("artifacts/answer.json"))
    evaluate = commands.add_parser("evaluate", help="run hand-calculated fixtures and rejection cases")
    evaluate.add_argument("--output", type=Path, default=Path("artifacts/evaluation.json"))
    verify = commands.add_parser("verify", help="replay a saved answer and compare its SQL results/data fingerprint")
    verify.add_argument("--db", type=Path, required=True)
    verify.add_argument("--answer", type=Path, required=True)
    server = commands.add_parser("serve", help="start the local MCP v2 stdio server")
    server.add_argument("--db", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from .warehouse import create_demo
            _emit(create_demo(args.db, seed=args.seed))
        elif args.command == "import-csv":
            from .warehouse import import_csv
            _emit(import_csv(args.csv, args.db))
        elif args.command == "questions":
            from .planning import CATALOG
            _emit({"mode": "offline_rules", "questions": [entry["question"] for entry in CATALOG]})
        elif args.command in {"schema", "query"}:
            from .engine import QueryEngine
            engine = QueryEngine(args.db)
            if args.command == "schema":
                _emit(engine.schema())
            else:
                _emit(engine.query(args.sql), args.output)
        elif args.command == "ask":
            from .answers import answer_question, render_markdown, write_bundle
            if args.planner == "offline_rules" and args.model:
                raise ValueError("--model requires --planner ollama")
            bundle = answer_question(args.db, args.question, planner=args.planner, model=args.model, base_url=args.ollama_url)
            write_bundle(bundle, args.output)
            print(render_markdown(bundle))
            print(f"JSON evidence: {args.output}")
        elif args.command == "evaluate":
            from .evaluation import evaluate
            report = evaluate()
            _emit(report, args.output)
            return 0 if report["all_passed"] else 1
        elif args.command == "verify":
            from .answers import verify_bundle
            verification = verify_bundle(json.loads(args.answer.read_text(encoding="utf-8")), args.db)
            _emit(verification)
            return 0 if verification["verified"] else 1
        elif args.command == "serve":
            from .mcp_server import create_server
            create_server(args.db).run(transport="stdio")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0

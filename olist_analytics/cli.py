"""Command-line entry point; importing this module never reads or writes data."""

import argparse
import json

from .data import load_tables, prepare_data
from .demo import DEMO_AS_OF, demo_tables


def main(argv=None):
    parser = argparse.ArgumentParser(description="Olist sales + RFM + cohort retention, with offline demo.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="use deterministic SYNTHETIC data, not real Olist records")
    source.add_argument("--data-dir", help="directory containing the four Olist CSV files")
    parser.add_argument("--output", default="reports/latest", help="output directory (default: reports/latest)")
    parser.add_argument("--as-of", help="exclusive observation end, e.g. 2018-09-01; must reflect source coverage")
    parser.add_argument("--seed", type=int, default=42, help="synthetic demo random seed (default: 42)")
    args = parser.parse_args(argv)
    try:
        tables = demo_tables(args.seed) if args.demo else load_tables(args.data_dir)
        cutoff = args.as_of or (DEMO_AS_OF if args.demo else None)
        items, quality, observation_end = prepare_data(tables, as_of=cutoff)
        quality["observation_end_origin"] = "explicit_or_demo_contract" if cutoff else "inferred_next_day_after_last_order"
        quality["coverage_note"] = "An absence of orders does not prove complete source coverage; verify exports before interpreting zero retention."
        from .report import write_report

        summary = write_report(items, quality, observation_end, args.output,
                               "synthetic_demo" if args.demo else "user_supplied_olist_csv")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print("SYNTHETIC DEMO — not actual Olist business results" if args.demo else "Olist CSV analysis")
    print(json.dumps(summary["metrics"], ensure_ascii=False, indent=2, allow_nan=False))
    print(f"Report: {args.output}/index.html")
    return 0

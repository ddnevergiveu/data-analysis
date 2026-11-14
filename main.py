"""Backward-compatible script entry; use --demo or --data-dir."""
from olist_analytics.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

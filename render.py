#!/usr/bin/env python3
import argparse
import os
import re
import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent / "sql"

REQUIRED = ["BILLING_TABLE", "AUDIT_DATASET", "OUT_DATASET", "PROJECT_ID"]
DEFAULTS = {
    "AUDIT_TABLE": "cloudaudit_googleapis_com_data_access_*",
    "START_DATE": "2025-01-01",
    "TIMEZONE": "UTC",
}
FLAGS = {
    "BILLING_TABLE": "--billing-table",
    "AUDIT_DATASET": "--audit-dataset",
    "AUDIT_TABLE": "--audit-table",
    "OUT_DATASET": "--out-dataset",
    "PROJECT_ID": "--project-id",
    "START_DATE": "--start-date",
    "TIMEZONE": "--timezone",
}
HELP = {
    "BILLING_TABLE": "detailed billing export table, project.dataset.table",
    "AUDIT_DATASET": "dataset the log sink writes to, project.dataset",
    "AUDIT_TABLE": "audit table name; use cloudaudit_googleapis_com_data_access for partitioned tables",
    "OUT_DATASET": "dataset for the output tables, project.dataset",
    "PROJECT_ID": "project whose Vertex AI usage to report",
    "START_DATE": "first day to include, YYYY-MM-DD (the day audit logs were turned on)",
    "TIMEZONE": "time zone used to cut days, such as UTC or America/New_York",
}
PLACEHOLDER = re.compile(r"\$\{([A-Z_]+)\}")


def render(text, values):
    missing = sorted({m for m in PLACEHOLDER.findall(text) if m not in values})
    if missing:
        raise KeyError("no value for: " + ", ".join(missing))
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def leftover(text):
    return PLACEHOLDER.findall(text)


def sql_files():
    return sorted(SQL_DIR.glob("*.sql"))


def resolve_values(args):
    values = dict(DEFAULTS)
    for name in list(DEFAULTS) + REQUIRED:
        value = getattr(args, name.lower()) or os.environ.get(name)
        if value:
            values[name] = value
    absent = [n for n in REQUIRED if n not in values]
    if absent:
        raise SystemExit("missing: " + ", ".join(f"{FLAGS[n]} or ${n}" for n in absent))
    return values


def build_parser():
    p = argparse.ArgumentParser(description="Fill the placeholders in sql/*.sql.")
    for name, flag in FLAGS.items():
        p.add_argument(flag, dest=name.lower(), help=f"{HELP[name]} (env {name})")
    p.add_argument("--out", help="write one file per query into this folder instead of printing")
    p.add_argument("--only", help="render only files whose name contains this text, such as 03")
    p.add_argument("--dry-run", action="store_true", help="print a bq dry-run command for each query")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    values = resolve_values(args)
    files = [f for f in sql_files() if not args.only or args.only in f.name]
    if not files:
        raise SystemExit("no queries matched")
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        text = render(f.read_text(), values)
        if leftover(text):
            raise SystemExit(f"{f.name}: unfilled placeholders")
        if out_dir:
            target = out_dir / f.name
            target.write_text(text)
            print(f"wrote {target}")
            if args.dry_run:
                print(f"  bq query --use_legacy_sql=false --dry_run < {target}")
        else:
            print(f"-- {f.name}")
            print(text)
            if args.dry_run:
                print(f"-- check: python3 render.py --only {f.name[:2]} | bq query --use_legacy_sql=false --dry_run")
    return 0


if __name__ == "__main__":
    sys.exit(main())

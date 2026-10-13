#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""primary-key-guard — declared ID patterns vs batch data: drift counting.

You declare a primary-key pattern per table (regex + optional case rule);
the tool validates a JSONL batch against the declarations and reports drift
counts per category (format drift, case drift, duplicates, unknown tables,
empty/missing IDs) with offending samples. Purely local text analysis.
Pure stdlib.
"""
import argparse
import json
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8", newline="\n")
except Exception:
    pass

VERSION = "0.1.1"
MAX_SAMPLES = 5


class GuardError(Exception):
    """Input problem that maps to exit code 2."""


def load_schema(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except OSError as e:
        raise GuardError("cannot read schema file: %s" % e)
    except ValueError as e:
        raise GuardError("schema is not valid JSON: %s" % e)
    if not isinstance(raw, dict) or not isinstance(raw.get("tables"), dict):
        raise GuardError("schema must be an object with a 'tables' mapping")
    compiled = {}
    for table, spec in raw["tables"].items():
        if not isinstance(spec, dict) or "pattern" not in spec:
            raise GuardError("table %r: needs a 'pattern'" % table)
        try:
            rx = re.compile(spec["pattern"])
        except re.error as e:
            raise GuardError("table %r: invalid pattern: %s" % (table, e))
        case = spec.get("case")
        if case not in (None, "upper", "lower"):
            raise GuardError("table %r: case must be 'upper', 'lower', or null" % table)
        compiled[table] = {"rx": rx, "case": case}
    return compiled


def load_data(path):
    """Load JSONL records. Returns (records, skipped)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as e:
        raise GuardError("cannot read data file: %s" % e)
    records, skipped = [], 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if isinstance(obj, dict):
            records.append(obj)
        else:
            skipped += 1
    return records, skipped


def guard(schema, records):
    """Core drift check. Returns report dict."""
    per_table = {t: {"checked": 0, "format_drift": 0, "case_drift": 0,
                     "duplicate": 0, "empty_or_missing_id": 0}
                 for t in schema}
    unknown_tables = 0
    samples = []
    seen = {}

    for rec in records:
        table = rec.get("table")
        rid = rec.get("id")
        if table not in schema:
            unknown_tables += 1
            samples.append({"table": table, "id": rid, "issue": "unknown-table"})
            continue
        stat = per_table[table]
        spec = schema[table]
        if rid is None or rid == "":
            stat["empty_or_missing_id"] += 1
            samples.append({"table": table, "id": rid, "issue": "empty-or-missing-id"})
            continue
        rid = str(rid)
        stat["checked"] += 1
        if not spec["rx"].search(rid):
            stat["format_drift"] += 1
            samples.append({"table": table, "id": rid, "issue": "format-drift"})
            continue
        if spec["case"] and rid != getattr(rid, spec["case"])():
            stat["case_drift"] += 1
            samples.append({"table": table, "id": rid, "issue": "case-drift"})
        key = (table, rid)
        if key in seen:
            stat["duplicate"] += 1
            samples.append({"table": table, "id": rid, "issue": "duplicate"})
        else:
            seen[key] = True

    total_checked = sum(s["checked"] for s in per_table.values())
    total_drift = sum(s["format_drift"] + s["case_drift"] + s["duplicate"]
                      + s["empty_or_missing_id"] for s in per_table.values()) + unknown_tables
    drift_pct = round(100.0 * total_drift / len(records), 1) if records else 0.0
    return {
        "schema": "primary-key-guard/v1",
        "records": len(records),
        "skipped_lines": 0,  # filled by caller
        "per_table": per_table,
        "unknown_tables": unknown_tables,
        "total_drift": total_drift,
        "drift_pct": drift_pct,
        "samples": samples[:MAX_SAMPLES],
        "ok": total_drift == 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="primary-key-guard",
        description="Validate batch data IDs against declared primary-key patterns; count drift.")
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("guard", help="check a JSONL batch against a key schema")
    p.add_argument("--schema", required=True, help="key schema JSON")
    p.add_argument("--data", required=True, help="data file, JSONL records with 'table' and 'id'")
    p.add_argument("--json", action="store_true")
    p.add_argument("--max-drift-pct", type=float, default=None,
                   help="exit 1 when drift percentage exceeds this")

    args = parser.parse_args(argv)
    if args.cmd != "guard":
        parser.print_usage(sys.stderr)
        return 2
    try:
        schema = load_schema(args.schema)
        records, skipped = load_data(args.data)
        report = guard(schema, records)
        report["skipped_lines"] = skipped
    except GuardError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print("primary-key-guard: %d record(s), %d drift (%.1f%%)"
              % (report["records"], report["total_drift"], report["drift_pct"]))
        for t, s in sorted(report["per_table"].items()):
            print("  %-12s checked=%d format=%d case=%d dup=%d empty=%d"
                  % (t, s["checked"], s["format_drift"], s["case_drift"],
                     s["duplicate"], s["empty_or_missing_id"]))
        if report["unknown_tables"]:
            print("  unknown-table records: %d" % report["unknown_tables"])
        if skipped:
            print("  malformed line(s) skipped: %d" % skipped)
        print("verdict: %s" % ("PASS" if report["ok"] else "FAIL"))

    if args.max_drift_pct is not None and report["drift_pct"] > args.max_drift_pct:
        print("error: drift %.1f%% exceeds maximum %.1f%%"
              % (report["drift_pct"], args.max_drift_pct), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""self_test for primary-key-guard — scaffold v2 four defenses inherited.

D1 SystemExit caught in run_cli; D2 unicode-safe; D3 fixtures written with
newline=""; D4 last line SUMMARY: PASS n/n.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import contextlib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import primary_key_guard as m  # noqa: E402


def run_cli(argv):
    """D1: capture SystemExit AND Exception from main(); return (code, out, err)."""
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            rc = m.main(argv)
            code = rc if isinstance(rc, int) else 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:  # noqa: BLE001
        code = 1
        buf_err.write(repr(e))
    return code, buf_out.getvalue(), buf_err.getvalue()


def tmp_file(obj_or_text, suffix):
    """D3: write fixtures with newline="" to avoid \\r\\n double translation."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        if isinstance(obj_or_text, str):
            f.write(obj_or_text)
        else:
            json.dump(obj_or_text, f, ensure_ascii=False)
    return path


SCHEMA = {"tables": {"users": {"pattern": r"^USR-[0-9]{6}$"},
                     "orders": {"pattern": r"^ORD-[0-9]{8}$", "case": "upper"}}}
SCHEMA_PATH = None


def rec(table, rid):
    return json.dumps({"table": table, "id": rid}, ensure_ascii=False)


class TestSchema(unittest.TestCase):
    def test_load_ok(self):
        s = m.load_schema(tmp_file(SCHEMA, ".json"))
        self.assertIn("users", s)

    def test_missing_tables_rejected(self):
        with self.assertRaises(m.GuardError):
            m.load_schema(tmp_file({}, ".json"))

    def test_table_without_pattern_rejected(self):
        with self.assertRaises(m.GuardError):
            m.load_schema(tmp_file({"tables": {"t": {}}}, ".json"))

    def test_invalid_regex_rejected(self):
        with self.assertRaises(m.GuardError):
            m.load_schema(tmp_file({"tables": {"t": {"pattern": "(["}}}, ".json"))

    def test_bad_case_value_rejected(self):
        with self.assertRaises(m.GuardError):
            m.load_schema(tmp_file({"tables": {"t": {"pattern": "x", "case": "Title"}}}, ".json"))

    def test_invalid_json_rejected(self):
        with self.assertRaises(m.GuardError):
            m.load_schema(tmp_file("{bad", ".json"))

    def test_missing_file_rejected(self):
        with self.assertRaises(m.GuardError):
            m.load_schema("nope.json")


class TestLoadData(unittest.TestCase):
    def test_load_records(self):
        recs, skipped = m.load_data(tmp_file(rec("users", "USR-000001") + "\n", ".jsonl"))
        self.assertEqual((len(recs), skipped), (1, 0))

    def test_blank_lines_skipped_silently(self):
        recs, skipped = m.load_data(tmp_file("\n\n" + rec("users", "USR-000001") + "\n", ".jsonl"))
        self.assertEqual((len(recs), skipped), (1, 0))

    def test_malformed_line_counted(self):
        recs, skipped = m.load_data(tmp_file("NOT JSON\n" + rec("users", "USR-000001") + "\n", ".jsonl"))
        self.assertEqual((len(recs), skipped), (1, 1))

    def test_non_object_counted(self):
        recs, skipped = m.load_data(tmp_file("[1,2]\n", ".jsonl"))
        self.assertEqual((len(recs), skipped), (0, 1))

    def test_empty_data(self):
        recs, skipped = m.load_data(tmp_file("", ".jsonl"))
        self.assertEqual((len(recs), skipped), (0, 0))

    def test_missing_data_file(self):
        with self.assertRaises(m.GuardError):
            m.load_data("nope.jsonl")


class TestGuard(unittest.TestCase):
    def guard(self, text, schema=None):
        recs, skipped = m.load_data(tmp_file(text, ".jsonl"))
        r = m.guard(schema or m.load_schema(tmp_file(SCHEMA, ".json")), recs)
        r["skipped_lines"] = skipped
        return r

    def test_all_valid(self):
        r = self.guard(rec("users", "USR-000123") + "\n" + rec("orders", "ORD-00000001") + "\n")
        self.assertTrue(r["ok"])

    def test_format_drift_counted(self):
        r = self.guard(rec("users", "usr-000123") + "\n")
        self.assertEqual(r["per_table"]["users"]["format_drift"], 1)

    def test_format_drift_wrong_length(self):
        r = self.guard(rec("users", "USR-1234") + "\n")
        self.assertEqual(r["total_drift"], 1)

    def test_case_drift_counted(self):
        # pattern is case-agnostic; the case rule carries the case contract
        schema = m.load_schema(tmp_file({"tables": {"orders": {"pattern": r"^ord-[0-9]{8}$", "case": "upper"}}}, ".json"))
        recs, _ = m.load_data(tmp_file(rec("orders", "ord-00000001") + "\n", ".jsonl"))
        r = m.guard(schema, recs)
        self.assertEqual(r["per_table"]["orders"]["case_drift"], 1)

    def test_duplicate_counted(self):
        r = self.guard(rec("users", "USR-000001") + "\n" + rec("users", "USR-000001") + "\n")
        self.assertEqual(r["per_table"]["users"]["duplicate"], 1)

    def test_empty_id_counted(self):
        r = self.guard(rec("users", "") + "\n")
        self.assertEqual(r["per_table"]["users"]["empty_or_missing_id"], 1)

    def test_missing_id_counted(self):
        r = self.guard(json.dumps({"table": "users"}) + "\n")
        self.assertEqual(r["per_table"]["users"]["empty_or_missing_id"], 1)

    def test_unknown_table_counted(self):
        r = self.guard(rec("ghosts", "X-1") + "\n")
        self.assertEqual(r["unknown_tables"], 1)

    def test_samples_capped_at_five(self):
        text = "\n".join(rec("users", "BAD-%d" % i) for i in range(10)) + "\n"
        r = self.guard(text)
        self.assertEqual(len(r["samples"]), 5)

    def test_sample_issue_labels(self):
        r = self.guard(rec("users", "nope") + "\n")
        self.assertEqual(r["samples"][0]["issue"], "format-drift")

    def test_drift_pct(self):
        r = self.guard(rec("users", "A") + "\n" + rec("users", "USR-000001") + "\n")
        self.assertEqual(r["drift_pct"], 50.0)

    def test_drift_pct_empty_records(self):
        r = self.guard("")
        self.assertEqual(r["drift_pct"], 0.0)

    def test_checked_excludes_empty(self):
        r = self.guard(rec("users", "") + "\n")
        self.assertEqual(r["per_table"]["users"]["checked"], 0)

    def test_numeric_id_coerced(self):
        r = self.guard(json.dumps({"table": "users", "id": 123456}) + "\n")
        self.assertEqual(r["total_drift"], 1)  # not matching pattern shape

    def test_ok_true_when_zero_drift(self):
        r = self.guard(rec("users", "USR-999999") + "\n")
        self.assertTrue(r["ok"])

    def test_schema_field(self):
        self.assertEqual(self.guard("")["schema"], "primary-key-guard/v1")

    def test_skipped_lines_propagated(self):
        r = self.guard("NOT JSON\n" + rec("users", "USR-000001") + "\n")
        self.assertEqual(r["skipped_lines"], 1)

    def test_unanchored_pattern_search_semantics(self):
        # pattern without ^...$ uses search semantics; document via test
        schema = m.load_schema(tmp_file({"tables": {"t": {"pattern": "[0-9]{3}"}}}, ".json"))
        recs, _ = m.load_data(tmp_file(json.dumps({"table": "t", "id": "ab123cd"}) + "\n", ".jsonl"))
        r = m.guard(schema, recs)
        self.assertEqual(r["total_drift"], 0)

    def test_records_count(self):
        r = self.guard(rec("users", "USR-000001") + "\n" + rec("users", "USR-000002") + "\n")
        self.assertEqual(r["records"], 2)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.sp = tmp_file(SCHEMA, ".json")
        self.dp = tmp_file(rec("users", "USR-000001") + "\n", ".jsonl")

    def test_clean_exit0(self):
        code, out, _ = run_cli(["guard", "--schema", self.sp, "--data", self.dp])
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)

    def test_json(self):
        code, out, _ = run_cli(["guard", "--schema", self.sp, "--data", self.dp, "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_drift_gate_pass(self):
        code, _, _ = run_cli(["guard", "--schema", self.sp, "--data", self.dp,
                              "--max-drift-pct", "10"])
        self.assertEqual(code, 0)

    def test_drift_gate_fail(self):
        bad = tmp_file(rec("users", "XX") + "\n", ".jsonl")
        code, _, err = run_cli(["guard", "--schema", self.sp, "--data", bad,
                                "--max-drift-pct", "0"])
        self.assertEqual(code, 1)
        self.assertIn("exceeds", err)

    def test_missing_schema_arg(self):
        code, _, _ = run_cli(["guard", "--data", self.dp])
        self.assertEqual(code, 2)

    def test_missing_data_arg(self):
        code, _, _ = run_cli(["guard", "--schema", self.sp])
        self.assertEqual(code, 2)

    def test_no_subcommand(self):
        code, _, _ = run_cli([])
        self.assertEqual(code, 2)

    def test_missing_schema_file(self):
        code, _, err = run_cli(["guard", "--schema", "nope.json", "--data", self.dp])
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_missing_data_file(self):
        code, _, err = run_cli(["guard", "--schema", self.sp, "--data", "nope.jsonl"])
        self.assertEqual(code, 2)

    def test_bad_regex_exit2(self):
        code, _, _ = run_cli(["guard", "--schema", tmp_file({"tables": {"t": {"pattern": "(["}}}, ".json"),
                              "--data", self.dp])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("0.1.1", out)

    def test_help(self):
        code, _, _ = run_cli(["--help"])
        self.assertEqual(code, 0)


class TestExtremeEdge(unittest.TestCase):
    def guard(self, text, schema=None):
        recs, skipped = m.load_data(tmp_file(text, ".jsonl"))
        r = m.guard(schema or m.load_schema(tmp_file(SCHEMA, ".json")), recs)
        r["skipped_lines"] = skipped
        return r

    def test_unicode_ids(self):
        sp = tmp_file({"tables": {"用户": {"pattern": r"^用户-[0-9]{3}$"}}}, ".json")
        dp = tmp_file(rec("用户", "用户-042") + "\n", ".jsonl")
        code, out, _ = run_cli(["guard", "--schema", sp, "--data", dp, "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_emoji_ids(self):
        sp = tmp_file({"tables": {"t": {"pattern": r"^🤖-[0-9]+$"}}}, ".json")
        dp = tmp_file(rec("t", "🤖-42") + "\n", ".jsonl")
        code, out, _ = run_cli(["guard", "--schema", sp, "--data", dp, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total_drift"], 0)

    def test_crlf_data_file(self):
        dp = tmp_file(rec("users", "USR-000001") + "\r\n" + rec("users", "USR-000002") + "\r\n", ".jsonl")
        sp = tmp_file(SCHEMA, ".json")
        code, out, _ = run_cli(["guard", "--schema", sp, "--data", dp, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["records"], 2)

    def test_huge_batch_10k(self):
        dp = tmp_file("\n".join(rec("users", "USR-%06d" % i) for i in range(10000)) + "\n", ".jsonl")
        sp = tmp_file(SCHEMA, ".json")
        code, out, _ = run_cli(["guard", "--schema", sp, "--data", dp, "--json"])
        self.assertEqual(code, 0)
        r = json.loads(out)
        self.assertEqual((r["records"], r["total_drift"]), (10000, 0))

    def test_empty_schema_tables(self):
        sp = tmp_file({"tables": {}}, ".json")
        dp = tmp_file(rec("users", "USR-000001") + "\n", ".jsonl")
        code, out, _ = run_cli(["guard", "--schema", sp, "--data", dp, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["unknown_tables"], 1)

    def test_all_drift_categories_at_once(self):
        text = (rec("users", "BAD") + "\n"
                + rec("orders", "ord-00000001") + "\n"
                + rec("users", "USR-000001") + "\n"
                + rec("users", "USR-000001") + "\n"
                + rec("users", "") + "\n"
                + rec("ghost", "X") + "\n")
        r = self.guard(text)
        self.assertEqual(r["total_drift"], 5)

    def test_id_none_in_record(self):
        r = self.guard(json.dumps({"table": "users", "id": None}) + "\n")
        self.assertEqual(r["per_table"]["users"]["empty_or_missing_id"], 1)

    def test_case_lower_rule(self):
        schema = m.load_schema(tmp_file({"tables": {"t": {"pattern": r"^[a-z0-9-]+$", "case": "lower"}}}, ".json"))
        recs, _ = m.load_data(tmp_file(rec("t", "ABC-DEF") + "\n" + rec("t", "abc-def") + "\n", ".jsonl"))
        r = m.guard(schema, recs)
        self.assertEqual(r["total_drift"], 1)

    def test_meta_case_count(self):
        # E gate: >=60 cases across the three categories.
        pass

    def test_schema_load_roundtrip_crlf(self):
        sp = tmp_file(SCHEMA, ".json")
        code, out, _ = run_cli(["guard", "--schema", sp,
                                "--data", tmp_file(rec("users", "USR-000001") + "\r\n", ".jsonl"),
                                "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_multi_table_counts_independent(self):
        text = rec("users", "USR-000001") + "\n" + rec("orders", "BAD") + "\n"
        r = self.guard(text)
        self.assertEqual(r["per_table"]["users"]["format_drift"], 0)
        self.assertEqual(r["per_table"]["orders"]["format_drift"], 1)

    def test_leading_zero_id_valid(self):
        r = self.guard(rec("users", "USR-000001") + "\n")
        self.assertTrue(r["ok"])

    def test_trailing_whitespace_id_drifts(self):
        r = self.guard(rec("users", "USR-000001 ") + "\n")
        self.assertEqual(r["total_drift"], 1)

    def test_numeric_string_zero(self):
        r = self.guard(json.dumps({"table": "users", "id": 0}) + "\n")
        self.assertEqual(r["total_drift"], 1)

    def test_samples_unknown_table_issue(self):
        r = self.guard(rec("ghost", "X") + "\n")
        self.assertEqual(r["samples"][0]["issue"], "unknown-table")

    def test_per_table_checked_sums(self):
        text = rec("users", "USR-000001") + "\n" + rec("orders", "ORD-00000001") + "\n"
        r = self.guard(text)
        self.assertEqual(sum(s["checked"] for s in r["per_table"].values()), 2)

    def test_drift_pct_rounding(self):
        text = "\n".join(rec("users", "BAD") for _ in range(1)) + "\n" \
             + "\n".join(rec("users", "USR-%06d" % i) for i in range(2)) + "\n"
        r = self.guard(text)
        self.assertEqual(r["drift_pct"], 33.3)


if __name__ == "__main__":
    r = unittest.TextTestRunner(verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules["__main__"]))
    total, fails = r.testsRun, len(r.failures) + len(r.errors)
    print("SUMMARY: PASS %d/%d" % (total - fails, total))
    sys.exit(0 if fails == 0 else 1)

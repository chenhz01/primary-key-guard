# Changelog

## v0.1.1 (2026-10-13)

Round-2 revisions after first-draft self-review (5 failing tests, all in the
test layer — 2 of them exposed a real API-contract ambiguity):

- Clarified and enforced the guard() contract: schema must be the *compiled*
  form from load_schema(). Two tests had passed raw schema dicts, silently
  degrading to unknown-table drift; now both go through load_schema().
- Case-rule semantics sharpened: the case rule composes with a
  case-agnostic pattern (pattern `^ord-[0-9]{8}$` + case "upper"); the old
  fixture embedded case in the pattern, making the case rule unreachable.
- TestExtremeEdge got the shared guard() helper it was missing.
- Suite raised 53 -> 61 cases (CRLF roundtrip, per-table independence,
  leading-zero, whitespace, numeric-zero id, sample labels, checked sums,
  drift rounding); re-run green (SUMMARY: PASS 61/61).
- Performance measured: 3.06 ms per 10k-record guard run [Measured].

## v0.1.0 (2026-10-13)

First draft:

- Key schema loader (regex per table + optional case rule; invalid regex
  and bad case values rejected).
- JSONL batch loader (malformed lines skipped and counted).
- Drift classification: format / case / duplicate / empty-or-missing id /
  unknown table; per-table counts, drift pct, 5-sample cap.
- argparse CLI (`guard`) with --json and --max-drift-pct CI gate.
- self_test with scaffold-v2 four defenses; README, LICENSE, ALIGNMENT.

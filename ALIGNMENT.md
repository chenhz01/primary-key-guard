# ALIGNMENT — primary-key-guard

Round R14, rubric v4.0 (E/F graded). Local-only draft: no git remote, no push, no repo creation.
Date: 2026-10-13.

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Runnable Python, pure stdlib | PASS | primary_key_guard.py imports only argparse/json/re/sys |
| 2 | argparse CLI | PASS | `guard` with `--schema/--data/--json/--max-drift-pct`; usage errors exit 2, drift gate exit 1 |
| 3 | self_test inherits scaffold-v2 four defenses | PASS | D1 SystemExit+Exception in run_cli (tested); D2 unicode ids (CJK/emoji tables+ids, tested); D3 fixtures newline="" via tmp_file (tested, CRLF case); D4 last line SUMMARY |
| 4 | E gate >=60 cases, 3 categories | PASS | SUMMARY: PASS 61/61 — TestSchema/TestLoadData/TestGuard (functional), TestCli (exception), TestExtremeEdge (10k batch/unicode/empty/all-drift) |
| 5 | SUMMARY last-line contract | PASS | final line `SUMMARY: PASS 61/61` |
| 6 | README English, <=60-word lead | PASS | README.md opening paragraph is 60 words |
| 7 | README Problem section | PASS | README.md '## Problem' |
| 8 | README How-it-works | PASS | README.md '## How it works' |
| 9 | README Quickstart with timing | PASS | README.md '## Quickstart' says "~1 min total" |
| 10 | why-not-X >=3 alternatives | PASS | README.md '## Why not X' lists 4 incl. real anchors johnmakridis/tax-id-validator and Vendic/hyva-checkout-eu-vat-id-format-validator |
| 11 | Performance [Measured] + repro command | PASS | README.md '## Performance': 3.06 ms per 10k-record run [Measured], repro one-liner |
| 12 | Minimal Fallback | PASS | README.md '## Minimal Fallback' (grep/uniq recipe) |
| 13 | Design Trade-offs | PASS | README.md '## Design Trade-offs' (4 entries) |
| 14 | Limits & Second-order Effects | PASS | README.md '## Limits & Second-order Effects' (4 entries) |
| 15 | FAQ incl When NOT to use | PASS | README.md '## FAQ' first item is 'When NOT to use this?' |
| 16 | Core Assumptions >=3 + confidence + as-of + hygiene | PASS | README.md '[Core Assumptions]' 4 items with confidence; 'As of 2026-10-13'; MIT LICENSE (zhengming contributors); CHANGELOG v0.1.0 -> v0.1.1; no secrets/real names; contact only hcac4735@agent.qq.com |
| + | Ethics/safety | PASS | Reads two local files; no network, no DB access, no execution |

Round-2 iteration (rule 99): self-review pinned down the compiled-schema
contract and case-rule composition semantics via failing tests; suite grown
53 -> 61; performance measured. See CHANGELOG v0.1.1.

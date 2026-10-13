# primary-key-guard

Catch primary-key drift before bad IDs reach your database. Declare one regex pattern (plus optional case rule) per table, point it at a JSONL batch, and get per-table drift counts — format, case, duplicates, unknown tables, empty IDs — with samples and a CI-gateable drift percentage. Pure Python, standard library only, zero network.

## Problem

ID formats drift the moment nobody is watching: someone concatenates without the prefix, a legacy importer writes lowercase, a queue retry duplicates a key. Each violation is individually harmless-looking and collectively expensive — they surface months later as foreign-key breaks, deduplication migrations, or "user not found" tickets. Schema-level constraints catch most of this at the database, but batch pipelines and data-migration jobs read files long before (or instead of) touching the schema. The format decision should be written down once and checked everywhere data is produced.

## How it works

1. **Declare** a key schema: `{"tables": {"users": {"pattern": "^USR-[0-9]{6}$", "case": "upper"}}}`. Patterns are Python regex (`search` semantics; anchor with `^...$` for full-match). The `case` rule is an additional contract for case-agnostic patterns.
2. **Load** the batch: JSONL records with `table` and `id` fields. Malformed lines are skipped and counted, never fatal.
3. **Classify** each record: format drift (regex), case drift (case rule), duplicates (per table+id), empty/missing id, unknown table (not declared in the schema).
4. **Report**: per-table counts, total drift, drift percentage, up to five offending samples, and an `ok` verdict. `--max-drift-pct` turns it into a CI gate (exit 1).

## Quickstart

```bash
# ~1 min total
python primary_key_guard.py guard --schema keys.json --data batch.jsonl
python primary_key_guard.py guard --schema keys.json --data batch.jsonl --json
python primary_key_guard.py guard --schema keys.json --data batch.jsonl --max-drift-pct 0.5
```

## Why not X

- **johnmakridis/tax-id-validator** — validates *tax ID* formats (VAT/GST/TIN/EIN) for 167 countries with curated per-country regexes, plus optional live VIES checks. Excellent for its domain, but the rule set is fixed to tax IDs; it cannot express your project's `USR-######` contract.
- **Vendic/hyva-checkout-eu-vat-id-format-validator** — same story, narrower still: EU VAT syntax inside a Magento 2 checkout.
- **Database schema constraints (CHECK/regex types)** — enforce at write time, which is right for the database but blind to files, exports, and migrations that never pass through it; also not portable across engines.
- **Ad-hoc pandas one-offs** — every script invents its own definition of "valid"; drift reporting is never consistent between runs.

## How this differs from tax-id-validator

The closest anchor, `johnmakridis/tax-id-validator`, per its README validates "the **format** of tax identification numbers (VAT, GST, TIN, EIN, and similar) for **167 of 245 ISO countries**" — a *fixed, curated* rule set for a well-known global ID family, shipped as an npm library, with optional live VIES cross-checking. This repo is the inversion of that: instead of shipping a fixed rule catalog, it makes **your** declarations the rule set — any pattern, any table names — and shifts the unit of work from "one ID" to "a whole batch", reporting drift counts, duplicates, and unknown-table records rather than a single boolean. Tax-ID-style catalogs and this tool compose well: extract IDs from your batch, keep the domain validators for semantics, use this for format drift at the pipeline level.

## Performance

[Measured] on Windows 10 Pro, Python 3.11, 2026-10-13. A 10,000-record batch guards in **3.06 ms per run** (0.061 s for 20 runs). Reproduce:

```bash
python -c "import time,primary_key_guard as m; s={'users':{'rx':__import__('re').compile(r'^USR-[0-9]{6}$'),'case':None}}; recs=[{'table':'users','id':'USR-%06d'%i} for i in range(10000)]; recs[500]['id']='BAD'; t0=time.perf_counter(); [m.guard(s,recs) for _ in range(20)]; print((time.perf_counter()-t0)*50)"
```

## Minimal Fallback

No Python? In any spreadsheet or `awk`: extract the id column, count rows not matching your pattern with `grep -vcE '^USR-[0-9]{6}$'`, and count duplicates with `sort | uniq -d`. Those two numbers are 80% of this tool's report.

## Design Trade-offs

- **Your regexes over a fixed ID catalog** — maximally general and dependency-free, but the schema author owns pattern quality (no per-country sanity checking).
- **Drift counting over fail-fast** — a batch run reports *everything* wrong instead of dying on the first bad record; more useful for triage, worse as a hard stream filter.
- **Samples capped at five** — keeps reports readable; full forensics belongs in the data pipeline, not the audit output.
- **JSONL-only input** — one trivially-parseable format over adapters for CSV/Parquet; converters are one line each in any pipeline.

## Limits & Second-order Effects

- Pattern quality is the single point of failure: an over-permissive declaration makes the guard useless while everything still "passes".
- `--max-drift-pct` gates can be gamed by shrinking batch size; gate on counts too for critical tables.
- Search semantics (unanchored patterns) can silently accept prefixed garbage; anchor patterns unless you mean it.
- Widespread gating may push teams to "fix" data by loosening declarations instead of repairing the producers.

## FAQ

**When NOT to use this?**
When IDs need *semantic* validation (checksums, country-specific tax formats) — use a domain validator for that and keep this for structural drift. Also not a replacement for database-level constraints on the write path.

**Why did my unanchored pattern accept extra characters?**
Patterns use `re.search`; write `^...$` when you mean full-string match.

**Is `case` needed if my pattern already encodes case?**
No — it exists for case-agnostic patterns where case is still a contract (e.g. `[A-Za-z]` pattern, upper rule).

**What happens to unknown tables?**
Counted as drift and sampled; an un-declared table is exactly the kind of thing you want surfaced.

## Core Assumptions

- [A1] ID formats are stable enough to express as one regex per table. Confidence: High.
- [A2] Batch/JSONL is the dominant interchange shape for pipeline data. Confidence: High; CSV converters are trivial.
- [A3] Drift percentage plus samples is actionable for triage. Confidence: High.
- [A4] Declared schemas live in files and can be versioned with the code that produces the data. Confidence: Medium — depends on team discipline.

Confidence in the mechanism: High. As of 2026-10-13.

## License

MIT — see [LICENSE](LICENSE). Contact: hcac4735@agent.qq.com

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 105 purpose-built AI-engineering tools across neglected niches.

Related tools: [slow-query-pattern-ledger](https://github.com/chenhz01/slow-query-pattern-ledger) · [baseline-drift-ledger](https://github.com/chenhz01/baseline-drift-ledger) · [etl-resume-spec](https://github.com/chenhz01/etl-resume-spec)

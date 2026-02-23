# Challenge #3 tools (Constraint Gauntlet)

A small, **best-effort** validator + PR scanner for the AI Village “Constraint Gauntlet” poem challenge.

These scripts are intended to help humans triage submissions quickly (e.g., catch obvious path mistakes, acrostic failures, syllable/rhyme issues). They will sometimes be wrong on edge cases.

## Files

- `validate_ch3.py` — validates a single markdown submission file.
- `scan_ch3_prs.py` — scans one or more GitHub PRs and runs `validate_ch3.py` against the canonical submission file in each PR.

## Requirements

- Python 3.10+
- GitHub CLI (`gh`) authenticated (for `scan_ch3_prs.py`)

Optional (improves syllable + rhyme accuracy):

```bash
pip install pronouncing
```

If `pronouncing` is not installed, the validator falls back to simple heuristics.

## Usage

### Validate a local submission

```bash
python3 tools/challenge_03/validate_ch3.py challenges/challenge-03-someuser.md --json
```

### Scan specific PRs

```bash
python3 tools/challenge_03/scan_ch3_prs.py 32 33 35
```

### Scan all open PRs (triage)

```bash
python3 tools/challenge_03/scan_ch3_prs.py --open --json > ch3_scan_report.json
```

## Notes / known limitations

- Semantics (“theme”, “must include weather/animal/instrument/...”) are based on keyword lists; authors can satisfy constraints without matching those keywords.
- Rhymes are based on CMU pronunciations when available. Some valid rhymes may not be recognized (and vice versa).
- Poem extraction searches for any 12-line window whose acrostic matches `VILLAGECODES`, preferring fenced code blocks.

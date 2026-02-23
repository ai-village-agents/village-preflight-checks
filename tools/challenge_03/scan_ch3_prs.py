#!/usr/bin/env python3
"""Scan Challenge #3 PRs in ai-village-agents/village-challenges.

This is a convenience wrapper around:
- `gh pr view --json ...` (to discover changed files and head ref)
- GitHub Contents API (raw accept) to fetch the canonical submission file
- `validate_ch3.py` to best-effort validate constraints

Examples:
  # Scan specific PRs:
  python3 scan_ch3_prs.py 32 33 35

  # Scan all open PRs:
  python3 scan_ch3_prs.py --open

  # Emit machine-readable JSON:
  python3 scan_ch3_prs.py --open --json > report.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from typing import Any

DEFAULT_REPO = "ai-village-agents/village-challenges"
CANON_RE = re.compile(r"^challenges/challenge-03-([a-z0-9-]+)\.md$")


def sh(cmd: list[str], *, input_text: str | None = None, timeout: int = 45) -> str:
    res = subprocess.run(cmd, input=input_text, text=True, capture_output=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\nstdout={res.stdout}\nstderr={res.stderr}")
    return res.stdout


def gh_json(args: list[str], timeout: int = 45) -> Any:
    out = sh(["gh"] + args, timeout=timeout)
    return json.loads(out)


def gh_raw_file(owner_repo: str, path: str, ref: str, timeout: int = 45) -> str:
    # Use contents API with raw accept.
    ref_q = urllib.parse.quote(ref, safe="")
    endpoint = f"/repos/{owner_repo}/contents/{path}?ref={ref_q}"
    return sh(["gh", "api", "-H", "Accept: application/vnd.github.raw", endpoint], timeout=timeout)


def list_open_prs(repo: str, limit: int = 200) -> list[int]:
    rows = gh_json(["pr", "list", "-R", repo, "--state", "open", "--limit", str(limit), "--json", "number"], timeout=60)
    return [int(r["number"]) for r in rows]


@dataclass
class PRReport:
    pr: int
    url: str
    title: str
    author: str
    head_ref: str
    head_repo: str
    canonical_files: list[str]
    other_changed: list[str]
    path_ok: bool
    mirror_suspected: bool
    poem_username: str | None
    validation_ok: bool | None
    failures: list[str]
    warnings: list[str]


def scan_pr(repo: str, n: int) -> PRReport:
    info = gh_json(
        [
            "pr",
            "view",
            str(n),
            "-R",
            repo,
            "--json",
            "number,url,title,state,author,headRefName,headRepository,headRepositoryOwner,files",
        ],
        timeout=60,
    )
    author = info["author"]["login"]
    head_ref = info["headRefName"]

    head_repo = (info.get("headRepository") or {}).get("nameWithOwner") or ""
    if not head_repo:
        owner = (info.get("headRepositoryOwner") or {}).get("login") or ""
        name = (info.get("headRepository") or {}).get("name") or ""
        if owner and name:
            head_repo = f"{owner}/{name}"
    if not head_repo:
        head_repo = repo

    files = [f["path"] for f in info.get("files", [])]
    canonical_files = [p for p in files if CANON_RE.match(p)]
    other_changed = [p for p in files if p not in canonical_files]

    mirror_suspected = info.get("title", "").lower().startswith("mirror")
    poem_username = None
    path_ok = False
    failures: list[str] = []
    warnings: list[str] = []
    validation_ok: bool | None = None

    if len(canonical_files) == 1:
        m = CANON_RE.match(canonical_files[0])
        poem_username = m.group(1) if m else None
        path_ok = True
        if poem_username and poem_username != author:
            if mirror_suspected:
                warnings.append(f"Filename slug ({poem_username}) != PR author ({author}); mirror suspected")
            else:
                warnings.append(f"Filename slug ({poem_username}) != PR author ({author})")
    elif len(canonical_files) == 0:
        failures.append("No canonical file challenges/challenge-03-<username>.md changed in this PR")
    else:
        failures.append(f"Multiple canonical files changed: {canonical_files}")

    if other_changed:
        warnings.append(
            f"Non-canonical files also changed ({len(other_changed)}): {', '.join(other_changed[:6])}" + (" ..." if len(other_changed) > 6 else "")
        )

    if canonical_files:
        path = canonical_files[0]
        try:
            md = gh_raw_file(head_repo, path, head_ref, timeout=60)
        except Exception as e:
            failures.append(f"Failed to fetch {path} from {head_repo}@{head_ref}: {e}")
            md = None

        if md is not None:
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md", encoding="utf-8") as tf:
                tf.write(md)
                tmp_path = tf.name
            try:
                tool_dir = os.path.dirname(__file__)
                validator = os.path.join(tool_dir, "validate_ch3.py")
                proc = subprocess.run([sys.executable, validator, tmp_path, "--json"], text=True, capture_output=True)
                try:
                    v = json.loads(proc.stdout)
                except Exception:
                    failures.append("Validator did not return JSON")
                    v = {"ok": False, "failures": ["validator_json"], "warnings": [proc.stderr], "details": {}}

                validation_ok = bool(v.get("ok"))
                for f in v.get("failures", []) or []:
                    failures.append(f"Poem: {f}")
                for w in v.get("warnings", []) or []:
                    warnings.append(f"Poem: {w}")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return PRReport(
        pr=n,
        url=info["url"],
        title=info["title"],
        author=author,
        head_ref=head_ref,
        head_repo=head_repo,
        canonical_files=canonical_files,
        other_changed=other_changed,
        path_ok=path_ok,
        mirror_suspected=mirror_suspected,
        poem_username=poem_username,
        validation_ok=validation_ok,
        failures=failures,
        warnings=warnings,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prs", nargs="*", type=int, help="PR numbers to scan")
    ap.add_argument("--open", action="store_true", help="Scan all open PRs (up to --limit)")
    ap.add_argument("--limit", type=int, default=200, help="Max open PRs to scan when using --open")
    ap.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo (owner/name)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    pr_numbers: list[int]
    if args.open:
        pr_numbers = list_open_prs(args.repo, limit=args.limit)
    else:
        pr_numbers = args.prs

    if not pr_numbers:
        ap.error("Provide PR numbers or use --open")

    reports: list[PRReport] = []
    for n in pr_numbers:
        reports.append(scan_pr(args.repo, n))

    if args.json:
        json.dump([r.__dict__ for r in reports], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    for r in reports:
        status = "PATH_OK" if r.path_ok else "PATH_BAD"
        poem = "OK" if r.validation_ok else ("FAIL" if r.validation_ok is False else "N/A")
        print(f"PR #{r.pr} {r.author}: {status}; poem={poem}")
        for f in r.failures:
            print("  -", f)
        for w in r.warnings[:8]:
            print("  *", w)
        if len(r.warnings) > 8:
            print(f"  * (+{len(r.warnings)-8} more warnings)")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

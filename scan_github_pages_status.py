#!/usr/bin/env python3
"""Scan GitHub org repositories for GitHub Pages status.

This is primarily useful for identifying repositories where Pages is not enabled.
Repo admin access (not necessarily org admin) is typically sufficient to enable
Pages; org policy can still block it.

The script reports:
- repo properties (archived/fork/default_branch)
- REST API `has_pages` flag
- optional `/pages` endpoint HTTP status and (when enabled) the published URL

Notes:
- `GET /repos/{owner}/{repo}/pages` returns 404 when Pages is not enabled.
  In some environments it may also return 404 due to org policy/permissions.
  Treat 404 as "not enabled or blocked".

Auth:
- If `GITHUB_TOKEN` is set, it will be used for authenticated requests.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional

from urllib import error, parse, request


DEFAULT_ORG = "ai-village-agents"
API_ROOT = "https://api.github.com"


@dataclass
class RepoPagesStatus:
    full_name: str
    html_url: str
    default_branch: str
    archived: bool
    fork: bool
    has_pages: bool
    remediation: str = ""
    pages_endpoint_status: Optional[int] = None
    pages_html_url: Optional[str] = None
    pages_build_type: Optional[str] = None
    pages_source_branch: Optional[str] = None
    pages_source_path: Optional[str] = None
    permissions_admin: Optional[bool] = None
    permissions_push: Optional[bool] = None
    permissions_pull: Optional[bool] = None
    permissions_maintain: Optional[bool] = None
    permissions_triage: Optional[bool] = None


class SimpleResponse:
    def __init__(self, *, status_code: int, text: str, json_data: Any, json_error: Optional[Exception] = None) -> None:
        self.status_code = status_code
        self.text = text
        self._json_data = json_data
        self._json_error = json_error

    def json(self) -> Any:
        if self._json_error:
            raise self._json_error
        return self._json_data


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Scan repositories in an org for GitHub Pages status (has_pages + optional /pages endpoint check)."
        )
    )
    p.add_argument(
        "org",
        nargs="?",
        default=DEFAULT_ORG,
        help=f"GitHub org to scan (default: {DEFAULT_ORG}).",
    )
    p.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived repositories.",
    )
    p.add_argument(
        "--include-forks",
        action="store_true",
        help="Include fork repositories.",
    )
    p.add_argument(
        "--check-pages-endpoint",
        action="store_true",
        help="Also GET /repos/{owner}/{repo}/pages for each repo.",
    )
    p.add_argument(
        "--out-json",
        help="Write full results to a JSON file.",
    )
    p.add_argument(
        "--format",
        choices=["table", "repos"],
        default="table",
        help="Output format: 'table' (default) or 'repos' (full_name + remediation for repos needing attention).",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Optional sleep (seconds) between per-repo API calls (default: 0).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optionally limit the number of repositories processed (default: no limit).",
    )
    return p.parse_args()


def build_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "scan_github_pages_status.py",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request_json(
    url: str,
    headers: Dict[str, str],
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
) -> "SimpleResponse":
    if params:
        query = parse.urlencode(params)
        separator = "&" if parse.urlparse(url).query else "?"
        url = f"{url}{separator}{query}"

    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            body_bytes = resp.read()
            encoding = resp.headers.get_content_charset() or "utf-8"
            text = body_bytes.decode(encoding, errors="replace")
    except error.HTTPError as exc:
        status_code = exc.code
        body_bytes = exc.read()
        encoding = exc.headers.get_content_charset() or "utf-8"
        text = body_bytes.decode(encoding, errors="replace")
    except error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc

    json_error: Optional[Exception] = None
    try:
        json_data: Any = json.loads(text) if text else None
    except ValueError as exc:
        json_data = None
        json_error = exc

    return SimpleResponse(status_code=status_code, text=text, json_data=json_data, json_error=json_error)


def list_org_repos(org: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    repos: List[Dict[str, Any]] = []
    page = 1
    while True:
        url = f"{API_ROOT}/orgs/{org}/repos"
        resp = request_json(url, headers, params={"per_page": 100, "page": page, "type": "all"})
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to list repos for org {org}: {resp.status_code} {resp.text}")
        batch = resp.json()
        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected response for org repos list: {type(batch)}")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def get_pages_endpoint(full_name: str, headers: Dict[str, str]) -> Dict[str, Any]:
    url = f"{API_ROOT}/repos/{full_name}/pages"
    resp = request_json(url, headers)
    out: Dict[str, Any] = {"status": resp.status_code}
    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if isinstance(data, dict):
            out["html_url"] = data.get("html_url")
            out["build_type"] = data.get("build_type")
            src = data.get("source")
            if isinstance(src, dict):
                out["source_branch"] = src.get("branch")
                out["source_path"] = src.get("path")
    return out


def _optional_bool(value: Any) -> Optional[bool]:
    return value if isinstance(value, bool) else None


def to_status(repo: Dict[str, Any], headers: Dict[str, str], *, check_pages: bool, sleep_s: float) -> RepoPagesStatus:
    full_name = repo.get("full_name") or ""
    status = RepoPagesStatus(
        full_name=full_name,
        html_url=repo.get("html_url") or "",
        default_branch=repo.get("default_branch") or "",
        archived=bool(repo.get("archived")),
        fork=bool(repo.get("fork")),
        has_pages=bool(repo.get("has_pages")),
    )

    permissions = repo.get("permissions")
    if isinstance(permissions, dict):
        status.permissions_admin = _optional_bool(permissions.get("admin"))
        status.permissions_push = _optional_bool(permissions.get("push"))
        status.permissions_pull = _optional_bool(permissions.get("pull"))
        status.permissions_maintain = _optional_bool(permissions.get("maintain"))
        status.permissions_triage = _optional_bool(permissions.get("triage"))

    if check_pages and full_name:
        info = get_pages_endpoint(full_name, headers)
        status.pages_endpoint_status = info.get("status")
        status.pages_html_url = info.get("html_url")
        status.pages_build_type = info.get("build_type")
        status.pages_source_branch = info.get("source_branch")
        status.pages_source_path = info.get("source_path")
        if sleep_s:
            time.sleep(sleep_s)

    # Remediation rules:
    # - If pages_endpoint_status == 200 OR has_pages is True: "ok"
    # - Else if pages_endpoint_status == 403: "blocked (403)..." with detail based on repo admin permission
    # - Else if permissions_admin is True: self-remediable (repo admin can enable Pages)
    # - Else if permissions_admin is False: needs-admin (no repo admin permission)
    # - Else (permissions missing): unknown (no permissions data; set GITHUB_TOKEN)
    remediation: str
    pages_status = status.pages_endpoint_status
    remediation = "unknown (no permissions data; set GITHUB_TOKEN)"

    if pages_status == 200 or status.has_pages:
        remediation = "ok"
    elif pages_status == 403:
        if status.permissions_admin is True:
            remediation = "blocked (403) though repo admin; org policy?"
        elif status.permissions_admin is False:
            remediation = "blocked (403); needs-admin"
        else:
            remediation = "blocked (403); unknown perms"
    elif status.permissions_admin is True:
        remediation = "self-remediable (repo admin can enable Pages)"
    elif status.permissions_admin is False:
        remediation = "needs-admin (no repo admin permission)"

    status.remediation = remediation
    return status


def print_table(statuses: Iterable[RepoPagesStatus]) -> None:
    rows: List[List[str]] = []
    header = [
        "repo",
        "remediation",
        "perm_admin",
        "has_pages",
        "pages_http",
        "archived",
        "fork",
        "default_branch",
        "pages_url",
    ]
    rows.append(header)

    for s in statuses:
        rows.append(
            [
                s.full_name,
                s.remediation,
                ""
                if s.permissions_admin is None
                else ("yes" if s.permissions_admin else "no"),
                "yes" if s.has_pages else "no",
                "" if s.pages_endpoint_status is None else str(s.pages_endpoint_status),
                "yes" if s.archived else "no",
                "yes" if s.fork else "no",
                s.default_branch,
                s.pages_html_url or "",
            ]
        )

    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    for idx, r in enumerate(rows):
        line = "  ".join(r[i].ljust(widths[i]) for i in range(len(header)))
        print(line)
        if idx == 0:
            print("  ".join("-" * widths[i] for i in range(len(header))))


def main() -> int:
    args = parse_args()

    if args.limit is not None and args.limit < 0:
        print("Error: --limit must be zero or a positive integer.", file=sys.stderr)
        return 2

    try:
        headers = build_headers()
        if not headers.get("Authorization"):
            print("Warning: GITHUB_TOKEN not set; proceeding unauthenticated (may be rate-limited).", file=sys.stderr)
        repos = list_org_repos(args.org, headers)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    filtered: List[Dict[str, Any]] = []
    for r in repos:
        if not args.include_archived and r.get("archived"):
            continue
        if not args.include_forks and r.get("fork"):
            continue
        filtered.append(r)

    if args.limit is not None:
        filtered = filtered[: args.limit]

    statuses: List[RepoPagesStatus] = []
    for r in filtered:
        statuses.append(to_status(r, headers, check_pages=args.check_pages_endpoint, sleep_s=args.sleep))

    if args.out_json:
        payload = {
            "org": args.org,
            "count": len(statuses),
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": [asdict(s) for s in statuses],
        }
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")

    if args.format == "table":
        print_table(statuses)
        return 0

    # format == repos
    for s in statuses:
        pages_status = s.pages_endpoint_status
        should_print = s.remediation != "ok" and (
            pages_status in (None, 404, 403) or not s.has_pages
        )
        if should_print:
            print(f"{s.full_name}\t{s.remediation}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

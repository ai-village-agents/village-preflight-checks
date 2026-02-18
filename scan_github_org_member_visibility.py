#!/usr/bin/env python3
"""Scan a GitHub org's members for "ghost" (non-public / 404) user accounts.

Problem
- Some GitHub user accounts appear to function when authenticated (can push/PR),
  but their public profile and REST user endpoint resolve as 404.
- When such an account authors PRs/issues, external observers can see links that
  appear "broken" (author profile 404; sometimes related UI elements degrade).

This script lists org members and checks whether each member's user record is
publicly resolvable via the REST API endpoint:
  GET https://api.github.com/users/{login}

Interpretation
- 200: user is publicly resolvable.
- 404: user is NOT publicly resolvable ("ghost" / deleted / hidden). Treat as a
  visibility anomaly worth mitigating.

Auth
- If GITHUB_TOKEN is set, it will be used for authenticated requests.
  (Note: for some ghost accounts, /users/{login} may still return 404 even when
  authenticated; that is the point of this check.)

Output
- Table (default) or just logins.
- Optional JSON output for automation.

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import error, parse, request


DEFAULT_ORG = "ai-village-agents"
API_ROOT = "https://api.github.com"
WEB_ROOT = "https://github.com"


@dataclass
class MemberVisibility:
    login: str
    user_api_status: int
    user_api_html_url: Optional[str] = None
    web_profile_status: Optional[int] = None


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
            "Scan a GitHub org's members and detect 'ghost' accounts whose public user API endpoint returns 404."
        )
    )
    p.add_argument(
        "org",
        nargs="?",
        default=DEFAULT_ORG,
        help=f"GitHub org to scan (default: {DEFAULT_ORG}).",
    )
    p.add_argument(
        "--check-web",
        action="store_true",
        help="Also probe https://github.com/{login} with a HEAD request (optional).",
    )
    p.add_argument(
        "--only-ghost",
        action="store_true",
        help="Only output members whose /users/{login} returns 404.",
    )
    p.add_argument(
        "--format",
        choices=["table", "logins"],
        default="table",
        help="Output format: 'table' (default) or 'logins' (one login per line).",
    )
    p.add_argument(
        "--out-json",
        help="Write results to a JSON file.",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Optional sleep (seconds) between per-member checks (default: 0).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optionally limit the number of members processed (default: no limit).",
    )
    return p.parse_args()


def build_headers(*, user_agent: str) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": user_agent,
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
) -> SimpleResponse:
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


def request_head_status(url: str, headers: Dict[str, str], *, timeout: int = 20) -> int:
    # Note: Some servers don't support HEAD perfectly; this is best-effort.
    req = request.Request(url, headers=headers, method="HEAD")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return int(resp.getcode())
    except error.HTTPError as exc:
        return int(exc.code)
    except error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def list_org_members(org: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    members: List[Dict[str, Any]] = []
    page = 1
    while True:
        url = f"{API_ROOT}/orgs/{org}/members"
        resp = request_json(url, headers, params={"per_page": 100, "page": page})
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to list members for org {org}: {resp.status_code} {resp.text}")
        batch = resp.json()
        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected response for org members list: {type(batch)}")
        if not batch:
            break
        members.extend(batch)
        page += 1
    return members


def check_member(login: str, headers_api: Dict[str, str], *, check_web: bool, headers_web: Dict[str, str]) -> MemberVisibility:
    user_url = f"{API_ROOT}/users/{login}"
    resp = request_json(user_url, headers_api)

    html_url: Optional[str] = None
    if resp.status_code == 200:
        try:
            data = resp.json()
        except Exception:
            data = None
        if isinstance(data, dict):
            v = data.get("html_url")
            if isinstance(v, str):
                html_url = v

    web_status: Optional[int] = None
    if check_web:
        web_status = request_head_status(f"{WEB_ROOT}/{login}", headers_web)

    return MemberVisibility(login=login, user_api_status=resp.status_code, user_api_html_url=html_url, web_profile_status=web_status)


def is_ghost(m: MemberVisibility) -> bool:
    return m.user_api_status == 404


def format_table(rows: List[MemberVisibility], *, only_ghost: bool, check_web: bool) -> str:
    display = [r for r in rows if (is_ghost(r) if only_ghost else True)]

    cols = [
        ("login", lambda r: r.login),
        ("user_api", lambda r: str(r.user_api_status)),
    ]
    if check_web:
        cols.append(("web", lambda r: "" if r.web_profile_status is None else str(r.web_profile_status)))
    cols.append(("html_url", lambda r: r.user_api_html_url or ""))

    widths = []
    for name, getter in cols:
        widths.append(max(len(name), *(len(getter(r)) for r in display)) if display else len(name))

    lines = []
    header = "  ".join(name.ljust(w) for (name, _), w in zip(cols, widths))
    lines.append(header)
    lines.append("  ".join("-" * w for w in widths))
    for r in display:
        lines.append("  ".join(getter(r).ljust(w) for (_, getter), w in zip(cols, widths)))
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    headers_api = build_headers(user_agent="scan_github_org_member_visibility.py")
    # For github.com HEAD probes, use a different UA and accept HTML.
    headers_web = {
        "User-Agent": "scan_github_org_member_visibility.py",
        "Accept": "text/html,application/xhtml+xml",
    }

    members = list_org_members(args.org, headers_api)
    logins = []
    for m in members:
        login = m.get("login")
        if isinstance(login, str) and login:
            logins.append(login)

    if args.limit is not None:
        logins = logins[: args.limit]

    results: List[MemberVisibility] = []
    for i, login in enumerate(logins, start=1):
        mv = check_member(login, headers_api, check_web=args.check_web, headers_web=headers_web)
        results.append(mv)
        if args.sleep:
            time.sleep(args.sleep)

    if args.out_json:
        payload = {
            "org": args.org,
            "checked": len(results),
            "ghost_count": sum(1 for r in results if is_ghost(r)),
            "check_web": bool(args.check_web),
            "members": [asdict(r) for r in results],
        }
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")

    if args.format == "logins":
        for r in results:
            if args.only_ghost and not is_ghost(r):
                continue
            print(r.login)
    else:
        print(format_table(results, only_ghost=args.only_ghost, check_web=args.check_web))
        checked = len(results)
        ghost = sum(1 for r in results if is_ghost(r))
        print("\nSummary:")
        print(f"- org: {args.org}")
        print(f"- members checked: {checked}")
        print(f"- ghost (/users/{{login}} == 404): {ghost}")
        if args.check_web:
            web_404 = sum(1 for r in results if r.web_profile_status == 404)
            print(f"- web 404 (HEAD https://github.com/{{login}}): {web_404}")

    # Exit status 1 if any ghost accounts found (useful in CI / preflight).
    return 1 if any(is_ghost(r) for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

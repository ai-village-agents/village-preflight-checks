#!/usr/bin/env python3
"""Merge a GitHub pull request via the REST API."""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, Optional

import requests


API_ROOT = "https://api.github.com"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge a GitHub pull request via the GitHub REST API."
    )
    parser.add_argument(
        "repository",
        help="Target repository in the form owner/name.",
    )
    parser.add_argument(
        "pull_request",
        type=int,
        help="Pull request number to merge.",
    )
    parser.add_argument(
        "--merge-method",
        choices=("merge", "squash", "rebase"),
        default="merge",
        help="Merge strategy to use. Defaults to 'merge'.",
    )
    parser.add_argument(
        "--commit-title",
        help="Optional merge commit title.",
    )
    parser.add_argument(
        "--commit-message",
        help="Optional merge commit message.",
    )
    return parser.parse_args(argv)


def ensure_repo_format(repo: str) -> str:
    cleaned = repo.strip()
    if cleaned.count("/") != 1:
        raise SystemExit("Repository must be in the format 'owner/name'.")
    return cleaned


def load_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Environment variable GITHUB_TOKEN must be set.")
    return token.strip()


def create_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "merge-pr-script",
        }
    )
    return session


def merge_pull_request(
    session: requests.Session,
    repo: str,
    pull_number: int,
    merge_method: str,
    commit_title: Optional[str],
    commit_message: Optional[str],
) -> Dict[str, Any]:
    url = f"{API_ROOT}/repos/{repo}/pulls/{pull_number}/merge"
    payload: Dict[str, str] = {"merge_method": merge_method}
    if commit_title:
        payload["commit_title"] = commit_title
    if commit_message:
        payload["commit_message"] = commit_message

    response = session.put(url, json=payload, timeout=15)
    if response.status_code == 405:
        message = response.json().get("message", "Merge not allowed.")
        raise SystemExit(f"Merge not allowed: {message}")
    if response.status_code == 409:
        message = response.json().get("message", "Merge conflict.")
        raise SystemExit(f"Merge conflict: {message}")
    if not response.ok:
        raise SystemExit(
            f"Failed to merge pull request: {response.status_code} {response.text}"
        )

    result = response.json()
    if not result.get("merged"):
        raise SystemExit(result.get("message", "Merge unsuccessful."))
    return result


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    repo = ensure_repo_format(args.repository)
    token = load_token()
    session = create_session(token)

    try:
        result = merge_pull_request(
            session=session,
            repo=repo,
            pull_number=args.pull_request,
            merge_method=args.merge_method,
            commit_title=args.commit_title,
            commit_message=args.commit_message,
        )
    except requests.RequestException as exc:
        raise SystemExit(f"Network error: {exc}") from exc

    sha = result.get("sha", "unknown")
    print(f"Pull request #{args.pull_request} merged successfully: {sha}")


if __name__ == "__main__":
    main()

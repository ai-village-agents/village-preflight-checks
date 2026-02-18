#!/usr/bin/env python3
"""Enable GitHub Pages for a repository via the REST API."""

import argparse
import os
import sys
from typing import Dict

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enable GitHub Pages for the given repository."
    )
    parser.add_argument(
        "repository",
        help="Target repository in the format 'owner/repo'.",
    )
    return parser.parse_args()


def build_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print(
            "Warning: GITHUB_TOKEN not set; proceeding with an unauthenticated request.",
            file=sys.stderr,
        )
    return headers


def validate_repository_format(repository: str) -> None:
    owner, sep, repo = repository.partition("/")
    if sep != "/" or not owner or not repo:
        raise ValueError("Repository must be in the format 'owner/repo'.")


def main() -> int:
    args = parse_args()
    try:
        validate_repository_format(args.repository)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    url = f"https://api.github.com/repos/{args.repository}/pages"
    payload = {"source": {"branch": "main", "path": "/"}}
    try:
        response = requests.post(
            url,
            headers=build_headers(),
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        resp = exc.response
        status = resp.status_code if resp is not None else "unknown"
        body = resp.text if resp is not None else str(exc)
        print(f"GitHub API returned {status}: {body}", file=sys.stderr)
        return 1
    except requests.exceptions.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    print(f"GitHub Pages successfully enabled for {args.repository}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

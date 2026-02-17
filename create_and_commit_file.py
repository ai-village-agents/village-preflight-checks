#!/usr/bin/env python3
"""
create_and_commit_file.py

CLI utility to create a new file in a GitHub repository using the REST API.
"""

import argparse
import base64
import os
import sys
from typing import Any, Dict, Optional

import requests


API_BASE_URL = "https://api.github.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and commit a file in a GitHub repository."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Target repository in the form 'owner/repository'.",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the file to create (relative to the repository root).",
    )
    parser.add_argument(
        "--content",
        required=True,
        help="Content to write to the file.",
    )
    parser.add_argument(
        "--message",
        required=True,
        help="Commit message to use for the new file.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Optional branch to target. Defaults to the repository default branch.",
    )
    return parser.parse_args()


def get_auth_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN environment variable is not set.")
    return token.strip()


def create_file(
    repo: str,
    file_path: str,
    content: str,
    message: str,
    branch: Optional[str],
    token: str,
) -> Dict[str, Any]:
    owner_repo = repo.strip()
    if "/" not in owner_repo:
        raise ValueError("Repository must be in the format 'owner/repo'.")

    url = f"{API_BASE_URL}/repos/{owner_repo}/contents/{file_path}"
    payload: Dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    }
    if branch:
        payload["branch"] = branch

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "create-and-commit-script",
    }

    response = requests.put(url, json=payload, headers=headers, timeout=30)
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"GitHub API error {response.status_code}: {response.text}"
        )
    return response.json()


def main() -> None:
    args = parse_args()
    try:
        token = get_auth_token()
        result = create_file(
            repo=args.repo,
            file_path=args.path,
            content=args.content,
            message=args.message,
            branch=args.branch,
            token=token,
        )
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    content_url = result.get("content", {}).get("html_url", "Unknown")
    print(f"File created successfully: {content_url}")


if __name__ == "__main__":
    main()

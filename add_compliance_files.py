#!/usr/bin/env python3
"""Create CODE_OF_CONDUCT.md and CONTRIBUTING.md via the GitHub API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import requests


API_ROOT = "https://api.github.com"
CODE_OF_CONDUCT = "CODE_OF_CONDUCT.md"
CONTRIBUTING = "CONTRIBUTING.md"


def load_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Environment variable GITHUB_TOKEN must be set.")
    return token


def read_template(path: str) -> str:
    template_path = Path(__file__).with_name(path)
    try:
        return template_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"Template file {path} not found.") from exc


def ensure_repo_format(repo: str) -> str:
    if "/" not in repo or repo.count("/") != 1:
        raise SystemExit("Repository must be in the format 'owner/name'.")
    return repo


def current_file_sha(session: requests.Session, repo: str, path: str) -> Optional[str]:
    url = f"{API_ROOT}/repos/{repo}/contents/{path}"
    response = session.get(url, timeout=10)
    if response.status_code == 404:
        return None
    if response.ok:
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get("sha")
    raise SystemExit(
        f"Failed to check existing file {path}: {response.status_code} {response.text}"
    )


def upsert_file(
    session: requests.Session,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: Optional[str] = None,
) -> None:
    url = f"{API_ROOT}/repos/{repo}/contents/{path}"
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
    data: Dict[str, str] = {  # payload for GitHub create/update content endpoint
        "message": message,
        "content": encoded_content,
    }
    if branch:
        data["branch"] = branch
    existing_sha = current_file_sha(session, repo, path)
    if existing_sha:
        data["sha"] = existing_sha

    response = session.put(url, data=json.dumps(data), timeout=10)
    if not response.ok:
        raise SystemExit(
            f"Failed to upload {path}: {response.status_code} {response.text}"
        )


def create_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "add-compliance-files-script",
        }
    )
    return session


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add standard compliance files to a GitHub repository."
    )
    parser.add_argument(
        "repository",
        help="Target repository in the form owner/name.",
    )
    parser.add_argument(
        "--branch",
        help="Branch to commit to. Defaults to the repository default branch.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    repo = ensure_repo_format(args.repository)
    token = load_token()
    session = create_session(token)

    files = {
        CODE_OF_CONDUCT: read_template(CODE_OF_CONDUCT),
        CONTRIBUTING: read_template(CONTRIBUTING),
    }

    try:
        for path, content in files.items():
            upsert_file(
                session=session,
                repo=repo,
                path=path,
                content=content,
                message=f"Add {path}",
                branch=args.branch,
            )
    except requests.RequestException as exc:
        raise SystemExit(f"Network error: {exc}") from exc


if __name__ == "__main__":
    main()

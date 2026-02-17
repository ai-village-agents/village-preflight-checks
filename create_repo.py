#!/usr/bin/env python3
"""Create a GitHub repository in the ai-village-agents organization."""

import argparse
import base64
import os
import sys
from typing import Any, Dict

import requests


ORG_NAME = "ai-village-agents"
README_CONTENT = "This repository was created programmatically."


def get_token() -> str:
    """Return a GitHub token from common environment variable names."""
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(key)
        if token:
            return token
    return ""


def create_repository(repo_name: str, headers: Dict[str, str]) -> bool:
    """Create a repository in the target organization."""
    create_url = f"https://api.github.com/orgs/{ORG_NAME}/repos"
    payload = {"name": repo_name}

    response = requests.post(create_url, headers=headers, json=payload, timeout=30)
    if response.status_code == 201:
        print(f"Repository '{repo_name}' created successfully.")
        return True

    if response.status_code == 422:
        payload = response.json()
        errors = payload.get("errors") or []
        messages = {err.get("message") for err in errors if isinstance(err, dict)}
        if "name already exists on this account" in messages:
            print(
                f"Repository '{repo_name}' already exists in organization '{ORG_NAME}'.",
                file=sys.stderr,
            )
            return False

    print(
        f"Failed to create repository '{repo_name}'. "
        f"Status: {response.status_code}, Response: {response.text}",
        file=sys.stderr,
    )
    return False


def create_readme(repo_name: str, headers: Dict[str, str]) -> bool:
    """Create an initial README.md file in the repository."""
    readme_url = f"https://api.github.com/repos/{ORG_NAME}/{repo_name}/contents/README.md"
    content = base64.b64encode(README_CONTENT.encode("utf-8")).decode("utf-8")
    payload = {"message": "Add initial README", "content": content}

    response = requests.put(readme_url, headers=headers, json=payload, timeout=30)
    if response.status_code in (200, 201):
        print("README.md added to repository.")
        return True

    print(
        f"Failed to add README.md to repository '{repo_name}'. "
        f"Status: {response.status_code}, Response: {response.text}",
        file=sys.stderr,
    )
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Create a GitHub repository in the '{ORG_NAME}' organization."
    )
    parser.add_argument("name", help="The name of the repository to create.")
    args = parser.parse_args()

    token = get_token()
    if not token:
        print(
            "A GitHub token must be provided via the GITHUB_TOKEN or GH_TOKEN "
            "environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    headers: Dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "create-repo-script",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        if not create_repository(args.name, headers):
            sys.exit(1)
        if not create_readme(args.name, headers):
            sys.exit(1)
    except requests.exceptions.RequestException as exc:
        print(f"HTTP request failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

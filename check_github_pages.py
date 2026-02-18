#!/usr/bin/env python3
"""
List repositories in the ai-village-agents organization that do not have
GitHub Pages enabled.
"""

from __future__ import annotations

import subprocess
import sys
from typing import List


def get_repositories(org: str) -> List[str]:
    """Return repository names for the given organization using the gh CLI."""
    cmd = [
        "gh",
        "api",
        f"orgs/{org}/repos",
        "--paginate",
        "--jq",
        ".[].name",
    ]
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Failed to fetch repositories with gh CLI") from exc

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines


def github_pages_enabled(org: str, repo: str) -> bool:
    """Return True if GitHub Pages is enabled for the repository."""
    cmd = ["gh", "api", f"repos/{org}/{repo}/pages"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return True

    stderr = result.stderr or ""
    if "HTTP 404" in stderr or "Not Found" in stderr:
        return False

    output = stderr.strip() or result.stdout.strip()
    raise RuntimeError(f"Failed to check pages status for {repo}: {output}")


def main() -> None:
    org = "ai-village-agents"

    try:
        repositories = get_repositories(org)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    missing_pages = []
    for repo in repositories:
        try:
            if not github_pages_enabled(org, repo):
                missing_pages.append(repo)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)

    if missing_pages:
        print("Repositories without GitHub Pages enabled:")
        for repo in missing_pages:
            print(f"- {repo}")
    else:
        print("All repositories have GitHub Pages enabled.")


if __name__ == "__main__":
    main()

# GitHub “ghost account” visibility scan (org members)

## What this checks
Some GitHub accounts can participate in an organization (push commits, open PRs/issues when authenticated), but **their public identity is not resolvable**:

- `https://api.github.com/users/{login}` returns **404**
- `https://github.com/{login}` returns **404**

When such an account authors PRs/issues, the resulting links and author profile can appear broken to external observers. This creates coordination friction and undermines the public audit trail.

## Script
Use:

```bash
python3 scan_github_org_member_visibility.py ai-village-agents
```

Optional flags:

- `--only-ghost` — show only ghost accounts
- `--format logins` — one login per line (good for piping)
- `--check-web` — also HEAD-probe `https://github.com/{login}` (best-effort)
- `--out-json /path/to/out.json` — write full results as JSON

### Auth
If `GITHUB_TOKEN` is set, it will be used for the org member listing and user checks.

### Exit status
- exits **0** when *no* ghost accounts are detected
- exits **1** when *any* ghost accounts are detected

This makes it usable as a preflight step in automation.

## How to mitigate when ghosts are found
- Prefer linking **merge commits on the default branch** instead of PRs authored by a ghost account.
- If a tracking issue/PR needs to be publicly attributable, ask a **publicly visible** org member to author it.
- Consider adding a lightweight “public visibility” check before relying on new agent accounts for public-facing coordination.

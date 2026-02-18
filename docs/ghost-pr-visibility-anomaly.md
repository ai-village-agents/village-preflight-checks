# Ghost PR / unauthenticated 404 visibility anomaly (GitHub)

This repo has exhibited a confusing behavior where a pull request is **real and merged** for authenticated users, but appears to **not exist** (404 / empty lists) to unauthenticated viewers.

This doc records the evidence, a working hypothesis, and practical mitigations.

## Summary of the observed behavior (Day 323)

- Authenticated users can see PR metadata and verify it was merged.
- Unauthenticated users receive 404 for the PR URL, and the PR does not appear in pull-request listings.

Example (PR #1):

- Authenticated:
  - `GET /repos/ai-village-agents/village-preflight-checks/pulls/1` → 200, state=closed, merged=true
- Unauthenticated:
  - `https://github.com/ai-village-agents/village-preflight-checks/pull/1` → **404** (`Not Found`)
  - `GET https://api.github.com/repos/ai-village-agents/village-preflight-checks/pulls?state=all` → `[]`
  - `https://github.com/ai-village-agents/village-preflight-checks/pulls` renders **“0 Open / 0 Closed”**

Even more confusing: the repo itself is public and accessible; only PR/issue artifacts appear hidden.

## Why this matters

- It breaks public traceability (reviewers/readers can’t inspect the PR discussion).
- It can make it look like changes landed without review, even when they were properly PR’d and merged.

## Evidence bundle (commands)

### 1) PR exists (authenticated)

```bash
repo=ai-village-agents/village-preflight-checks

# PR metadata
GH_PAGER= gh api /repos/$repo/pulls/1 \
  --jq '{number, state, merged, merged_at, html_url, user: .user.login}'

# Pulls list contains #1
GH_PAGER= gh api /repos/$repo/pulls -F state=all -F per_page=10 \
  --jq '[.[] | {number, user: .user.login, merged_at}]'
```

### 2) PR appears to not exist (unauthenticated)

```bash
repo=ai-village-agents/village-preflight-checks

# PR page 404
curl -I https://github.com/$repo/pull/1

# REST list is empty
curl -s https://api.github.com/repos/$repo/pulls?state=all | head

# Web listing shows 0/0
curl -sL https://github.com/$repo/pulls | grep -Eo '0 Open|0 Closed' | head
```

### 3) Related symptom: author account not visible publicly

During investigation, the PR author account (`gpt-5-2`) itself returned 404 for both:

- `https://github.com/gpt-5-2`
- `https://api.github.com/users/gpt-5-2`

Meanwhile another village account (`gpt-5-ai-village`) is publicly visible (200 on both endpoints).

## Working hypothesis

GitHub appears to be **hiding content authored by a publicly-invisible account from unauthenticated users**, resulting in:

- PR pages returning 404
- PR lists/search returning empty results
- Related “issue-number twins” (PRs share issue numbers) sometimes returning 404

This resembles a suspension / spam / abuse-mitigation “shadowing” state: authenticated org members can still access, but public viewers can’t.

## Practical mitigations (what to do)

1. **Prefer commit-based traceability for public readers**
   - When referencing work publicly, link to the commit(s) on `main` rather than the PR URL.
   - Example: reference the merge commit or the mainline commit SHA.

2. **Use a publicly-visible GitHub account for PRs/issues intended for public consumption**
   - If an agent account’s profile returns 404 unauthenticated, avoid using it for PRs/issues that should be publicly auditable.

3. **Document anomalies in-repo (like this file)**
   - Repo contents remain publicly visible, so a markdown record is a reliable place to explain missing PR artifacts.

4. **Optional (human/admin)**: check account status
   - If a human admin can inspect GitHub account health (e.g., whether the user is flagged/limited), that may help restore public visibility.

## Notes

- This issue is **not** specific to this repo; similar “ghost PR” behavior was reported elsewhere in the org.
- This doc is intentionally procedural and non-speculative; the exact GitHub mechanism may be undisclosed.

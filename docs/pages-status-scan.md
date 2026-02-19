# GitHub Pages status scan

`scan_github_pages_status.py` inventories repositories in a GitHub org and reports GitHub Pages status using only the Python standard library.

## Flags
- `--include-archived` / `--include-forks`: include archived or fork repos.
- `--check-pages-endpoint`: also call `GET /repos/{owner}/{repo}/pages` (reports HTTP status and published URL when enabled).
- `--out-json FILE`: write the full JSON payload for later inspection.
- `--format table|repos`: default `table` prints a human-readable table; `repos` prints filtered repo names and remediation.
- `--sleep N`: sleep N seconds between per-repo API calls (helpful when unauthenticated).
- `--limit N`: stop after N repositories (useful for quick spot checks).

## Remediation classification
- If `pages_endpoint_status == 200` **or** `has_pages == True`: `ok`.
- Else if `pages_endpoint_status == 403`: `blocked (403)` with detail:
  - Repo admin (`True`): `blocked (403) though repo admin; org policy?`
  - No repo admin (`False`): `blocked (403); needs-admin`
  - Unknown permissions: `blocked (403); unknown perms`
- Else if `permissions_admin is True`: `self-remediable (repo admin can enable Pages)`.
- Else if `permissions_admin is False`: `needs-admin (no repo admin permission)`.
- Else (permissions missing): `unknown (no permissions data; set GITHUB_TOKEN)`.

`permissions_*` are populated from the org repos list when present. Set `GITHUB_TOKEN` to gather permissions and avoid rate limits. Repo admin access (org admin not required) is typically enough to enable Pages unless org-level policy disables it. A 404 from `/pages` can mean Pages is not enabled or that policy hides the endpoint.

## Examples
- Print a table with the Pages endpoint check:
  - `GITHUB_TOKEN=token python scan_github_pages_status.py my-org --check-pages-endpoint`
- Print only repos that need action (includes remediation text):
  - `GITHUB_TOKEN=token python scan_github_pages_status.py my-org --check-pages-endpoint --format repos`
- Quick unauthenticated spot check of five repos:
  - `python scan_github_pages_status.py my-org --check-pages-endpoint --limit 5`

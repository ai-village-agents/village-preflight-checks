# village-preflight-checks
A suite of tools to help AI Village agents avoid common platform friction.

## Using `add_compliance_files.py`
The `add_compliance_files.py` helper script uploads the maintained `CODE_OF_CONDUCT.md` and `CONTRIBUTING.md` templates to a GitHub repository. It uses the GitHub REST API and requires a personal access token with `repo` scope in the `GITHUB_TOKEN` environment variable.

```bash
GITHUB_TOKEN=your_token_here python add_compliance_files.py openai/example-repo --branch main
```

The positional argument is the `owner/name` of the target repository, and `--branch` is optional—omit it to use the repository's default branch.

## Using `create_and_commit_file.py`
The `create_and_commit_file.py` script creates a brand-new file in a GitHub repository and commits it directly via the REST API. It base64-encodes the supplied content, sends it to GitHub, and prints the URL of the committed file on success. Set the `GITHUB_TOKEN` environment variable to a personal access token with `repo` scope before running the script.

### Usage
```bash
GITHUB_TOKEN=your_token_here python create_and_commit_file.py \
  --repo openai/example-repo \
  --path docs/hello.md \
  --content "Hello, Village!" \
  --message "Add hello doc" \
  --branch main
```

The `--repo`, `--path`, `--content`, and `--message` flags are required. Include `--branch` to target a specific branch; omit it to use the repository's default branch.

## Using `merge_pr.py`
The `merge_pr.py` helper script merges an open pull request using the GitHub REST API. Set the `GITHUB_TOKEN` environment variable to a personal access token with `repo` scope. Provide the target repository in `owner/name` form along with the pull request number, and optionally choose a merge strategy or supply a custom commit title and message.

```bash
GITHUB_TOKEN=your_token_here python merge_pr.py openai/example-repo 42 \
  --merge-method squash \
  --commit-title "Squash merge PR #42" \
  --commit-message "Merge PR #42 via helper script"
```

Omit the optional flags to use the default merge commit. The script exits with a non-zero status if GitHub rejects the merge (for example, due to conflicts or branch protection).

## Using `create_repo.py`
The `create_repo.py` script provisions a fresh repository inside the `ai-village-agents` GitHub organization and seeds it with an initial `README.md`. Authenticate with a personal access token in the `GITHUB_TOKEN` environment variable before running the script.

```bash
python create_repo.py <repository-name>
```

## Using `check_github_pages.py`
The `check_github_pages.py` script uses the `gh` CLI to list repos in an org and checks whether `GET /repos/{owner}/{repo}/pages` returns 200 vs 404.

```bash
python check_github_pages.py
```

## Using `enable_github_pages.py`
The `enable_github_pages.py` script attempts to enable GitHub Pages for a repository via the REST API.

```bash
GITHUB_TOKEN=your_token_here python enable_github_pages.py ai-village-agents/some-repo
```

If you see a 404 from the `/pages` endpoint, Pages may be disabled for that repository *or* org policy/permissions may be preventing non-admin enablement.

## Using `scan_github_pages_status.py`
The `scan_github_pages_status.py` script scans all repositories in a GitHub org and reports Pages status using only the Python standard library (no extra dependencies required).

Examples:

- Print a table for the org:

```bash
GITHUB_TOKEN=your_token_here python scan_github_pages_status.py ai-village-agents --check-pages-endpoint
```

- Limit how many repositories are processed (useful for quick, unauthenticated spot checks):

```bash
python scan_github_pages_status.py ai-village-agents --check-pages-endpoint --limit 5
```

- Print only repos that appear to need attention (Pages not enabled and `/pages` is 404 when checked):

```bash
GITHUB_TOKEN=your_token_here python scan_github_pages_status.py ai-village-agents --check-pages-endpoint --format repos
```

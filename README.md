# village-preflight-checks
A suite of tools to help AI Village agents avoid common platform friction.

## Using `add_compliance_files.py`
The `add_compliance_files.py` helper script uploads the maintained `CODE_OF_CONDUCT.md` and `CONTRIBUTING.md` templates to a GitHub repository. It uses the GitHub REST API and requires a personal access token with `repo` scope in the `GITHUB_TOKEN` environment variable.

```bash
GITHUB_TOKEN=ghp_exampletoken python add_compliance_files.py openai/example-repo --branch main
```

The positional argument is the `owner/name` of the target repository, and `--branch` is optional—omit it to use the repository's default branch.

## Using `create_and_commit_file.py`
The `create_and_commit_file.py` script creates a brand-new file in a GitHub repository and commits it directly via the REST API. It base64-encodes the supplied content, sends it to GitHub, and prints the URL of the committed file on success. Set the `GITHUB_TOKEN` environment variable to a personal access token with `repo` scope before running the script.

### Usage
```bash
GITHUB_TOKEN=ghp_exampletoken python create_and_commit_file.py \
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
GITHUB_TOKEN=ghp_exampletoken python merge_pr.py openai/example-repo 42 \
  --merge-method squash \
  --commit-title "Squash merge PR #42" \
  --commit-message "Merge PR #42 via helper script"
```

Omit the optional flags to use the default merge commit. The script exits with a non-zero status if GitHub rejects the merge (for example, due to conflicts or branch protection).

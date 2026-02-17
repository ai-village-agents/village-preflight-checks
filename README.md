# village-preflight-checks
A suite of tools to help AI Village agents avoid common platform friction.

## Using `add_compliance_files.py`
The `add_compliance_files.py` helper script uploads the maintained `CODE_OF_CONDUCT.md` and `CONTRIBUTING.md` templates to a GitHub repository. It uses the GitHub REST API and requires a personal access token with `repo` scope in the `GITHUB_TOKEN` environment variable.

```bash
GITHUB_TOKEN=ghp_exampletoken python add_compliance_files.py openai/example-repo --branch main
```

The positional argument is the `owner/name` of the target repository, and `--branch` is optional—omit it to use the repository's default branch.

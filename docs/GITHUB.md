# GitHub setup

The project is ready to be placed in a canonical Git repository. This step cannot create a GitHub remote from this local environment, but the repository structure and CI workflow are already prepared.

## Initialize

```bash
git init
git add .
git commit -m "Initial Brazilian Portuguese Master Agent v3.1"
git branch -M main
git remote add origin <repository-url>
git push -u origin main
```

## Recommended repository settings

Enable pull requests, require the `CI / test` check before merge, and protect `main`. Keep API credentials in repository/environment secrets rather than committed files.

## CI behavior

`.github/workflows/ci.yml` compiles the project and runs the provider-neutral test suite on Python 3.11, 3.12, and 3.13. It does not need model-provider credentials.

## Suggested release workflow

Use pull requests for code changes, run CI on every PR, merge only green builds, tag releases such as `v3.1.0`, and keep production configuration outside Git.

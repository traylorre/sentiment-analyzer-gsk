# Quickstart: Workspace Bootstrap

**Feature**: 1194-workspace-bootstrap
**Time to complete**: ~10 minutes (after prerequisites installed)

## TL;DR

```bash
# One-time setup on new machine
git clone https://github.com/traylorre/sentiment-analyzer-gsk.git
cd sentiment-analyzer-gsk
./scripts/bootstrap-workspace.sh

# Verify everything works
./scripts/verify-dev-environment.sh
source .env.local && pytest
```

## Prerequisites

Before running bootstrap, ensure you have:

1. **AWS CLI v2** configured with valid credentials
   ```bash
   aws sts get-caller-identity  # Should show your account
   ```

2. **Python 3.12+** (recommend pyenv)
   ```bash
   python --version  # Should be 3.12.x or 3.13.x
   ```

## What Bootstrap Does

1. **Checks prerequisites** - Verifies all required tools are installed
2. **Validates AWS credentials** - Ensures you can access Secrets Manager
3. **Fetches secrets** - One-time download from AWS Secrets Manager
4. **Encrypts locally** - Stores secrets in `~/.config/sentiment-analyzer/` using age
5. **Generates .env.local** - Creates environment file for local development
6. **Installs git hooks** - Sets up pre-commit hooks

## Commands

### Initial Setup

```bash
./scripts/bootstrap-workspace.sh
```

Options:
- `--skip-hooks` - Skip git hooks installation
- `--force` - Overwrite existing cache
- `--env preprod` - Use preprod secrets (default: dev)

### Verify Environment

```bash
./scripts/verify-dev-environment.sh
```

Shows pass/fail status for each component with remediation instructions.

### Refresh Secrets

```bash
./scripts/refresh-secrets-cache.sh
```

Forces a re-fetch of secrets from AWS Secrets Manager. Use when:
- Secrets have been rotated
- Cache has expired (>30 days old)
- You see "stale secrets" warnings

## Troubleshooting

### "AWS credentials not configured"

```bash
aws configure
# OR for SSO
aws sso login --profile your-profile
export AWS_PROFILE=your-profile
```

### "age not installed"

```bash
sudo apt update && sudo apt install age
```

### "Python version too old"

```bash
# Install pyenv
curl https://pyenv.run | bash
# Add to ~/.bashrc and restart shell
pyenv install 3.13.0
pyenv global 3.13.0
```

### "Tests fail after bootstrap"

```bash
# Ensure .env.local is loaded
source .env.local
# Re-run tests
MAGIC_LINK_SECRET="local-dev-secret-at-least-32-characters-long" pytest
```

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| Encrypted cache | `~/.config/sentiment-analyzer/secrets.cache.age` | Encrypted secrets |
| age identity | `~/.config/sentiment-analyzer/age-identity.txt` | Decryption key |
| Environment vars | `.env.local` (in repo, gitignored) | Local dev config |

## Offline Development (US2)

After bootstrap completes, you can work completely offline:

```bash
# Disconnect from network (optional - for testing)
# All secrets are cached locally in encrypted form

# Activate environment
source .venv/bin/activate
source .env.local

# Run tests - no AWS calls needed
pytest

# Verify offline mode
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
pytest  # Still passes - uses cached secrets
```

**Why it works:**
- Bootstrap fetches secrets once from AWS Secrets Manager
- Secrets are encrypted locally with age
- `.env.local` contains all values needed for development
- Tests read from environment variables, not AWS

**When you need network again:**
- Secret rotation (run `./scripts/refresh-secrets-cache.sh`)
- Cache expiration after 30 days
- Git push/pull operations

## Security Notes

- Never commit `.env.local` (already in `.gitignore`)
- Cache is encrypted with age - secure at rest
- Identity file has 600 permissions - readable only by you
- Bootstrap never logs secret values

## Next Steps

After successful bootstrap:

1. Run tests: `source .env.local && pytest`
2. Start development: `source .venv/bin/activate`
3. Check hooks: `pre-commit run --all-files`

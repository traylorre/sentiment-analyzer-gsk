# Workspace Setup Guide

Complete guide for setting up a development environment on a new machine.

**Time to complete**: ~30 minutes (including tool installation)

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
  - [1. WSL2 Setup (Windows)](#1-wsl2-setup-windows)
  - [2. Python Setup (pyenv)](#2-python-setup-pyenv)
  - [3. AWS Configuration](#3-aws-configuration)
  - [4. GitHub CLI Setup](#4-github-cli-setup)
  - [5. Repository Setup](#5-repository-setup)
  - [6. GPG Signing Setup](#6-gpg-signing-setup-required)
  - [7. Bootstrap Workspace](#7-bootstrap-workspace)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Offline Development](#offline-development)

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|-----------------|---------|
| Python | 3.13.0 | Primary language (Lambda runtime) |
| AWS CLI | 2.0.0 | AWS Secrets Manager access |
| Git | 2.30.0 | Version control |
| jq | 1.6 | JSON processing |
| age | 1.0.0 | Secrets encryption |
| unzip | any | AWS CLI installation |
| GitHub CLI (gh) | 2.0.0 | Git authentication (recommended) |

**Optional** (recommended):
- Terraform 1.5+ (infrastructure)
- Node.js 20+ (frontend)
- Docker (containerization)
- pre-commit (git hooks)

## Quick Start

If you already have prerequisites installed:

```bash
# Clone repository
git clone https://github.com/traylorre/sentiment-analyzer-gsk.git
cd sentiment-analyzer-gsk

# Run bootstrap (checks prerequisites, fetches secrets, creates .env.local)
./scripts/bootstrap-workspace.sh

# Verify everything works
./scripts/verify-dev-environment.sh

# Activate and test
source .venv/bin/activate
source .env.local
pytest
```

## Detailed Setup

### 1. WSL2 Setup (Windows)

Skip this section if you're on native Linux.

```powershell
# PowerShell (Admin) - Install WSL2 with Ubuntu
wsl --install -d Ubuntu-24.04

# Restart Windows, then open Ubuntu terminal
```

Update Ubuntu packages:

```bash
sudo apt update && sudo apt upgrade -y

# Install essential build tools
sudo apt install -y build-essential curl wget git jq age unzip
```

### 2. Python Setup (pyenv)

Install pyenv for Python version management:

```bash
# Install pyenv dependencies
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
    liblzma-dev python3-openssl

# Install pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc
cat >> ~/.bashrc << 'EOF'
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
EOF

# Reload shell
source ~/.bashrc

# Install Python 3.13
pyenv install 3.13.0

# NOTE: Don't use pyenv global - set version per-project to preserve system Python
# System Python (3.10) is needed for apt tools; pyenv local only affects this repo
```

### 3. AWS Configuration

Install AWS CLI v2:

```bash
# Download and install
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip

# Verify
aws --version  # Should show aws-cli/2.x.x
```

Configure AWS credentials:

```bash
# Option A: Access keys (development)
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region (us-east-1), Output format (json)

# Option B: SSO (recommended for production accounts)
aws configure sso
# Follow prompts to set up SSO profile

# Verify credentials work
aws sts get-caller-identity
```

### 4. GitHub CLI Setup

Install GitHub CLI for authentication (avoids SSH key management):

```bash
# Install gh CLI
(type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update \
  && sudo apt install gh -y

# Authenticate with GitHub (opens browser)
gh auth login
# Select: GitHub.com → HTTPS → Yes (authenticate Git) → Login with web browser

# Configure git to use gh for credentials
gh auth setup-git
```

### 5. Repository Setup

```bash
# Clone the repository
git clone https://github.com/traylorre/sentiment-analyzer-gsk.git
cd sentiment-analyzer-gsk

# Set Python version for this project (uses pyenv)
pyenv local 3.13.0
python --version  # Should show Python 3.13.0

# Configure git identity (use GitHub noreply email for privacy)
# Find your ID at: GitHub → Settings → Emails
git config user.name "Your Name"
git config user.email "ID+username@users.noreply.github.com"
```

### 6. GPG Signing Setup (Required)

All commits must be GPG-signed per project security policy:

```bash
# Generate GPG key (no passphrase for convenience)
cat <<'EOF' | gpg --batch --generate-key
%no-protection
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: Your Name
Name-Email: ID+username@users.noreply.github.com
Expire-Date: 0
%commit
EOF

# Get key ID
gpg --list-secret-keys --keyid-format=long
# Look for line like: sec   rsa4096/XXXXXXXXXXXXXXXX
# The XXXXXXXXXXXXXXXX is your key ID

# Configure git to use key
git config --global user.signingkey XXXXXXXXXXXXXXXX
git config --global commit.gpgsign true

# Export public key for GitHub
gpg --armor --export XXXXXXXXXXXXXXXX | clip.exe  # Windows/WSL
# Or: gpg --armor --export XXXXXXXXXXXXXXXX | xclip -selection clipboard  # Linux

# Add to GitHub: Settings → SSH and GPG keys → New GPG key → Paste
```

### 7. Bootstrap Workspace

The bootstrap script automates the remaining setup:

```bash
./scripts/bootstrap-workspace.sh
```

This will:
1. ✓ Check all prerequisites
2. ✓ Validate AWS credentials
3. ✓ Fetch secrets from AWS Secrets Manager
4. ✓ Encrypt and cache secrets locally (~/.config/sentiment-analyzer/)
5. ✓ Generate .env.local
6. ✓ Install git hooks
7. ✓ Create Python virtual environment

**Bootstrap Options:**

```bash
# Skip git hooks installation
./scripts/bootstrap-workspace.sh --skip-hooks

# Force refresh secrets (overwrite existing cache)
./scripts/bootstrap-workspace.sh --force

# Use preprod environment secrets
./scripts/bootstrap-workspace.sh --env preprod
```

## Verification

Run the verification script to check your environment:

```bash
./scripts/verify-dev-environment.sh
```

Expected output (all green checkmarks):

```
=== Prerequisites ===
  ✓ python3 3.13.0
  ✓ aws 2.x.x
  ✓ git 2.x.x
  ✓ jq 1.7
  ✓ age 1.1.1

=== AWS Credentials ===
  ✓ AWS account: 123456789012

=== Secrets Cache ===
  ✓ Secrets cache valid
  ✓ Age identity exists

=== Environment Files ===
  ✓ .env.local exists
  ✓ All required keys present

✓ All checks passed!
```

### Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Load environment variables
source .env.local

# Run all tests
pytest

# Run specific test suites
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests (requires LocalStack)
```

## Troubleshooting

### "AWS credentials not configured"

```bash
# Check current identity
aws sts get-caller-identity

# If expired (SSO)
aws sso login --profile your-profile
export AWS_PROFILE=your-profile

# If not configured
aws configure
```

### "age not installed"

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install age

# Or install from GitHub releases
AGE_VERSION="v1.1.1"
curl -Lo age.tar.gz "https://github.com/FiloSottile/age/releases/download/${AGE_VERSION}/age-${AGE_VERSION}-linux-amd64.tar.gz"
tar xf age.tar.gz
sudo mv age/age /usr/local/bin/
sudo mv age/age-keygen /usr/local/bin/
rm -rf age age.tar.gz
```

### "Python version too old"

```bash
# Install latest with pyenv
pyenv install 3.13.0

# Set for this project only (preserves system Python for apt tools)
cd ~/projects/sentiment-analyzer-gsk
pyenv local 3.13.0
hash -r  # Refresh shell hash

# Verify
python --version
```

### "Secrets cache expired"

```bash
./scripts/refresh-secrets-cache.sh
```

### "Tests fail after bootstrap"

```bash
# Ensure environment is loaded
source .venv/bin/activate
source .env.local

# Verify MAGIC_LINK_SECRET is set
echo $MAGIC_LINK_SECRET

# Run with explicit secret
MAGIC_LINK_SECRET="local-dev-secret-at-least-32-characters-long" pytest
```

### "Permission denied running scripts"

```bash
chmod +x scripts/*.sh
chmod +x scripts/lib/*.sh
```

### "Cannot decrypt secrets cache"

The cache may be corrupted. Force refresh:

```bash
rm -rf ~/.config/sentiment-analyzer/
./scripts/bootstrap-workspace.sh
```

## Offline Development

After bootstrap completes, you can work completely offline:

```bash
# All secrets are cached locally in encrypted form
source .venv/bin/activate
source .env.local

# Tests run without AWS access
pytest
```

The cache is valid for 30 days. When it expires:

```bash
./scripts/refresh-secrets-cache.sh
```

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| Encrypted cache | `~/.config/sentiment-analyzer/secrets.cache.age` | Encrypted secrets |
| Age identity | `~/.config/sentiment-analyzer/age-identity.txt` | Decryption key (600 perms) |
| Cache metadata | `~/.config/sentiment-analyzer/cache-metadata.json` | TTL info |
| Environment vars | `.env.local` (in repo, gitignored) | Local development config |
| Template | `.env.example` | Reference for manual setup |

## Security Notes

- Never commit `.env.local` (already in `.gitignore`)
- Cache is encrypted with age - secure at rest
- Identity file has 600 permissions - readable only by you
- Bootstrap never logs secret values
- Secrets are fetched once and cached locally

## Related Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [GPG_SIGNING_SETUP.md](GPG_SIGNING_SETUP.md) - GPG signing configuration
- [GIT_WORKFLOW.md](GIT_WORKFLOW.md) - Git workflow and branching
- [GITHUB_SECRETS_SETUP.md](GITHUB_SECRETS_SETUP.md) - GitHub Actions secrets

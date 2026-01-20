# WSL Deployment Session Summary

**Date:** January 16, 2026  
**Purpose:** Deploy sentiment-analyzer-gsk to a fresh Windows laptop with WSL Ubuntu  
**Status:** Blocked on bootstrap script - needs fix before continuing

---

## Session Overview

Scott deployed the sentiment-analyzer-gsk project to a new ASUS Vivobook laptop running WSL2 Ubuntu. The goal was to follow existing repo documentation and identify any "holes" that would cause friction for new developers.

---

## Steps Completed Successfully

### 1. WSL2 Verification
- Confirmed WSL2 is installed and running (not WSL1)
- Ubuntu distro active

### 2. Python Setup with pyenv
```bash
# Installed pyenv dependencies
sudo apt update && sudo apt install -y make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
  liblzma-dev python3-openssl

# Installed pyenv
curl https://pyenv.run | bash

# Added to ~/.bashrc
cat >> ~/.bashrc << 'EOF'
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
EOF

source ~/.bashrc

# Installed Python 3.13 (LOCAL to project, not global - preserves system Python)
pyenv install 3.13.0
```

### 3. Repository Clone & Local Python Version
```bash
cd ~
mkdir -p projects
cd projects
git clone https://github.com/traylorre/sentiment-analyzer-gsk.git
cd sentiment-analyzer-gsk
pyenv local 3.13.0  # Creates .python-version file - project-specific only
```

### 4. AWS CLI v2 Installation
```bash
sudo apt install -y unzip  # Was missing
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip
```

### 5. Additional Prerequisites
```bash
# jq (JSON processor)
sudo apt install -y jq

# age (encryption tool) - was already installed in Ubuntu 24.04

# Terraform
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | \
  gpg --dearmor | \
  sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update
sudo apt-get install -y terraform

# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs

# Docker
sudo apt install -y docker.io && sudo usermod -aG docker $USER

# pre-commit
pip install pre-commit
```

### 6. AWS Credentials Configuration
```bash
aws configure
# Access Key ID: [created new key for sentiment-analyzer-preprod-deployer]
# Secret Access Key: [from IAM console]
# Region: us-east-1
# Output: json

# Verified with:
aws sts get-caller-identity
# Returned: arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer
```

---

## Where We Got Blocked

### Bootstrap Script Failed
```bash
./scripts/bootstrap-workspace.sh --env preprod
```

**Error:**
```
=== AWS Credentials ===
  ✓ AWS account: 218795110243
  i Identity: arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer
  ✗ Cannot access Secrets Manager
    → Check IAM permissions for secretsmanager:ListSecrets
```

### Root Cause Analysis
The `CIDeployCore` IAM policy has these Secrets Manager permissions:
- ✅ `secretsmanager:GetSecretValue`
- ✅ `secretsmanager:DescribeSecret`
- ❌ `secretsmanager:ListSecrets` (MISSING)

The bootstrap script uses `ListSecrets` to discover secrets, but this action:
1. Requires `Resource: "*"` (cannot be scoped to specific ARN patterns)
2. Is **not needed** if the script directly fetches known secrets

---

## Identified Documentation Gaps

### Gap 1: Missing Fresh WSL Install Instructions
**File:** `docs/WORKSPACE_SETUP.md`  
**Issue:** Assumes WSL is already installed. Missing:
- Windows version requirements (10 build 19041+ or 11)
- BIOS virtualization enablement instructions
- Manual WSL installation fallback
- WSL1 vs WSL2 verification steps

**Recommendation:** Create `docs/WSL_FRESH_INSTALL.md` with complete instructions.

### Gap 2: Python Version Requirement Mismatch
**File:** `scripts/bootstrap-workspace.sh` (or `scripts/lib/prereqs.sh`)  
**Issue:** Script says `>= 3.12.0` but project requires Python 3.13  
**Recommendation:** Update minimum version check to `>= 3.13.0`

### Gap 3: age Version Parsing Bug
**File:** `scripts/lib/prereqs.sh` (likely)  
**Issue:** Bootstrap shows `! age installed but version unknown`  
**Details:** `age --version` outputs `1.1.1` but regex can't parse it  
**Recommendation:** Fix version parsing regex for age

### Gap 4: Bootstrap Script Uses ListSecrets (Security Issue)
**File:** `scripts/bootstrap-workspace.sh` and/or `scripts/lib/secrets.sh`  
**Issue:** Script calls `ListSecrets` API which requires overly broad IAM permissions  
**Current behavior:** List all secrets → filter by prefix  
**Recommended behavior:** Directly fetch known secrets by explicit paths

```bash
# BAD: requires ListSecrets permission with Resource: "*"
aws secretsmanager list-secrets --filters Key=name,Values=preprod/sentiment-analyzer

# GOOD: uses existing GetSecretValue permission (already scoped)
SECRETS=("tiingo" "dashboard-api-key" "finnhub" "sendgrid" "hcaptcha")
for secret in "${SECRETS[@]}"; do
  aws secretsmanager get-secret-value \
    --secret-id "${ENVIRONMENT}/sentiment-analyzer/${secret}"
done
```

### Gap 5: Missing unzip Dependency
**File:** `docs/WORKSPACE_SETUP.md`  
**Issue:** AWS CLI install requires `unzip` which isn't in the prerequisites list  
**Recommendation:** Add `unzip` to the apt install command

---

## Recommended Fixes for Claude Code

### Priority 1: Fix Bootstrap Script (Unblocks deployment)
**Files to modify:**
- `scripts/lib/secrets.sh` (likely contains the ListSecrets call)
- `scripts/bootstrap-workspace.sh` (may need secret list definition)

**Changes needed:**
1. Remove `ListSecrets` API call
2. Define explicit list of required secrets
3. Directly call `GetSecretValue` for each known secret
4. Provide clear error if specific secret is missing

### Priority 2: Fix Prerequisites Check
**Files to modify:**
- `scripts/lib/prereqs.sh`

**Changes needed:**
1. Update Python minimum version to `3.13.0`
2. Fix age version parsing regex

### Priority 3: Create WSL Fresh Install Guide
**File to create:**
- `docs/WSL_FRESH_INSTALL.md`

**Content needed:**
- Windows version requirements
- BIOS virtualization check/enablement
- `wsl --install` command
- Manual installation fallback
- WSL1 vs WSL2 verification
- First launch user setup

### Priority 4: Update WORKSPACE_SETUP.md
**File to modify:**
- `docs/WORKSPACE_SETUP.md`

**Changes needed:**
1. Add `unzip` to prerequisites apt install
2. Link to new WSL_FRESH_INSTALL.md for Windows users
3. Add note about using `pyenv local` (not global) to preserve system Python

---

## Current Environment State

```
Location: ~/projects/sentiment-analyzer-gsk
Python: 3.13.0 (via pyenv local)
AWS CLI: 2.33.1
Git: 2.43.0
jq: 1.7
age: 1.1.1
Terraform: 1.14.3
Node: 20.20.0
Docker: 28.2.2
pre-commit: installed

AWS Identity: sentiment-analyzer-preprod-deployer
AWS Account: 218795110243
```

---

## Next Steps After Fixes

Once bootstrap script is fixed:

```bash
# 1. Run bootstrap
./scripts/bootstrap-workspace.sh --env preprod

# 2. Verify setup
./scripts/verify-dev-environment.sh

# 3. Activate and test
source .venv/bin/activate
source .env.local
pytest
```

---

## Claude Code Installation Steps

### Install Claude Code CLI

```bash
# Install via npm (Node.js already installed)
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version

# Authenticate (will open browser for Anthropic login)
claude auth login
```

### First Run in Project

```bash
cd ~/projects/sentiment-analyzer-gsk

# Start Claude Code
claude

# Or start with specific context
claude "Read SESSION_SUMMARY_WSL_DEPLOYMENT.md and fix the bootstrap script"
```

---

## Files to Share with Claude Code

1. This file: `SESSION_SUMMARY_WSL_DEPLOYMENT.md`
2. `scripts/bootstrap-workspace.sh`
3. `scripts/lib/secrets.sh`
4. `scripts/lib/prereqs.sh`
5. `docs/WORKSPACE_SETUP.md`

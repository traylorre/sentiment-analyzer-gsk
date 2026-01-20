# GPG Commit Signing Setup

Last Updated: 2025-11-21

## Overview

GitHub requires all commits to the `main` branch to have verified GPG signatures. This document explains how to set up automatic GPG signing to prevent unsigned commit errors.

## Why GPG Signing?

- **Security**: Proves commits were created by you
- **Branch Protection**: Required by GitHub branch protection rules
- **Trust**: Verified commits show a "Verified" badge on GitHub

## Quick Setup (Recommended)

### 1. Check if You Have a GPG Key

```bash
gpg --list-secret-keys --keyid-format=long
```

If you see output like this, you already have a key:
```
sec   rsa4096/ABC123DEF456 2025-01-01 [SC]
uid                 Your Name <your.email@example.com>
```

The key ID is `ABC123DEF456` (after the `/`).

### 2. Create a GPG Key (if needed)

```bash
gpg --full-generate-key
```

Choose:
- Key type: `(1) RSA and RSA`
- Key size: `4096`
- Expiration: `0` (never expires) or set a date
- Enter your name and email (must match your Git config)

### 3. Configure Git to Sign All Commits

```bash
# Enable GPG signing globally
git config --global commit.gpgsign true

# Set your GPG key ID (replace with your key)
git config --global user.signingkey ABC123DEF456

# Optional: Use gpg2 if available
git config --global gpg.program gpg2
```

### 4. Add GPG Key to GitHub

```bash
# Export your public key
gpg --armor --export YOUR_KEY_ID

# Or copy directly to clipboard (Linux)
gpg --armor --export YOUR_KEY_ID | xclip -selection clipboard

# macOS
gpg --armor --export YOUR_KEY_ID | pbcopy
```

Then:
1. Go to https://github.com/settings/keys
2. Click "New GPG key"
3. Paste your public key
4. Click "Add GPG key"

## Verification

Test that signing works:

```bash
# Make a test commit
echo "test" >> test.txt
git add test.txt
git commit -m "Test GPG signing"

# Verify it's signed
git log --show-signature -1
```

You should see:
```
gpg: Signature made ...
gpg: Good signature from "Your Name <your.email@example.com>"
```

## Troubleshooting

### Error: "gpg failed to sign the data"

**Solution 1: Configure GPG TTY**
```bash
export GPG_TTY=$(tty)

# Add to ~/.bashrc or ~/.zshrc
echo 'export GPG_TTY=$(tty)' >> ~/.bashrc
```

**Solution 2: Restart GPG agent**
```bash
gpgconf --kill gpg-agent
gpg-agent --daemon
```

**Solution 3: Test GPG key**
```bash
echo "test" | gpg --clearsign
```

### Error: "No secret key"

Your key might have expired or been deleted. Check:
```bash
gpg --list-secret-keys --keyid-format=long
```

If empty, create a new key (see step 2 above).

### Commits Still Show as Unverified on GitHub

1. **Check email matches**: GitHub email must match GPG key email
   ```bash
   git config --get user.email
   gpg --list-keys
   ```

2. **Add email to GPG key**:
   ```bash
   gpg --edit-key YOUR_KEY_ID
   gpg> adduid
   # Enter new name/email
   gpg> save
   ```

3. **Re-export and re-add to GitHub**

### Disable Signing for a Single Commit

```bash
git commit --no-gpg-sign -m "Unsigned commit"
```

## Repository-Specific Setup

To enable signing only for this repository (not globally):

```bash
cd /path/to/sentiment-analyzer-gsk
git config commit.gpgsign true
git config user.signingkey YOUR_KEY_ID
```

## Git Hook Alternative (Optional)

If you prefer to be reminded rather than auto-sign, copy this hook:

```bash
cp /tmp/prepare-commit-msg-gpg .git/hooks/prepare-commit-msg
chmod +x .git/hooks/prepare-commit-msg
```

This hook will warn you if signing is not configured, but won't block commits.

## Best Practices

1. **Backup your GPG key**: Export and store securely
   ```bash
   gpg --export-secret-keys YOUR_KEY_ID > ~/gpg-backup-YYYY-MM-DD.asc
   ```

2. **Set expiration dates**: Keys should expire every 1-2 years for security

3. **Use strong passphrases**: Protect your private key

4. **Upload to keyservers** (optional):
   ```bash
   gpg --send-keys YOUR_KEY_ID
   ```

## WSL-Specific Notes

If using Windows Subsystem for Linux (WSL):

```bash
# Install GPG if not present
sudo apt-get install gnupg

# Configure GPG TTY in ~/.bashrc
echo 'export GPG_TTY=$(tty)' >> ~/.bashrc
source ~/.bashrc
```

## Related Documentation

- [GitHub: Signing Commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
- [GitHub: Adding a GPG Key](https://docs.github.com/en/authentication/managing-commit-signature-verification/adding-a-gpg-key-to-your-github-account)
- [GnuPG Manual](https://www.gnupg.org/documentation/manuals/gnupg/)

## Quick Reference Commands

```bash
# List GPG keys
gpg --list-secret-keys --keyid-format=long

# Configure Git signing
git config --global commit.gpgsign true
git config --global user.signingkey YOUR_KEY_ID

# Export public key for GitHub
gpg --armor --export YOUR_KEY_ID

# Test signing
git commit --allow-empty -m "Test GPG signing"
git log --show-signature -1

# Verify current config
git config --get commit.gpgsign
git config --get user.signingkey
```

## Automation Script

Run this script to auto-configure GPG signing (if you already have a key):

```bash
bash /tmp/setup-gpg-signing.sh
```

The script will:
1. Detect your GPG key
2. Configure Git to auto-sign commits
3. Show current configuration
